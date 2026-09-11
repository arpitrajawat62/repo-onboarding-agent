from fastapi import FastAPI

from app.config import Settings
from app.api.routes_repo import router as repo_router



app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok", "app": Settings.app_name}



app.include_router(repo_router)