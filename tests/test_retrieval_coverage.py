import pytest
from langchain_core.documents import Document

from rag.config import get_settings
from rag.retriever import is_library_overview, retrieve
from rag.token_budget import estimate_prompt, pack_context
from rag.topics import create_topic
from rag.vectorstore import get_vectorstore


@pytest.mark.parametrize('question,expected', [
    ('Tóm tắt nội dung chính của tài liệu', True),
    ('Tổng quan tất cả 7 file PDF', True),
    ('Summarize all documents in the library', True),
    ('So sánh nội dung toàn bộ tài liệu', True),
    ('Precision và recall khác nhau thế nào?', False),
    ('Tóm tắt thuật toán K-means trong tài liệu', False),
    ('np.arange sử dụng thế nào?\nChủ đề câu hỏi trước: Tóm tắt tất cả tài liệu', False),
])
def test_current_question_controls_overview_scope(question, expected):
    assert is_library_overview(question) is expected


def seven_file_library():
    create_topic('Seven')
    store = get_vectorstore('seven')
    documents = []
    for index in range(7):
        # One large file has many more vectors; each small file must still be represented.
        for page in range(1, 17 if index == 0 else 3):
            documents.append(Document(page_content=f'Chapter {index} page {page}. ' + 'Main concepts and definitions. ' * 25,
                                      metadata={'source': f'chapter-{index}.pdf', 'page': page}))
    store.add_documents(documents)
    return {f'chapter-{index}.pdf' for index in range(7)}


def test_seven_file_overview_survives_retrieval_and_token_budget(monkeypatch):
    monkeypatch.setenv('MAX_CONTEXT_CHUNKS', '12')
    monkeypatch.setenv('CONTEXT_TOKEN_BUDGET', '1800')
    get_settings.cache_clear()
    expected = seven_file_library()
    documents = retrieve('seven', 'Tóm tắt nội dung chính của tài liệu')
    assert len(documents) == 7 and {doc.metadata['source'] for doc in documents} == expected
    # Stress the actual packer with seven long pieces, preserving every source.
    for doc in documents:
        doc.page_content *= 10
    prompt, sources, stats = pack_context(documents, 'Tóm tắt nội dung chính của tài liệu', 'Vietnamese')
    assert {source['file'] for source in sources} == expected
    assert stats['file_coverage_complete'] and stats['sent_files'] == 7 and stats['trimmed']
    assert stats['context_tokens_estimated'] <= 1800
    assert estimate_prompt(prompt) <= get_settings().max_input_tokens
    assert all(source['excerpt'] in prompt.to_string() for source in sources)


def test_filename_scope_applies_to_semantic_and_literal_code_search():
    seven_file_library()
    store = get_vectorstore('seven')
    store.add_documents([Document(page_content='import numpy as np; np.arange(10,25,5)',
                                  metadata={'source': source, 'page': 9}) for source in ('chapter-0.pdf', 'chapter-6.pdf')])
    documents = retrieve('seven', 'Trong file chapter-6.pdf, trích lệnh import numpy và np.arange.')
    assert documents and {doc.metadata['source'] for doc in documents} == {'chapter-6.pdf'}
    assert any('np.arange(10,25,5)' in doc.page_content for doc in documents)


def test_small_configured_limit_reports_incomplete_overview(monkeypatch):
    monkeypatch.setenv('MAX_CONTEXT_CHUNKS', '3')
    get_settings.cache_clear()
    seven_file_library()
    documents = retrieve('seven', 'Tóm tắt tất cả tài liệu')
    _, sources, stats = pack_context(documents, 'Tóm tắt tất cả tài liệu', 'Vietnamese')
    assert len(sources) == 3
    assert stats['available_files'] == 7 and not stats['file_coverage_complete']
