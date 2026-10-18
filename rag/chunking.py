from functools import lru_cache

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from rag.config import get_settings
from rag.errors import ConfigurationError


@lru_cache(maxsize=2)
def get_chunk_tokenizer(model: str):
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained(model, trust_remote_code=False)


def chunk_documents(documents: list[Document]) -> list[Document]:
    settings = get_settings()
    if settings.chunk_unit == "tokens":
        tokenizer = get_chunk_tokenizer(settings.embedding_model)
        # E5 thêm passage: trước embedding và có special tokens.
        reserved = len(tokenizer.encode("passage: ", add_special_tokens=False)) + tokenizer.num_special_tokens_to_add()
        limit = min(settings.chunk_tokens, tokenizer.model_max_length - reserved - 8)
        if limit < 32 or settings.chunk_overlap_tokens >= limit:
            raise ConfigurationError("CHUNK_OVERLAP_TOKENS quá lớn so với giới hạn tokenizer embedding.")
        def length(text):
            return len(tokenizer.encode(text, add_special_tokens=False))
        overlap = settings.chunk_overlap_tokens
    else:
        limit, overlap, length = settings.chunk_size, settings.chunk_overlap, len
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=limit, chunk_overlap=overlap, length_function=length,
        separators=["\n\n", "\n", ". ", "; ", " ", ""], add_start_index=True,
    )
    chunks = []
    for document in documents:
        previous_start = 0
        for chunk in splitter.split_documents([document]):
            # LangChain suy ra vị trí bằng overlap tính theo ký tự. Trong chế độ
            # token, sửa vị trí -1 bằng tìm lại trên chính trang nguồn.
            if chunk.metadata.get("start_index", -1) < 0:
                chunk.metadata["start_index"] = document.page_content.find(chunk.page_content, previous_start)
            previous_start = max(0, chunk.metadata["start_index"])
            chunks.append(chunk)
    if settings.chunk_unit == "tokens":
        # BPE/SentencePiece không cộng tính: encode các mảnh ghép có thể dài hơn
        # tổng encode từng mảnh. Chia thêm thay vì để embedding cắt mất phần cuối.
        bounded = []
        for chunk in chunks:
            text, offset = chunk.page_content, 0
            while text:
                low, high = 1, len(text)
                if length(text) <= limit:
                    low = high
                else:
                    while low < high:
                        middle = (low + high + 1) // 2
                        if length(text[:middle]) <= limit:
                            low = middle
                        else:
                            high = middle - 1
                part = text[:low]
                if length(part) > limit or len(tokenizer.encode("passage: " + part)) > tokenizer.model_max_length:
                    raise ConfigurationError("Không thể chia văn bản trong giới hạn tokenizer embedding.")
                metadata = {**chunk.metadata, "chunk_tokens": length(part), "chunk_unit": "tokens"}
                if metadata.get("start_index", -1) >= 0:
                    metadata["start_index"] += offset
                bounded.append(Document(page_content=part, metadata=metadata))
                text, offset = text[low:], offset + low
        return bounded
    return chunks
