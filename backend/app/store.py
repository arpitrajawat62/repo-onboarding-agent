import uuid
from typing import Optional, Literal, Dict
from datetime import datetime



RepoStatus = Literal["pending", "cloning", "parsing", "indexing", "ready", "failed"]



class RepoRecord:
    def __init__(self, repo_url: str):
        self.id: str = str(uuid.uuid4())
        self.repo_url: str = repo_url
        self.status: RepoStatus = "pending"
        self.error: Optional[str] = None
        self.created_at = datetime.utcnow()


_repos: Dict[str, RepoRecord] = {}


def create_repo(repo_url: str) -> RepoRecord:
    record = RepoRecord(repo_url)
    _repos[record.id] = record
    return record


def get_repo(repo_id: str) -> Optional[RepoRecord]:
    return _repos.get(repo_id)


def update_repo_status(repo_id: str, status: RepoStatus, error: Optional[str] = None) -> None:
    record = _repos.get(repo_id)
    if record:
        record.status = status
        record.error = error


