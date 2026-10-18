from fastapi.testclient import TestClient as BaseTestClient

from api.main import app


def TestClient(application):
    return BaseTestClient(application, headers={"Authorization": "Bearer test-service-token", "X-RAG-User": "a" * 32, "X-RAG-Legacy": "1"})


def test_topic_api_and_validation():
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/topics").json() == {"topics": []}
        created = client.post("/topics", json={"name": "Tài liệu"})
        assert created.status_code == 201 and created.json()["id"] == "tai-lieu"
        assert client.post("/topics", json={"name": "Tài liệu"}).status_code == 409
        assert client.post("/topics", json={"name": "../"}).status_code == 400
        assert client.post("/ask", json={"topic": "missing", "question": "Hello"}).status_code == 404
        assert client.post("/ask", json={"topic": "tai-lieu", "question": "Hello", "k": 0}).status_code == 422


def test_api_batch_ingest_and_answer(pdf_bytes, monkeypatch):
    with TestClient(app) as client:
        client.post("/topics", json={"name": "API"})
        response = client.post("/ingest", data={"topic": "api"}, files=[
            ("files", ("a.pdf", pdf_bytes, "application/pdf")),
            ("files", ("broken.pdf", b"invalid", "application/pdf")),
            ("files", ("copy.pdf", pdf_bytes, "application/pdf")),
        ])
        assert response.status_code == 200
        assert [item["status"] for item in response.json()["results"]] == ["indexed", "error", "skipped"]
        from langchain_core.messages import AIMessage
        from langchain_core.runnables import RunnableLambda
        monkeypatch.setattr("rag.chain.get_llm", lambda: RunnableLambda(lambda _: AIMessage(content="RAG [1]")))
        answer = client.post("/ask", json={"topic": "api", "question": "RAG là gì?"})
        assert answer.status_code == 200 and answer.json()["sources"][0]["file"] == "a.pdf"
        assert answer.json()["retrieval"]["sent_chunks"] <= 5
        assert answer.json()["usage"]["total_tokens"] is None
        assert answer.json()["truncated"] is False
        missing = client.post("/ingest", data={"topic": "missing"},
                              files=[("files", ("a.pdf", pdf_bytes, "application/pdf"))])
        assert missing.status_code == 404


def test_api_preview_then_confirm_import(pdf_bytes, monkeypatch):
    monkeypatch.setattr("rag.preview.translate_text", lambda *args, **kwargs: "Bản dịch tiếng Việt đầy đủ")
    with TestClient(app) as client:
        client.post("/topics", json={"name": "Preview API"})
        client.post("/topics", json={"name": "Other"})
        assert "ja" in client.get("/languages").json()["languages"]
        result = client.post("/preview", data={"topic": "preview-api", "target_language": "vi",
                                              "source_language": "en"},
                             files={"file": ("a.pdf", pdf_bytes, "application/pdf")})
        assert result.status_code == 200
        token = result.json()["preview_id"]
        assert result.json()["pages"][0]["translation"] == "Bản dịch tiếng Việt đầy đủ"
        empty = client.post("/ask", json={"topic": "preview-api", "question": "Hello"})
        assert empty.json()["sources"] == []
        wrong_topic = client.post("/ingest", data={"topic": "other", "preview_ids": token, "index_mode": "translated"})
        assert wrong_topic.json()["results"][0]["status"] == "error"
        imported = client.post("/ingest", data={"topic": "preview-api", "preview_ids": token,
                                                "index_mode": "translated"})
        assert imported.status_code == 200 and imported.json()["results"][0]["language"] == "vi"
        assert client.delete(f"/preview/{token}", params={"topic": "preview-api"}).status_code == 400
        assert client.post("/ask", json={"topic": "preview-api", "question": "hi", "answer_language": "xx"}).status_code == 400
        direct = client.post("/ingest", data={"topic": "preview-api", "index_mode": "translated"},
                             files={"files": ("a.pdf", pdf_bytes, "application/pdf")})
        assert direct.status_code == 400


def test_api_translate(monkeypatch):
    monkeypatch.setattr("rag.translation._groq_translate", lambda *args: "Bonjour")
    with TestClient(app) as client:
        result = client.post("/translate", json={"text": "Hello", "target_language": "fr"})
        assert result.status_code == 200 and result.json()["translation"] == "Bonjour"
        assert client.post("/translate", json={"text": "Hello", "target_language": "bad"}).status_code == 400
