"""Mỗi topic là một PersistentClient Chroma trong thư mục riêng."""

from functools import lru_cache

import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_chroma import Chroma

from rag.config import get_settings
from rag.embedder import get_embeddings
from rag.errors import ConfigurationError
from rag.topics import require_topic

COLLECTION = "documents"


@lru_cache(maxsize=32)
def _client(path: str):
    return chromadb.PersistentClient(path=path, settings=ChromaSettings(anonymized_telemetry=False))


def get_collection(topic: str):
    _, folder = require_topic(topic)
    settings = get_settings()
    collection = _client(str(folder)).get_or_create_collection(
        COLLECTION, embedding_function=None,
        metadata={"embedding_model": settings.embedding_model, "hnsw:space": "cosine"},
    )
    saved_model = (collection.metadata or {}).get("embedding_model")
    if saved_model != settings.embedding_model:
        raise ConfigurationError(
            "EMBEDDING_MODEL khác model đã dùng trong chủ đề. "
            "Khôi phục cấu hình cũ hoặc tạo chủ đề mới và import lại PDF."
        )
    return collection


def get_vectorstore(topic: str) -> Chroma:
    get_collection(topic)  # Kiểm tra model trước khi query hoặc ghi.
    _, folder = require_topic(topic)
    return Chroma(client=_client(str(folder)), collection_name=COLLECTION,
                  embedding_function=get_embeddings(), create_collection_if_not_exists=False)


def topic_stats(topic: str) -> dict:
    from rag.topics import topic_lock

    with topic_lock(topic):
        data, _ = require_topic(topic)
        collection = get_collection(topic)
        return {"pdf_count": len(list(data.glob("*.pdf"))), "chunk_count": collection.count()}
