import uuid
from typing import List

from sentence_transformers import SentenceTransformer
from qdrant_client.http import models as qmodel

from app.ingestion.parser import CodeChunk
from app.vectorstore import upsert_chunks


_model = SentenceTransformer("all-MiniLM-L6-v2")


def index_chunks(repo_id: str, chunks: List[CodeChunk]) -> int:

    if not chunks:
        return 0

    texts = [chunk.content for chunk in chunks]
    vectors = _model.encode(texts).tolist()

    points = [
        qmodel.PointStruct(
            id=str(uuid.uuid4()),
            vector=vector,
            payload={
                "repo_id": repo_id,
                "file_path": chunk.file_path,
                "content": chunk.content,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
            },
        )
        for chunk, vector in zip(chunks, vectors)
    ]

    upsert_chunks(points)
    return len(points)