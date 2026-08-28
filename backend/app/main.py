from fastapi import FastAPI

from app.config import Settings



app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok", "app": Settings.app_name}