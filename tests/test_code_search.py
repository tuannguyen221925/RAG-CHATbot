from langchain_core.documents import Document

from rag.code_search import literal_code_candidates, merge_candidates


def test_literal_functions_find_the_code_chunk_instead_of_cover_or_data_types():
    class Collection:
        def get(self, *, where_document, **kwargs):
            clauses = where_document.get('$or', [where_document])
            terms = [clause['$contains'] for clause in clauses]
            docs = [('cover', 'Introduction to Machine Learning in Python', 1),
                    ('import', 'NumPy\n>>> import numpy as np', 9),
                    ('arrays', '>>> d = np.arange(10,25,5)\n>>> np.linspace(0,2,9)', 9),
                    ('types', 'Data Types\nnp.int64\nnp.float32', 9)]
            found = [doc for doc in docs if any(term in doc[1] for term in terms)]
            return {'ids': [d[0] for d in found], 'documents': [d[1] for d in found],
                    'metadatas': [{'source': 'chapter.pdf', 'page': d[2]} for d in found]}
    question = 'Theo chapter.pdf hãy trích câu lệnh import NumPy và ví dụ arange, linspace.'
    selected = literal_code_candidates(Collection(), question)
    assert len(selected) == 2
    text = '\n'.join(document.page_content for document in selected)
    assert 'np.arange(10,25,5)' in text
    assert 'np.linspace(0,2,9)' in text
    assert 'import numpy as np' in text


def test_ordinary_questions_do_not_run_literal_code_search():
    class Collection:
        def get(self, **kwargs):
            raise AssertionError('Unnecessary keyword lookup')
    assert literal_code_candidates(Collection(), 'Tóm tắt chapter.pdf về Machine Learning') == []


def test_merging_code_candidates_keeps_source_page_and_removes_duplicates():
    code = Document(page_content='np.arange(10,25,5)', metadata={'source': 'a.pdf', 'page': 9})
    other = Document(page_content='Data Types', metadata={'source': 'a.pdf', 'page': 9})
    assert merge_candidates([code], [code, other], 2) == [code, other]
