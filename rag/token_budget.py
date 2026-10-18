"""Ước lượng input và đóng gói context; không gửi toàn bộ kho PDF tới LLM.

o200k_base với dự phòng 20%, không phải tokenizer chính xác của mọi model Groq.
Token thực tế lấy từ usage của nhà cung cấp, không suy ra quota tài khoản từ ước lượng.
"""

import logging
import math
from functools import lru_cache

import tiktoken
from langchain_core.documents import Document

from rag.config import get_settings
from rag.errors import InvalidInput
from rag.prompt import RAG_PROMPT

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_encoding():
    return tiktoken.get_encoding("o200k_base")


def estimate_tokens(text: str) -> int:
    return math.ceil(len(get_encoding().encode(text, disallowed_special=())) * 1.2)


def estimate_prompt(prompt) -> int:
    return 16 + sum(8 + estimate_tokens(message.content) for message in prompt.to_messages())


def _prefix(text: str, budget: int) -> str:
    # Cắt theo ký tự để không làm hỏng UTF-8 khi một chữ gồm nhiều token.
    low, high = 0, len(text)
    while low < high:
        middle = (low + high + 1) // 2
        if estimate_tokens(text[:middle]) <= budget:
            low = middle
        else:
            high = middle - 1
    return text[:low].rstrip()


def pack_context(documents: list[Document], question: str, answer_language: str):
    settings = get_settings()
    def prompt(context):
        return RAG_PROMPT.invoke({"context": context, "question": question,
                                  "answer_language": answer_language})
    empty_tokens = estimate_prompt(prompt(""))
    if empty_tokens + 64 >= settings.max_input_tokens:
        raise InvalidInput("Câu hỏi quá dài so với giới hạn token. Hãy rút gọn câu hỏi.")
    budget = min(settings.context_token_budget, settings.max_input_tokens - empty_tokens - 32)
    overview = any(doc.metadata.get('retrieval_mode') == 'overview' for doc in documents)
    overview_allowance = None
    if overview:
        eligible = documents[:settings.max_context_chunks]
        headers = '\n\n'.join(f"[{index}] File: {doc.metadata['source']} | Trang: {doc.metadata['page']}\n"
                                for index, doc in enumerate(eligible, 1))
        # Reserve room for every filename/page header, then share the remaining
        # budget. A long first chapter must not consume all space for later files.
        overview_allowance = max(0, (budget - estimate_tokens(headers) - 32) // max(1, len(eligible)))
    sources, parts, seen = [], [], set()
    trimmed = False
    for document in documents:
        if len(sources) >= settings.max_context_chunks:
            break
        content_key = " ".join(document.page_content.split())
        key = (document.metadata['source'], content_key) if overview else content_key
        if not content_key or key in seen:
            continue
        seen.add(key)
        index = len(sources) + 1
        header = f"[{index}] File: {document.metadata['source']} | Trang: {document.metadata['page']}\n"
        text = document.page_content
        if overview:
            text = _prefix(text, overview_allowance)
            trimmed = trimmed or text != document.page_content
        candidate = "\n\n".join([*parts, header + text])
        if estimate_tokens(candidate) > budget or estimate_prompt(prompt(candidate)) > settings.max_input_tokens:
            if sources:
                continue  # Ưu tiên đoạn nguyên vẹn, có thể nhận đoạn ngắn hơn phía sau.
            text = _prefix(text, budget - estimate_tokens(header) - 16)
            candidate = header + text
            while text and (estimate_tokens(candidate) > budget or
                            estimate_prompt(prompt(candidate)) > settings.max_input_tokens):
                text = text[:-16].rstrip()
                candidate = header + text
            trimmed = True
        if not text:
            continue
        sources.append({"id": index, "file": document.metadata["source"],
                        "page": document.metadata["page"], "excerpt": text,
                        "language": document.metadata.get("language", "auto"),
                        "translated": document.metadata.get("translated", False)})
        parts.append(header + text)
    if not sources:
        raise InvalidInput("Không đủ ngân sách token cho trích đoạn tài liệu. Tăng giới hạn hoặc rút gọn câu hỏi.")
    context = "\n\n".join(parts)
    packed_prompt = prompt(context)
    selected_files = {doc.metadata['source'] for doc in documents}
    sent_files = {source['file'] for source in sources}
    available_files = max((doc.metadata.get('library_file_count', len(selected_files)) for doc in documents), default=0)
    stats = {
        "selected_chunks": len(documents), "sent_chunks": len(sources),
        "context_tokens_estimated": estimate_tokens(context),
        "input_tokens_estimated": estimate_prompt(packed_prompt),
        "context_token_budget": settings.context_token_budget,
        "max_input_tokens": settings.max_input_tokens, "trimmed": trimmed,
        "token_estimator": "o200k_base + 20% (estimate)",
        "rerank_enabled": settings.rerank_enabled,
        "mode": 'overview' if overview else 'semantic',
        "selected_files": len(selected_files), "sent_files": len(sent_files),
        "available_files": available_files if overview else None,
        "file_coverage_complete": len(sent_files) == available_files if overview else None,
        "omitted_files": sorted(selected_files - sent_files),
    }
    logger.info('Context mode=%s selected_files=%s sent_files=%s sent_chunks=%s estimated_tokens=%s coverage_complete=%s',
                stats['mode'], len(selected_files), len(sent_files), len(sources), stats['context_tokens_estimated'],
                stats['file_coverage_complete'])
    return packed_prompt, sources, stats


def response_usage(message) -> dict:
    """Giữ None khi provider không báo số liệu; không nhận cache hit giả bằng 0."""
    normalized = message.usage_metadata or {}
    raw = message.response_metadata.get("token_usage") or {}
    inputs = normalized.get("input_token_details") or raw.get("prompt_tokens_details") or {}
    outputs = normalized.get("output_token_details") or raw.get("completion_tokens_details") or {}
    return {"input_tokens": normalized.get("input_tokens", raw.get("prompt_tokens")),
            "output_tokens": normalized.get("output_tokens", raw.get("completion_tokens")),
            "total_tokens": normalized.get("total_tokens", raw.get("total_tokens")),
            "cached_input_tokens": inputs.get("cache_read", inputs.get("cached_tokens")),
            "reasoning_tokens": outputs.get("reasoning", outputs.get("reasoning_tokens"))}
