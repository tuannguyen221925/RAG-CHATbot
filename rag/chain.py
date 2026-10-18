from langchain_core.output_parsers import StrOutputParser

from rag.errors import InvalidInput, RAGError
from rag.llm import get_llm
from rag.languages import LANGUAGES, validate_language
from rag.retriever import retrieve
from rag.token_budget import estimate_tokens, pack_context, response_usage


def ask(topic: str, question: str, *, k: int | None = None, answer_language: str = "vi",
        chat_history: list[dict] | None = None) -> dict:
    validate_language(answer_language)
    question = question.strip()
    if not question or len(question) > 4000:
        raise InvalidInput("Câu hỏi phải có từ 1 đến 4000 ký tự.")
    recent, history_parts = chat_history or [], []
    for item in reversed(recent[-8:]):
        line = ("Người dùng" if item["role"] == "user" else "Trợ lý") + ": " + item["content"][:800]
        if estimate_tokens("\n".join([line, *history_parts])) > 600:
            break
        history_parts.insert(0, line)
    previous_question = next((m["content"][:600] for m in reversed(recent) if m["role"] == "user"), "")
    search_question = question + ("\nChủ đề câu hỏi trước: " + previous_question if previous_question else "")
    documents = retrieve(topic, search_question, k)
    if not documents:
        return {"topic": topic, "answer": "Chủ đề chưa có dữ liệu. Hãy import PDF trước khi hỏi đáp."
                if answer_language == "vi" else "This topic has no indexed data. Import a PDF first.",
                "sources": []}
    contextual_question = question
    if history_parts:
        contextual_question = ("LỊCH SỬ GẦN ĐÂY (chỉ để hiểu câu hỏi, không phải nguồn tài liệu; "
                               "không tái sử dụng số nguồn cũ):\n" + "\n".join(history_parts)
                               + "\n\nCÂU HỎI HIỆN TẠI:\n" + question)
    prompt, sources, retrieval = pack_context(documents, contextual_question, LANGUAGES[answer_language])
    message = get_llm().invoke(prompt)
    answer = StrOutputParser().invoke(message).strip()
    if not answer:
        raise RAGError("Model chưa trả về câu trả lời. Thử câu hỏi ngắn hơn hoặc tăng MAX_OUTPUT_TOKENS.")
    return {"topic": topic, "answer": answer, "sources": sources,
            "usage": response_usage(message), "retrieval": retrieval,
            "truncated": message.response_metadata.get("finish_reason") == "length"}
