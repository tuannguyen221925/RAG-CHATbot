import json

import httpx
import pytest
from langchain_core.documents import Document
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from rag.chain import ask
from rag.errors import ConfigurationError, Conflict, InvalidInput, RAGError
from rag.ingest import ingest_prepared
from rag.languages import ocr_codes
from rag.preview import edit_translation, get_preview, prepare_pdf, register_preview
from rag.topics import create_topic, require_topic
from rag.translation import translate_text
from rag.vectorstore import get_collection


def test_translation_prompt_preserves_domain_and_terminology(monkeypatch):
    prompts = []

    def translate(prompt):
        prompts.append(prompt.to_string())
        return AIMessage(content="Truy xuất có 12 bước, không phải 10 bước.",
                         response_metadata={"finish_reason": "stop"})

    monkeypatch.setattr("rag.translation.get_translation_llm", lambda: RunnableLambda(translate))
    result = translate_text("Retrieval has 12 steps, not 10.", "vi", source_language="en",
                            domain="Computer science", glossary="retrieval = truy xuất")
    assert "12" in result and "10" in result
    assert "retrieval = truy xuất" in prompts[0] and "Computer science" in prompts[0]
    assert "Tiếng Việt" in prompts[0] and "English" in prompts[0]
    assert len(prompts) == 2 and "DRAFT TRANSLATION" in prompts[1]


def test_translation_validation_chunking_and_failures(monkeypatch):
    received = []

    def echo(text, *args):
        received.append(text)
        return text

    monkeypatch.setattr("rag.translation._groq_translate", echo)
    text = "x" * 5000
    assert translate_text(text, "vi").replace("\n\n", "") == text
    assert len(received) == 3 and all(len(part) <= 1800 for part in received)
    assert translate_text("Hello", "en", source_language="en") == "Hello"
    for target in ("not-a-language", "auto", ""):
        with pytest.raises(InvalidInput):
            translate_text("Hello", target)
    with pytest.raises(InvalidInput):
        translate_text("", "vi")
    with pytest.raises(InvalidInput):
        translate_text("Hello", "vi", provider="google", glossary="hello = xin chào")
    monkeypatch.setattr("rag.translation._groq_translate", lambda *args: "")
    with pytest.raises(RAGError):
        translate_text("Hello", "vi")


def test_reject_truncated_llm_translation(monkeypatch):
    monkeypatch.setattr("rag.translation.get_translation_llm", lambda: RunnableLambda(
        lambda _: AIMessage(content="partial", response_metadata={"finish_reason": "length"})))
    with pytest.raises(RAGError, match="bị cắt"):
        translate_text("Hello", "vi")


def test_google_official_request_and_errors(monkeypatch):
    from rag.config import get_settings

    monkeypatch.setenv("GOOGLE_TRANSLATE_API_KEY", "test-key")
    get_settings.cache_clear()
    calls = []

    def post(url, **kwargs):
        calls.append((url, kwargs))
        return httpx.Response(200, request=httpx.Request("POST", url),
                              json={"data": {"translations": [{"translatedText": "Xin chào &amp; tạm biệt"}]}})

    monkeypatch.setattr("rag.translation.httpx.post", post)
    assert translate_text("Hello & goodbye", "vi", provider="google") == "Xin chào & tạm biệt"
    assert "key=" not in calls[0][0]
    assert calls[0][1]["headers"]["X-Goog-Api-Key"] == "test-key"
    assert "source" not in calls[0][1]["json"]
    translate_text("Hello", "ja", source_language="en", provider="google")
    assert calls[1][1]["json"]["source"] == "en"

    def denied(url, **kwargs):
        return httpx.Response(403, request=httpx.Request("POST", url), json={"error": "denied"})

    monkeypatch.setattr("rag.translation.httpx.post", denied)
    with pytest.raises(RAGError, match="Google Cloud"):
        translate_text("Hello", "vi", provider="google")
    monkeypatch.setenv("GOOGLE_TRANSLATE_API_KEY", "")
    get_settings.cache_clear()
    with pytest.raises(ConfigurationError):
        translate_text("Hello", "vi", provider="google")


def test_preview_edit_import_and_original_pdf_retained(pdf_bytes, monkeypatch):
    create_topic("Preview")
    monkeypatch.setattr("rag.preview.translate_text", lambda *args, **kwargs: "Bản dịch ban đầu 12 bước")
    prepared = prepare_pdf("english.pdf", pdf_bytes, source_language="en", target_language="vi")
    data, vectors = require_topic("preview")
    assert not list(data.glob("*.pdf")) and not (vectors / "chroma.sqlite3").exists()
    prepared = edit_translation(prepared, 1, "Bản dịch đã sửa: truy xuất gồm 12 bước.")
    result = ingest_prepared("preview", prepared, index_mode="translated")
    assert result["index_mode"] == "translated" and result["language"] == "vi"
    assert (data / "english.pdf").read_bytes() == pdf_bytes
    collection = get_collection("preview")
    stored = collection.get(include=["documents", "metadatas"])
    assert "đã sửa" in stored["documents"][0]
    assert stored["metadatas"][0]["translated"] is True
    sidecar = json.loads((data / ".translations" / f"{prepared.digest}.json").read_text(encoding="utf-8"))
    assert "augmented generation" in sidecar["pages"][0]["original"]
    assert "đã sửa" in sidecar["pages"][0]["translation"]
    assert ingest_prepared("preview", prepared, index_mode="translated")["status"] == "skipped"
    with pytest.raises(Conflict):
        ingest_prepared("preview", prepared, index_mode="original")
    with pytest.raises(Conflict):
        ingest_prepared("preview", edit_translation(prepared, 1, "Một bản dịch khác"), index_mode="translated")
    prompts = []

    def llm(prompt):
        prompts.append(prompt.to_string())
        return AIMessage(content="This document has twelve steps [1].")

    monkeypatch.setattr("rag.chain.get_llm", lambda: RunnableLambda(llm))
    answer = ask("preview", "How many steps?", answer_language="en")
    assert "ngôn ngữ: English" in prompts[0]
    assert answer["sources"][0]["translated"] is True


def test_preview_failures_create_no_partial_import(pdf_bytes, monkeypatch):
    create_topic("Safe")
    monkeypatch.setattr("rag.preview.load_pdf", lambda *args, **kwargs: [
        Document(page_content="Page one", metadata={"page": 1, "source": "a.pdf", "ocr": False}),
        Document(page_content="Page two", metadata={"page": 2, "source": "a.pdf", "ocr": False}),
    ])

    def fail(text, *args, **kwargs):
        if "two" in text:
            raise RAGError("translation failed")
        return "Trang một"

    monkeypatch.setattr("rag.preview.translate_text", fail)
    with pytest.raises(RAGError):
        prepare_pdf("a.pdf", pdf_bytes, target_language="vi")
    data, vectors = require_topic("safe")
    assert not list(data.glob("*.pdf")) and not (vectors / "chroma.sqlite3").exists()
    prepared = prepare_pdf("a.pdf", pdf_bytes)
    with pytest.raises(InvalidInput):
        ingest_prepared("safe", prepared, index_mode="translated")


def test_preview_tokens_bound_to_topic_and_expire(pdf_bytes, monkeypatch):
    import rag.preview as preview

    preview._previews.clear()
    prepared = prepare_pdf("a.pdf", pdf_bytes)
    token = register_preview("first", prepared)
    assert get_preview(token, "first") is prepared
    with pytest.raises(InvalidInput, match="chủ đề khác"):
        get_preview(token, "second")
    monkeypatch.setattr(preview, "monotonic", lambda: float("inf"))
    with pytest.raises(InvalidInput, match="hết hạn"):
        get_preview(token, "first")


def test_scan_language_mapping():
    assert ocr_codes("auto") == ("vi", "en")
    assert ocr_codes("ja") == ("ja", "en")
    assert ocr_codes("zh-CN") == ("ch_sim", "en")
    assert ocr_codes("zh-TW") == ("ch_tra", "en")
