import hashlib

import pytest
from langchain_core.embeddings import Embeddings

from rag.config import get_settings


class TestEmbeddings(Embeddings):
    """Vector xác định, chỉ dùng để kiểm tra storage/retrieval không tải model."""

    def embed_documents(self, texts):
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text):
        digest = hashlib.sha256(text.encode()).digest()
        return [value / 255 for value in digest[:16]]


class TestTokenizer:
    model_max_length = 512

    def encode(self, text, add_special_tokens=True):
        return list(text) + (["<s>", "</s>"] if add_special_tokens else [])

    def num_special_tokens_to_add(self):
        return 2


@pytest.fixture(autouse=True)
def isolated_project(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("VECTOR_DB_DIR", str(tmp_path / "vectors"))
    monkeypatch.setenv("RAG_SERVICE_TOKEN", "test-service-token")
    monkeypatch.setenv("OCR_MIN_TEXT_CHARS", "1")
    monkeypatch.setenv("EMBEDDING_MODEL", "test-embedding")
    monkeypatch.setenv("EMBEDDING_DEVICE", "cpu")
    monkeypatch.setenv("OCR_GPU", "false")
    monkeypatch.setenv("OCR_ENGINE", "easyocr")
    monkeypatch.setenv("RERANK_DEVICE", "cpu")
    get_settings.cache_clear()
    monkeypatch.setattr("rag.vectorstore.get_embeddings", lambda: TestEmbeddings())
    monkeypatch.setattr("rag.chunking.get_chunk_tokenizer", lambda model: TestTokenizer())
    yield
    get_settings.cache_clear()


def make_pdf(text: str = "A document about retrieval augmented generation and Vietnamese knowledge.") -> bytes:
    """PDF tối thiểu hợp lệ, đọc/render bằng thư viện thật."""
    safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 50 750 Td ({safe}) Tj ET".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = []
    for index, obj in enumerate(objects, 1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets:
        pdf.extend(f"{offset:010d} 00000 n \n".encode())
    pdf.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return bytes(pdf)


@pytest.fixture
def pdf_bytes():
    return make_pdf()
