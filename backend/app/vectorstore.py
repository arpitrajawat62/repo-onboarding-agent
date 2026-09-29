from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels


from app.config import settings



COLLECTION_NAME = "repo_chunks"
VECTOR_SIZE = 384



def get_client() -> QdrantClient:
    return QdrantClient(url=settings.qdrant_url)


def ensure_collection() -> None:
    client = get_client()
    existing = [c.name for c in client.get_collections().collections]

    if COLLECTION_NAME not in existing:
        client.create_collection(
           collection_name=COLLECTION_NAME,
           vectors_config=qmodels.VectorParams(
                size=VECTOR_SIZE,
                distance = qmodels.Distance.COSINE,
           ),
        )

def upsert_chunks(points: list[qmodels.PointStruct]) -> None:
    client = get_client()
    ensure_collection()
    client.upsert(collection_name=COLLECTION_NAME, points=points)
    

def search_chunks(repo_id: str, query_vector: list[float], top_k: int = 5) -> list[dict]:

    client = get_client()
    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        query_filter=qmodels.Filter(
            must=[qmodels.FieldCondition(key="repo_id", match=qmodels.MatchValue(value=repo_id))]
        ),
        limit = top_k
    ).points

    return [point.payload for point in results]