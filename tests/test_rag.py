import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from rag.chain import ask
from rag.config import get_settings
from rag.errors import ConfigurationError, Conflict, InvalidInput, TopicNotFound
from rag.ingest import ingest_pdf_bytes
from rag.loader import load_pdf
from rag.retriever import retrieve
from rag.topics import create_topic, require_topic, validate_topic
from rag.vectorstore import get_collection, topic_stats
from conftest import make_pdf


def test_topics_and_windows_path_validation():
    result = create_topic("Trí tuệ nhân tạo")
    assert result["id"] == "tri-tue-nhan-tao"
    assert result["name"] == "Trí tuệ nhân tạo"
    assert all(path.is_dir() for path in require_topic(result["id"]))
    with pytest.raises(Conflict):
        create_topic("Tri tue nhan tao")
    for unsafe in ("../x", "C:\\test", "con", "aux", "", "a" * 65):
        with pytest.raises(InvalidInput):
            validate_topic(unsafe)
    with pytest.raises(TopicNotFound):
        require_topic("missing")


def test_real_pdf_ingest_dedup_isolation_and_sources(pdf_bytes, monkeypatch):
    create_topic("Topic A")
    create_topic("Topic B")
    first = ingest_pdf_bytes("topic-a", "a.pdf", pdf_bytes)
    assert first["status"] == "indexed" and first["ocr_pages"] == 0
    count = topic_stats("topic-a")["chunk_count"]
    duplicate = ingest_pdf_bytes("topic-a", "copy.pdf", pdf_bytes)
    assert duplicate["status"] == "skipped" and duplicate["file"] == "a.pdf"
    assert topic_stats("topic-a")["chunk_count"] == count
    assert not (require_topic("topic-a")[0] / "copy.pdf").exists()
    other = ingest_pdf_bytes("topic-b", "b.pdf", pdf_bytes)
    assert other["status"] == "indexed"
    assert {doc.metadata["source"] for doc in retrieve("topic-a", "knowledge")} == {"a.pdf"}
    assert {doc.metadata["source"] for doc in retrieve("topic-b", "knowledge")} == {"b.pdf"}
    received = []

    def respond(prompt):
        received.append(prompt.to_string())
        return AIMessage(content="Tài liệu giải thích RAG [1].")

    monkeypatch.setattr("rag.chain.get_llm", lambda: RunnableLambda(respond))
    response = ask("topic-a", "Tài liệu nói gì?")
    assert response["sources"][0]["file"] == "a.pdf"
    assert response["sources"][0]["page"] == 1
    assert "a.pdf" in received[0] and "b.pdf" not in received[0]
    assert "[1]" in response["answer"]


def test_ingest_rejects_conflicting_filename_and_invalid_content(pdf_bytes):
    create_topic("Data")
    ingest_pdf_bytes("data", "a.pdf", pdf_bytes)
    with pytest.raises(Conflict):
        ingest_pdf_bytes("data", "A.PDF", make_pdf("This is a different document with conflicting contents."))
    for name in ("../evil.pdf", "C:\\evil.pdf", "nul.pdf", "bad.txt", "a:evil.pdf"):
        with pytest.raises(InvalidInput):
            ingest_pdf_bytes("data", name, pdf_bytes)
    with pytest.raises(InvalidInput):
        ingest_pdf_bytes("data", "bad.pdf", b"not a PDF")


def test_ingest_rolls_back_partial_vector_write(pdf_bytes, monkeypatch):
    create_topic("Rollback")
    collection = get_collection("rollback")

    class FailingStore:
        def add_documents(self, documents, ids):
            collection.add(ids=ids[:1], embeddings=[[0.1] * 16],
                           documents=[documents[0].page_content], metadatas=[documents[0].metadata])
            raise RuntimeError("Simulated failure after partial write")

    monkeypatch.setattr("rag.ingest.get_vectorstore", lambda topic: FailingStore())
    with pytest.raises(RuntimeError):
        ingest_pdf_bytes("rollback", "failed.pdf", pdf_bytes)
    assert collection.count() == 0
    folder = require_topic("rollback")[0]
    assert not list(folder.glob("*.pdf")) and not list(folder.glob("*.upload"))


def test_model_change_is_rejected(pdf_bytes, monkeypatch):
    create_topic("Models")
    ingest_pdf_bytes("models", "a.pdf", pdf_bytes)
    monkeypatch.setenv("EMBEDDING_MODEL", "different-model")
    get_settings.cache_clear()
    with pytest.raises(ConfigurationError):
        retrieve("models", "test")


def test_empty_topic_needs_no_llm(monkeypatch):
    create_topic("Empty")
    monkeypatch.setattr("rag.chain.get_llm", lambda: pytest.fail("Must not call LLM"))
    response = ask("empty", "Xin chào")
    assert response["sources"] == []
    with pytest.raises(InvalidInput):
        ask("empty", "   ")


def test_ocr_switch_preserves_page_and_filename(pdf_bytes, tmp_path, monkeypatch):
    path = tmp_path / "sample.pdf"
    path.write_bytes(pdf_bytes)
    calls = []

    def fake_ocr(file, page):
        calls.append(page)
        return "Văn bản OCR tiếng Việt"

    monkeypatch.setattr("rag.loader.ocr_page", fake_ocr)
    direct = load_pdf(path)
    assert calls == [] and direct[0].metadata["ocr"] is False
    forced = load_pdf(path, force_ocr=True)
    assert calls == [1] and forced[0].page_content == "Văn bản OCR tiếng Việt"
    assert forced[0].metadata["page"] == 1
    monkeypatch.setenv("OCR_MIN_TEXT_CHARS", "1000")
    get_settings.cache_clear()
    automatic = load_pdf(path)
    assert calls == [1] and automatic[0].metadata["ocr"] is True  # completed page reused from cache


def test_poppler_render_feeds_ocr_reader(pdf_bytes, tmp_path, monkeypatch):
    import shutil
    from pathlib import Path
    from rag.loader import ocr_page

    poppler = get_settings().resolve_poppler()
    if not (poppler and (Path(poppler) / "pdftoppm.exe").is_file()) and not shutil.which("pdftoppm"):
        pytest.skip("Poppler chưa cài trên máy kiểm thử")
    path = tmp_path / "render.pdf"
    path.write_bytes(pdf_bytes)
    received = []

    class Reader:
        def readtext(self, image, **kwargs):
            received.append(image.shape)
            return ["Văn bản tiếng Việt từ trang render"]

    monkeypatch.setattr("rag.loader.get_ocr_reader", lambda: Reader())
    assert ocr_page(path, 1) == "Văn bản tiếng Việt từ trang render"
    assert received[0][0] > 100 and received[0][1] > 100 and received[0][2] == 3
