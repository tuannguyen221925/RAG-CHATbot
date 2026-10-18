import logging
import re
import unicodedata

from langchain_core.documents import Document

from rag.config import get_settings
from rag.errors import InvalidInput
from rag.code_search import literal_code_candidates, merge_candidates
from rag.reranker import rerank
from rag.topics import require_topic, topic_lock
from rag.vectorstore import get_collection, get_vectorstore

logger = logging.getLogger(__name__)


def is_library_overview(question: str) -> bool:
    # History helps follow-up searches, but must not change the current scope.
    question = question.split('\nChủ đề câu hỏi trước:', 1)[0]
    text = unicodedata.normalize('NFKD', question.casefold()).replace('đ', 'd')
    text = ''.join(char for char in text if not unicodedata.combining(char))
    summary = re.search(
        r'\b(?:tom tat|tong quan|noi dung chinh|summari[sz]e|summary|overview)\s+'
        r'(?:(?:ngan gon|nhanh|noi dung chinh|noi dung|cac y chinh|cua|ve|trong|of|the|main content|main concepts|in)\s+)*'
        r'(?:(?:cac|nhung|tat ca|toan bo|all|every|these|my|\d+)\s+)*'
        r'(?:tai lieu|thu vien|files?|pdfs?|documents?|chapters?|cac chuong)\b', text)
    library = re.search(r'\b(tai lieu|thu vien|files?|pdfs?|documents?|chapters?|cac chuong)\b', text)
    all_files = re.search(r'\b(tat ca|toan bo|ca \d+|\d+ files?|all|every)\b', text)
    return bool(library and (summary or all_files))


def _overview_documents(store, question, sources, limit, count):
    # Embed once, then search separately in each file so a large chapter cannot
    # displace every vector from a smaller chapter in a library-wide question.
    vector = store.embeddings.embed_query(question + '\nMain concepts, definitions, topics and learning objectives')
    result = []
    for source in sources[:limit]:
        candidates = store.similarity_search_by_vector(vector, k=min(4, count), filter={'source': source})
        # A title/URL-only slide is poor evidence for a whole chapter.
        substantive = [doc for doc in candidates if len(re.sub(r'\s', '', doc.page_content)) >= 160
                       and not re.search(r'https?://', doc.page_content)]
        if candidates:
            doc = (substantive or candidates)[0]
            result.append(Document(page_content=doc.page_content, metadata={**doc.metadata,
                'retrieval_mode': 'overview', 'library_file_count': len(sources)}))
    return result


def retrieve(topic: str, question: str, k: int | None = None) -> list[Document]:
    require_topic(topic)
    if not question.strip():
        raise InvalidInput("Câu hỏi không được để trống.")
    settings = get_settings()
    requested_k = k
    k = settings.retrieval_k if k is None else k
    if not 1 <= k <= 12:
        raise InvalidInput("Số đoạn truy xuất phải nằm trong khoảng 1–12.")
    k = min(k, settings.max_context_chunks)
    with topic_lock(topic):
        collection = get_collection(topic)
        count = collection.count()
        if not count:
            return []
        current = question.split('\nChủ đề câu hỏi trước:', 1)[0]
        overview = is_library_overview(current)
        sources, focused = [], []
        if overview or '.pdf' in current.casefold():
            metadata = collection.get(include=['metadatas'])['metadatas']
            sources = sorted({item['source'] for item in metadata if item.get('source')})
            focused = [source for source in sources if re.search(r'(?<!\w)' + re.escape(source) + r'(?!\w)', current, re.I)]
        store = get_vectorstore(topic)
        if overview:
            limit = min(requested_k or settings.max_context_chunks, settings.max_context_chunks)
            documents = _overview_documents(store, current, focused or sources, limit, count)
            logger.info('Retrieval topic=%s mode=overview vectors=%s indexed_files=%s selected_files=%s selected_chunks=%s',
                        topic, count, len(sources), len({d.metadata['source'] for d in documents}), len(documents))
            return documents
        where = {'source': {'$in': focused}} if focused else None
        literal = literal_code_candidates(collection, question.strip(), limit=min(2, k), sources=focused)
        if settings.rerank_enabled:
            candidates = store.similarity_search(question.strip(), k=min(max(k, settings.rerank_candidates), count),
                                                **({'filter': where} if where else {}))
        else:
            retriever = store.as_retriever(
                search_type="mmr", search_kwargs={"k": min(k, count), "fetch_k": min(k * 4, count),
                                                  **({'filter': where} if where else {})},
            )
            documents = merge_candidates(literal, retriever.invoke(question.strip()), k)
    if settings.rerank_enabled:
        documents = rerank(question.strip(), merge_candidates(literal, candidates, len(candidates) + len(literal)), k)
    logger.info('Retrieval topic=%s mode=%s vectors=%s selected_files=%s selected_chunks=%s', topic,
                'file' if focused else 'semantic', count, len({d.metadata['source'] for d in documents}), len(documents))
    return documents
