"""Find literal API names alongside semantic search for questions about code."""
import math
import re
from collections import Counter

from langchain_core.documents import Document

_WORDS = re.compile(r'\b[A-Za-z_][A-Za-z_0-9]*(?:\.[A-Za-z_][A-Za-z_0-9]*)*\b')
_STOP = {'theo', 'trang', 'trong', 'code', 'this', 'that', 'these', 'which', 'what',
         'with', 'from', 'have', 'does', 'please', 'only', 'them', 'function'}


def literal_code_candidates(collection, question, limit=2, sources=None):
    # Ordinary questions keep the existing semantic search. A PDF extension is not an API.
    words = list(dict.fromkeys(_WORDS.findall(question)))
    dotted = [word for word in words if '.' in word and not word.lower().endswith('.pdf')]
    if not dotted and not re.search(r'\b(?:hàm|lệnh|function|code|import)\b', question, re.I):
        return []
    words = [word for word in words if len(word) >= 4 and word.lower() not in _STOP
             and not word.lower().endswith('.pdf')][-12:]
    candidates = {}
    for word in words:
        variants = list(dict.fromkeys([word, word.lower()]))
        clauses = [{'$contains': variant} for variant in variants]
        found = collection.get(where_document=clauses[0] if len(clauses) == 1 else {'$or': clauses},
                               include=['documents', 'metadatas'], limit=64,
                               **({'where': {'source': {'$in': sources}}} if sources else {}))
        for identity, text, metadata in zip(found['ids'], found['documents'], found['metadatas']):
            candidates[identity] = Document(page_content=text, metadata=metadata)
    if not candidates:
        return []
    terms = list(dict.fromkeys(word.lower() for word in words))
    matched = {key: {term for term in terms if re.search(r'\b' + re.escape(term) + r'\b', doc.page_content, re.I)}
               for key, doc in candidates.items()}
    frequency = Counter(term for terms_in_doc in matched.values() for term in terms_in_doc)
    def score(key):
        value = sum(math.log(1 + len(candidates) / frequency[term]) for term in matched[key])
        source = candidates[key].metadata.get('source', '')
        if source and source.casefold() in question.casefold():
            value *= 2
        return value
    ranked = sorted(candidates, key=score, reverse=True)
    return [candidates[key] for key in ranked[:limit] if score(key) > 0]


def merge_candidates(first, second, limit):
    result, seen = [], set()
    for document in [*first, *second]:
        key = (document.metadata.get('source'), document.metadata.get('page'), document.page_content)
        if key not in seen:
            result.append(document)
            seen.add(key)
        if len(result) >= limit:
            break
    return result
