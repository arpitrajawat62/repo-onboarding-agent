import os
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, BackgroundTasks

from app.store import create_repo, get_repo, update_repo_status, set_chunk_count
from app.api.schemas import CreateRepoRequest, CreateRepoResponse, RepoStatusResponse
from app.ingestion.cloner import clone_repo, WORKSPACE_DIR
from app.ingestion.parser import parse_repo, IGNORED_DIRS
from app.ingestion.indexer import index_chunks

router = APIRouter(prefix="/repos", tags=["repos"])

MAX_TREE_NODES = 600


def process_repository_task(repo_id: str, repo_url: str):
    stage = "starting"
    try:
        stage = "cloning"
        update_repo_status(repo_id, stage)
        t = time.time()
        clone_repo(repo_id, repo_url)
        print(f"[{repo_id[:8]}] clone: {time.time() - t:.0f}s")

        stage = "parsing"
        update_repo_status(repo_id, stage)
        t = time.time()
        chunks = parse_repo(WORKSPACE_DIR / repo_id)
        set_chunk_count(repo_id, len(chunks))
        print(f"[{repo_id[:8]}] parse: {time.time() - t:.0f}s, {len(chunks)} chunks")

        stage = "indexing"
        update_repo_status(repo_id, stage)
        t = time.time()
        index_chunks(repo_id, chunks)
        print(f"[{repo_id[:8]}] index: {time.time() - t:.0f}s")

        update_repo_status(repo_id, "ready")
    except Exception as e:
        update_repo_status(repo_id, "failed", error=f"during {stage}: {e}")


@router.post("", response_model=CreateRepoResponse)
def submit_repo(payload: CreateRepoRequest, background_tasks: BackgroundTasks):
    record = create_repo(payload.repo_url)
    background_tasks.add_task(process_repository_task, record.id, record.repo_url)
    return CreateRepoResponse(repo_id=record.id, status=record.status)


@router.get("/{repo_id}/status", response_model=RepoStatusResponse)
def get_repo_status(repo_id: str):
    record = get_repo(repo_id)
    if not record:
        raise HTTPException(status_code=404, detail="repo not found")

    return RepoStatusResponse(
        repo_id=record.id,
        repo_url=record.repo_url,
        status=record.status,
        error=record.error,
        chunk_count=record.chunk_count,
    )


@router.get("/{repo_id}/tree")
def get_repo_tree(repo_id: str):
    record = get_repo(repo_id)
    if not record:
        raise HTTPException(status_code=404, detail="repo not found")
    root = WORKSPACE_DIR / repo_id
    if not root.exists():
        raise HTTPException(status_code=404, detail="repo files not found on disk")

    entries = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS]
        base = Path(dirpath).relative_to(root)
        entries += [(base / d, "dir") for d in dirnames]
        entries += [(base / f, "file") for f in filenames]

    # shallow entries first, so a cap never keeps a child without its parent
    entries.sort(key=lambda e: (len(e[0].parts), e[0].as_posix().lower()))
    truncated = len(entries) > MAX_TREE_NODES
    entries = entries[:MAX_TREE_NODES]

    name = record.repo_url.rstrip("/").split("/")[-1]
    nodes = [{"id": ".", "name": name, "type": "dir", "parent": None}]
    for rel, kind in entries:
        nodes.append({"id": rel.as_posix(), "name": rel.name, "type": kind, "parent": rel.parent.as_posix()})
    return {"nodes": nodes, "truncated": truncated}