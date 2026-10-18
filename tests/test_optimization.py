import pytest
from langchain_core.documents import Document
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from rag.chain import ask
from rag.chunking import chunk_documents
from rag.config import get_settings
from rag.errors import ConfigurationError, InvalidInput
from rag.model_options import reasoning_options
from rag.prompt import RAG_PROMPT
from rag.reranker import rerank
from rag.token_budget import estimate_prompt, estimate_tokens, pack_context, response_usage


def docs(count=20, text="Một tài liệu về quy trình hỗ trợ khách hàng. " * 200):
    return [Document(page_content=f"Đoạn {index}: {text}",
                     metadata={"source": f"{index}.pdf", "page": index + 1}) for index in range(count)]


def test_model_specific_reasoning_options():
    assert reasoning_options("openai/gpt-oss-120b") == {"reasoning_effort": "low"}
    assert reasoning_options("openai/gpt-oss-20b") == {"reasoning_effort": "low"}
    assert reasoning_options("qwen/qwen3.8-27b") == {"reasoning_effort": "none"}
    assert reasoning_options("another-model") == {}
    assert reasoning_options("openai/gpt-oss-120b", "provider") == {}
    for model, effort in [("openai/gpt-oss-120b", "none"), ("another-model", "low")]:
        with pytest.raises(ConfigurationError):
            reasoning_options(model, effort)


def test_clients_pass_reasoning_to_api(monkeypatch):
    from rag.llm import get_llm
    from rag.translation import get_translation_llm
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("GROQ_MODEL", "openai/gpt-oss-120b")
    get_settings.cache_clear()
    get_llm.cache_clear()
    get_translation_llm.cache_clear()
    try:
        assert get_llm()._default_params["reasoning_effort"] == "low"
        assert get_translation_llm()._default_params["reasoning_effort"] == "none"
    finally:
        get_llm.cache_clear()
        get_translation_llm.cache_clear()


def test_large_context_is_bounded_and_sources_match_prompt():
    candidates = docs()
    prompt, sources, stats = pack_context(candidates, "Quy trình gồm gì?", "Vietnamese")
    settings = get_settings()
    assert 1 <= len(sources) <= 5
    assert stats["context_tokens_estimated"] <= settings.context_token_budget
    assert estimate_prompt(prompt) <= settings.max_input_tokens
    assert stats["trimmed"]
    assert "\ufffd" not in sources[0]["excerpt"]
    assert sources[0]["excerpt"] in candidates[0].page_content
    assert sources[0]["excerpt"] in prompt.to_messages()[1].content
    assert "1.pdf" not in prompt.to_string()


def test_packer_deduplicates_caps_chunks_and_keeps_shorter_evidence():
    candidates = docs(text="Mẫu ngắn.")
    candidates.insert(1, candidates[0])
    prompt, sources, stats = pack_context(candidates, "Nội dung?", "Vietnamese")
    assert len(sources) == get_settings().max_context_chunks
    assert len({source["excerpt"] for source in sources}) == get_settings().max_context_chunks
    assert not stats["trimmed"]
    mixed = [*docs(1, "Ngắn."), *docs(1), *docs(1, "Chứng cứ khác.")]
    _, sources, _ = pack_context(mixed, "Nội dung?", "Vietnamese")
    assert len(sources) == 2 and sources[1]["excerpt"].endswith("Chứng cứ khác.")


def test_overlong_question_fails_before_llm(monkeypatch):
    monkeypatch.setenv("MAX_INPUT_TOKENS", "800")
    monkeypatch.setenv("CONTEXT_TOKEN_BUDGET", "400")
    get_settings.cache_clear()
    with pytest.raises(InvalidInput, match="rút gọn"):
        pack_context(docs(1), "🙂漢字" * 1000, "Vietnamese")


def test_static_prompt_does_not_vary_with_question_context_or_language():
    first = RAG_PROMPT.invoke({"context": "first", "question": "q1", "answer_language": "Vietnamese"})
    second = RAG_PROMPT.invoke({"context": "second", "question": "q2", "answer_language": "English"})
    assert first.to_messages()[0].content == second.to_messages()[0].content


def test_token_chunks_preserve_tail_language_metadata_and_embedding_limit():
    content = "Tiếng Việt 漢字 🙂 quy trình nghiệp vụ. " * 100 + "TAIL_SENTINEL"
    original = Document(page_content=content, metadata={"source": "a.pdf", "page": 7})
    chunks = chunk_documents([original])
    assert len(chunks) > 1
    assert chunks[-1].page_content.endswith("TAIL_SENTINEL")
    assert all(chunk.metadata["page"] == 7 and chunk.metadata["chunk_tokens"] <= 480 for chunk in chunks)
    assert all(chunk.page_content in content for chunk in chunks)
    # Kiểm tra đầy đủ nội dung (bao gồm cuối trang), cho phép whitespace ở ranh giới.
    coverage = set()
    for chunk in chunks:
        start = chunk.metadata["start_index"]
        assert start >= 0
        coverage.update(range(start, start + len(chunk.page_content)))
    assert all(index in coverage for index, char in enumerate(content) if not char.isspace())


def test_local_reranker_reorders_and_removes_duplicates(monkeypatch):
    class FakeRanker:
        def predict(self, pairs, **kwargs):
            assert len(pairs) == 3 and all(pair[0] == "query" for pair in pairs)
            return [0.1, 0.9, 0.3]
    monkeypatch.setattr("rag.reranker.get_reranker", lambda: FakeRanker())
    candidates = docs(3, "Short")
    assert rerank("query", [*candidates, candidates[0]], 2) == [candidates[1], candidates[2]]


def test_reranker_retrieves_twenty_but_sends_at_most_five(monkeypatch):
    from rag.retriever import retrieve
    from rag.topics import create_topic
    create_topic("Candidates")
    monkeypatch.setenv("RERANK_ENABLED", "true")
    monkeypatch.setenv("MAX_CONTEXT_CHUNKS", "5")
    get_settings.cache_clear()
    class Collection:
        def count(self):
            return 30
    class Store:
        def similarity_search(self, question, k):
            assert k == 20
            return docs(k, "Short")
    monkeypatch.setattr("rag.retriever.get_collection", lambda topic: Collection())
    monkeypatch.setattr("rag.retriever.get_vectorstore", lambda topic: Store())
    monkeypatch.setattr("rag.retriever.rerank", lambda question, candidates, k: candidates[:k])
    assert len(retrieve("candidates", "query", 12)) == 5


def test_usage_survives_chain_and_source_budget(monkeypatch):
    monkeypatch.setattr("rag.chain.retrieve", lambda *args: docs(20, "Short"))
    message = AIMessage(content="Trả lời [1]", usage_metadata={
        "input_tokens": 650, "output_tokens": 80, "total_tokens": 730,
        "input_token_details": {"cache_read": 128}, "output_token_details": {"reasoning": 12}},
        response_metadata={"finish_reason": "length"})
    monkeypatch.setattr("rag.chain.get_llm", lambda: RunnableLambda(lambda _: message))
    response = ask("test", "Nội dung?")
    assert len(response["sources"]) == get_settings().max_context_chunks
    assert response["usage"]["total_tokens"] == 730
    assert response["usage"]["cached_input_tokens"] == 128
    assert response["usage"]["reasoning_tokens"] == 12
    assert response["truncated"]
    assert response_usage(AIMessage(content="ok"))["cached_input_tokens"] is None
    raw = AIMessage(content="ok", response_metadata={"token_usage": {
        "prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120,
        "prompt_tokens_details": {"cached_tokens": 50}}})
    assert response_usage(raw)["cached_input_tokens"] == 50
