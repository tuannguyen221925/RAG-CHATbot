"""Check repaired SQL/vector text and one real answer; never store credentials."""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path

import httpx
import numpy as np
import pdfplumber

from api.db import Database
from rag.vectorstore import get_collection
from rag.workspace import user_scope
from scripts.check_ocr_quality import assess


async def verify_indexes(args):
    db = Database()
    await db.open()
    results = []
    try:
        for address in args.email:
            users = await db.query('SELECT id,email,legacy_workspace FROM users WHERE email=%s', (address,))
            if len(users) != 1:
                raise RuntimeError('Expected one explicitly named account')
            user = users[0]
            rows = await db.query('SELECT id,topic,filename,sha256,page_count,chunks FROM documents WHERE user_id=%s AND status=%s', (user['id'], 'ready'))
            matched = 0
            for source in sorted(args.source.glob('*.pdf')):
                digest = hashlib.sha256(source.read_bytes()).hexdigest()
                owned = [r for r in rows if r['sha256'] == digest]
                if len(owned) != 1:
                    raise RuntimeError(f'Expected exactly one copy of {source.name} in named account')
                row = owned[0]
                with pdfplumber.open(source) as pdf:
                    expected = set(range(1, len(pdf.pages) + 1))
                sql_chunks = row['chunks']
                with user_scope(user):
                    vector = get_collection(row['topic']).get(where={'file_sha256': digest}, include=['documents', 'metadatas', 'embeddings'])
                sql_by_id = {chunk['id']: chunk for chunk in sql_chunks}
                vector_by_id = dict(zip(vector['ids'], zip(vector['documents'], vector['metadatas'])))
                if set(sql_by_id) != set(vector_by_id):
                    raise RuntimeError('SQL/vector chunk IDs do not match')
                if any(vector_by_id[key] != (chunk['text'], chunk['metadata']) for key, chunk in sql_by_id.items()):
                    raise RuntimeError('SQL/vector text or metadata differs')
                for key, embedding in zip(vector['ids'], vector['embeddings']):
                    if not np.allclose(embedding, sql_by_id[key]['embedding'], rtol=1e-5, atol=1e-7):
                        raise RuntimeError('SQL/vector embedding differs')
                pages = {chunk['metadata']['page'] for chunk in sql_chunks}
                if pages != expected or row['page_count'] != len(expected):
                    raise RuntimeError('Persisted index is missing pages')
                ocr = [c for c in sql_chunks if c['metadata'].get('ocr')]
                if any(c['metadata'].get('ocr_engine') != 'paddle' or c['metadata'].get('ocr_version') != 4 for c in ocr):
                    raise RuntimeError('Old OCR data remains in repaired document')
                result = {'email': address, 'file': source.name, 'pages': len(pages), 'chunks': len(sql_chunks), 'sql_vectors_identical': True}
                if source.name == 'ML_Chap1_p2.pdf':
                    text = '\n'.join(c['text'] for c in sql_chunks if c['metadata']['page'] == 9)
                    quality = assess(text)
                    if len(quality['api_matches']) < 16 or len(quality['code_matches']) != 3:
                        raise RuntimeError('Corrected NumPy code was not persisted')
                    result['numpy_page'] = quality
                results.append(result)
                matched += 1
            if matched != 7:
                raise RuntimeError('Expected seven verified PDFs')
        history = await db.query('SELECT conversation_id,role,COUNT(*) AS count FROM messages WHERE conversation_id IN (%s,%s) GROUP BY conversation_id,role',
                                ('de70eeb6c177ea27ea1c4c096debf116', 'f6a23851d4ae07fb2345f462107e8a32'))
        if len(history) != 4:
            raise RuntimeError('Expected historical user/assistant messages to remain')
        return {'indexes': results, 'historical_messages': history}
    finally:
        await db.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--email', action='append', required=True)
    parser.add_argument('--chat-email', required=True)
    parser.add_argument('--topic', required=True)
    parser.add_argument('--url', default='http://127.0.0.1:5173')
    args = parser.parse_args()
    password = os.environ.pop('BIGRAG_TEST_PASSWORD')
    report = asyncio.run(verify_indexes(args))
    print('SQL and Chroma verified: 14 PDFs, 167 pages per account; old chats retained', flush=True)
    with httpx.Client(base_url=args.url, timeout=240) as client:
        response = client.post('/api/auth/login', json={'email': args.chat_email, 'password': password})
        del password
        response.raise_for_status()
        response = client.post('/api/conversations', json={'topic': args.topic})
        response.raise_for_status()
        cid = response.json()['id']
        response = client.post(f'/api/conversations/{cid}/messages', json={
            'question': 'Theo trang NumPy trong ML_Chap1_p2.pdf, hãy trích chính xác câu lệnh import NumPy và hai ví dụ tạo mảng bằng arange và linspace, gồm cả các tham số số trong tài liệu. Dẫn nguồn trang, chỉ dùng nội dung tài liệu.',
            'answer_language': 'vi'})
        response.raise_for_status()
        answer = response.json()
        report['chat'] = {'conversation_id': cid, **answer}
        report['chat']['literal_check'] = assess(answer['answer'])
        sources = '\n'.join(source['excerpt'] for source in answer['sources'])
        report['chat']['source_literal_check'] = assess(sources)
        report['passed'] = (len(report['chat']['literal_check']['code_matches']) == 3 and
                            len(report['chat']['source_literal_check']['code_matches']) == 3 and
                            any(s['file'] == 'ML_Chap1_p2.pdf' and s['page'] == 9 for s in answer['sources']))
        Path('storage/ocr-quality-live-check.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'passed': report['passed'], 'conversation_id': cid, 'literal_check': report['chat']['literal_check'],
                          'source_literal_check': report['chat']['source_literal_check'], 'answer': answer['answer']}, ensure_ascii=False), flush=True)
        if not report['passed']:
            raise RuntimeError('Live answer/source regression failed; inspect saved report')


if __name__ == '__main__':
    main()
