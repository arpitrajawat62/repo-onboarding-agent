from pathlib import Path

from app.ingestion.cloner import WORKSPACE_DIR
from app.ingestion.indexer import embed_text
from app.vectorstore import search_chunks



def list_dir(repo_id: str, sub_path: str = ".") -> list[str]:

    target = WORKSPACE_DIR / repo_id / sub_path
    if not target.exists():
        return []
    return sorted(p.name for p in target.iterdir())


def read_file(repo_id: str, file_path: str, max_chars: int = 4000) -> str:

    target = WORKSPACE_DIR / repo_id / file_path
    if not target.exists():
        return f"(file not found: {file_path})"
    return target.read_text(errors="ignore")[:max_chars]


def search_code(repo_id: str, query: str, top_k: int = 5) -> list[dict]:

    query_Vector = embed_text(query)
    return search_chunks(repo_id, query_Vector, top_k=top_k)