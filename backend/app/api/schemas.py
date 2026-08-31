from pydantic import BaseModel



class CreateRepoRequest(BaseModel):
    repo_url: str


class CreateRepoResponse(BaseModel):
    repo_id: str
    status: str


class RepoStatusResponse(BaseModel):
    repo_id: str
    repo_url: str
    status: str
    error: str | None = None