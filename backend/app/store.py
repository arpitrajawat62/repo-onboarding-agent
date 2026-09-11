import uuid
from typing import Optional, Literal
from datetime import datetime, timezone



RepoStatus = Literal[
    "pending", 
    "cloning", 
    "parsing", 
    "indexing", 
    "ready", 
    "failed",
]



class RepoRecord:
    def __init__(self, repo_url: str):
        self.id: str = str(uuid.uuid4())
        self.repo_url: str = repo_url
        self.status: RepoStatus = "pending"
        self.error: Optional[str] = None
        self.chunk_count: int = 0
        self.created_at: datetime = datetime.now(timezone.utc)

# In-memory storage
_repos: dict[str, RepoRecord] = {}


def create_repo(repo_url: str) -> RepoRecord:

    if not repo_url:
        raise ValueError("Repository URL cannot be empty")
    
    record = RepoRecord(repo_url)
    _repos[record.id] = record
    return record


def get_repo(repo_id: str) -> Optional[RepoRecord]:
    return _repos.get(repo_id)


def update_repo_status(repo_id: str, status: RepoStatus, error: Optional[str] = None) -> None:
    record = _repos.get(repo_id)
    if record is None:
        raise ValueError(f"Repository not found: {repo_id}")
    
    record.status = status
    record.error = error

def set_chunk_count(repo_id: str, count: int) -> None:

    if count < 0:
        raise ValueError("Chunk count cannot be negative")
    
    record = _repos.get(repo_id)

    if record is None:
        raise ValueError(f"Repository not found: {repo_id}")
    
    record.chunk_count = count
        