from pathlib import Path
import git 


WORKSPACE_DIR = Path(__file__).resolve().parent.parent.parent / "workspace"



def clone_repo(repo_id: str, repo_url: str) -> Path:

    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    local_path = WORKSPACE_DIR / repo_id

    if local_path.exists():
        return local_path

    git.Repo.clone_from(repo_url, local_path, depth=50)
    return local_path



