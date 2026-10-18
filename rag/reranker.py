"""Reranker đa ngôn ngữ chạy local, chỉ tải model khi bật RERANK_ENABLED."""

import math
from functools import lru_cache
from threading import Lock

from langchain_core.documents import Document

from rag.config import get_settings
from rag.devices import require_device
from rag.errors import ConfigurationError

_lock = Lock()


@lru_cache(maxsize=1)
def get_reranker():
    from sentence_transformers import CrossEncoder
    settings = get_settings()
    return CrossEncoder(settings.rerank_model, device=require_device(settings.rerank_device),
                        max_length=1024, trust_remote_code=False)


def rerank(question: str, documents: list[Document], k: int) -> list[Document]:
    if not documents:
        return []
    unique, seen = [], set()
    for document in documents:
        key = " ".join(document.page_content.split())
        if key not in seen:
            seen.add(key)
            unique.append(document)
    with _lock:
        scores = get_reranker().predict([(question, doc.page_content) for doc in unique],
                                       batch_size=4, show_progress_bar=False)
    if len(scores) != len(unique) or any(not math.isfinite(float(score)) for score in scores):
        raise ConfigurationError("Reranker trả về điểm không hợp lệ.")
    order = sorted(range(len(unique)), key=lambda index: float(scores[index]), reverse=True)
    return [unique[index] for index in order[:k]]
