"""Chỉ tải model khi ingest/retrieve, không tải khi khởi động UI/API."""

from functools import lru_cache
from threading import Lock

from langchain_core.embeddings import Embeddings

from rag.config import get_settings
from rag.devices import require_device

_model_lock = Lock()


@lru_cache(maxsize=1)
def _load_model():
    from langchain_huggingface import HuggingFaceEmbeddings

    settings = get_settings()
    # E5 yêu cầu prefix cho cả tiếng Việt và tiếng Anh.
    is_e5 = "e5" in settings.embedding_model.lower()
    return HuggingFaceEmbeddings(
        model_name=settings.embedding_model,
        model_kwargs={"device": require_device(settings.embedding_device)},
        encode_kwargs={"normalize_embeddings": True, "batch_size": settings.embedding_batch_size,
                       **({"prompt": "passage: "} if is_e5 else {})},
        query_encode_kwargs={"normalize_embeddings": True,
                             **({"prompt": "query: "} if is_e5 else {})},
    )


class LocalEmbeddings(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        with _model_lock:
            return _load_model().embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        with _model_lock:
            return _load_model().embed_query(text)


@lru_cache(maxsize=1)
def get_embeddings() -> Embeddings:
    return LocalEmbeddings()
