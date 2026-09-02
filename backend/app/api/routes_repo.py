from fastapi import APIRouter, HTTPException, BackgroundTasks

from app.store import create_repo, get_repo, update_repo_status
from app.api.schemas import CreateRepoRequest, CreateRepoResponse, RepoStatusResponse

from app.ingestion.cloner import clone_repo


router = APIRouter(prefix="/repos", tags=["repos"])



def process_repository_task(repo_id: str, repo_url: str):

    try:
        update_repo_status(repo_id, "cloning")
        clone_repo(repo_id, repo_url)

        update_repo_status(repo_id, "parsing")
        update_repo_status(repo_id, "indexing")
        update_repo_status(repo_id, "ready")

    except Exception as e:

        update_repo_status(repo_id,"failed", error=str(e))


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
        error=record.status,
    )