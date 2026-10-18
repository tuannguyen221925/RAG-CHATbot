"""Read-only SQL/vector audit plus real local retrieval on every PDF in a library."""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path

import numpy as np

from api.db import Database
from rag.retriever import retrieve
from rag.token_budget import pack_context
from rag.vectorstore import get_collection
from rag.workspace import user_scope


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--user-id', required=True)
    parser.add_argument('--topic', required=True)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--output', type=Path, default=Path('storage/retrieval-coverage.json'))
    args = parser.parse_args()
    db = Database()
    await db.open()
    try:
        users = await db.query('SELECT id,legacy_workspace FROM users WHERE id=%s', (args.user_id,))
        if len(users) != 1:
            raise RuntimeError('Expected one existing account')
        rows = await db.query('SELECT filename,sha256,status,page_count,chunk_count,chunks FROM documents WHERE user_id=%s AND topic=%s',
                              (args.user_id, args.topic))
    finally:
        await db.close()
    report = {'topic': args.topic, 'files': [], 'queries': []}
    with user_scope(users[0]):
        collection = get_collection(args.topic)
        vectors = collection.get(include=['documents', 'metadatas', 'embeddings'])
        by_id = {key: (text, metadata, vector) for key, text, metadata, vector in
                 zip(vectors['ids'], vectors['documents'], vectors['metadatas'], vectors['embeddings'])}
        for row in sorted(rows, key=lambda row: row['filename']):
            chunks = row['chunks'] or []
            actual_ids = {key for key, value in by_id.items() if value[1].get('file_sha256') == row['sha256']}
            pages = {by_id[key][1]['page'] for key in actual_ids}
            identical = actual_ids == {chunk['id'] for chunk in chunks} and all(
                by_id[chunk['id']][:2] == (chunk['text'], chunk['metadata']) and
                np.allclose(by_id[chunk['id']][2], chunk['embedding'], rtol=1e-5, atol=1e-7) for chunk in chunks)
            source = args.source / row['filename'] if args.source else None
            item = {'file': row['filename'], 'status': row['status'], 'pages': row['page_count'],
                    'sql_chunks': len(chunks), 'vector_chunks': len(actual_ids), 'sql_vectors_identical': identical,
                    'missing_pages': sorted(set(range(1, row['page_count'] + 1)) - pages),
                    'source_pdf_matches': hashlib.sha256(source.read_bytes()).hexdigest() == row['sha256'] if source else None}
            report['files'].append(item)
            print(json.dumps(item, ensure_ascii=False), flush=True)
        questions = [('overview', 'Tóm tắt nội dung chính của tài liệu')]
        questions += [(row['filename'], f"Trong file {row['filename']}, trình bày các khái niệm chính.") for row in rows]
        for target, question in questions:
            documents = retrieve(args.topic, question)
            _, sources, stats = pack_context(documents, question, 'Vietnamese')
            files = sorted({source['file'] for source in sources})
            passed = set(files) == {row['filename'] for row in rows} if target == 'overview' else files == [target]
            item = {'target': target, 'retrieved_files': sorted({d.metadata['source'] for d in documents}),
                    'sent_files': files, 'passed': passed, 'retrieval': stats}
            report['queries'].append(item)
            print(json.dumps(item, ensure_ascii=False), flush=True)
    report['passed'] = (bool(rows) and all(item['sql_vectors_identical'] and not item['missing_pages'] and
                         item['status'] == 'ready' and item['source_pdf_matches'] is not False for item in report['files']) and
                         all(item['passed'] for item in report['queries']))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Coverage audit passed: {report['passed']}; report: {args.output}", flush=True)
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    asyncio.run(main())
