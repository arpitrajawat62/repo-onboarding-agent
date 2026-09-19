from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels


from app.config import Settings



COLLECTION_NAME = "repo_chunks"
VECTOR_SIZE = 384



def get_client() -> QdrantClient:
    return QdrantClient(url=Settings.qdrant_url)


def ensure_collection() -> None:
    client = get_client()
    existing = [c.name for c in client.get_collections().collections]

    if COLLECTION_NAME not in existing:
        client.create_collection(
           collection_name=COLLECTION_NAME,
           vector_config=qmodels.VectorParams(
                SIZE=VECTOR_SIZE,
                distance = qmodels.Distance.COSINE,
           ),
        )

def upsert_chunks(points: list[qmodels.PointStruct]) -> None:
    client = get_client()
    ensure_collection()
    client.upsert(collection_name=COLLECTION_NAME, points=points)
    
