import pytest

from rag.errors import Conflict, InvalidInput, TopicNotFound
from rag.ingest import ingest_pdf_bytes
from rag.preview import prepare_pdf, register_preview, get_preview, delete_preview
from rag.topics import create_topic, delete_topic, list_topics, require_topic
from rag.vectorstore import topic_stats
from rag.workspace import user_scope


def test_two_users_have_private_documents_even_with_same_topic(pdf_bytes):
    create_topic("ML")
    ingest_pdf_bytes("ml", "old.pdf", pdf_bytes)
    alice = {"id": "a" * 32, "legacy_workspace": True}
    bob = {"id": "b" * 32, "legacy_workspace": False}
    with user_scope(alice):
        assert list_topics()[0]["pdf_count"] == 1
        alice_path = require_topic("ml")[0]
    with user_scope(bob):
        assert list_topics() == []
        with pytest.raises(TopicNotFound):
            require_topic("ml")
        create_topic("ML")
        ingest_pdf_bytes("ml", "bob.pdf", pdf_bytes)
        assert topic_stats("ml")["pdf_count"] == 1
        assert require_topic("ml")[0] != alice_path
        assert not (require_topic("ml")[0] / "old.pdf").exists()
    with user_scope(alice):
        assert not (require_topic("ml")[0] / "bob.pdf").exists()


def test_preview_cannot_be_reused_by_other_account(pdf_bytes):
    alice = {"id": "a" * 32, "legacy_workspace": True}
    bob = {"id": "b" * 32, "legacy_workspace": False}
    with user_scope(alice):
        token = register_preview("ml", prepare_pdf("a.pdf", pdf_bytes))
    with user_scope(bob):
        with pytest.raises(InvalidInput):
            get_preview(token, "ml")
        with pytest.raises(InvalidInput):
            delete_preview(token, "ml", missing_ok=True)
    with user_scope(alice):
        assert get_preview(token, "ml").filename == "a.pdf"
        delete_preview(token, "ml")


def test_delete_library_is_private_and_recreation_has_no_old_vectors(pdf_bytes):
    alice = {"id": "a" * 32, "legacy_workspace": True}
    bob = {"id": "b" * 32, "legacy_workspace": False}
    with user_scope(alice):
        create_topic("ML")
        create_topic("Keep")
        ingest_pdf_bytes("ml", "alice.pdf", pdf_bytes)
        folder = require_topic("ml")[0]
        token = register_preview("ml", prepare_pdf("preview.pdf", pdf_bytes))
    with user_scope(bob):
        create_topic("ML")
        ingest_pdf_bytes("ml", "bob.pdf", pdf_bytes)
    with user_scope(alice):
        assert delete_topic("ml") == {"status": "deleted"}
        assert not folder.exists()
        assert [t["id"] for t in list_topics()] == ["keep"]
        with pytest.raises(InvalidInput):
            get_preview(token, "ml")
        delete_topic("ml")  # Retry after an interrupted SQL delete is safe.
        create_topic("ML")
        assert topic_stats("ml") == {"pdf_count": 0, "chunk_count": 0}
        with pytest.raises(InvalidInput):
            delete_topic("../keep")
    with user_scope(bob):
        assert topic_stats("ml")["pdf_count"] == 1
        assert topic_stats("ml")["chunk_count"] > 0


def test_followup_uses_bounded_history_and_current_sources(monkeypatch):
    from langchain_core.documents import Document
    from langchain_core.messages import AIMessage
    from langchain_core.runnables import RunnableLambda
    from rag.chain import ask
    captured = []
    searches = []
    def retrieve(topic, question, k):
        searches.append(question)
        return [Document(page_content="K-means uses centroids.", metadata={"source": "current.pdf", "page": 1})]
    monkeypatch.setattr("rag.chain.retrieve", retrieve)
    def answer(prompt):
        captured.append(prompt.to_string())
        return AIMessage(content="Answer [1]")
    monkeypatch.setattr("rag.chain.get_llm", lambda: RunnableLambda(answer))
    response = ask("ml", "How does it work?", chat_history=[
        {"role": "user", "content": "Explain K-means"}, {"role": "assistant", "content": "old answer [9]"}])
    assert "Explain K-means" in searches[0] and "LỊCH SỬ GẦN ĐÂY" in captured[0]
    assert response["sources"][0]["file"] == "current.pdf"
    assert response["retrieval"]["input_tokens_estimated"] <= response["retrieval"]["max_input_tokens"]
