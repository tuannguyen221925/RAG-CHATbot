"""Rebuild original-text indexes for explicitly named accounts and matching source PDFs.

Keep PDF blobs, document IDs, libraries, conversations and old messages. Back up
the previous chunks and restore vectors if a SQL/vector update fails.
"""
import argparse
import asyncio
import hashlib
import json
import shutil
import time
from pathlib import Path

from api.db import Database, execute
from rag.chunking import chunk_documents
from rag.embedder import get_embeddings
from rag.loader import load_pdf
from rag.topics import topic_lock
from rag.vectorstore import get_collection
from rag.workspace import user_scope


def write_vectors(collection, chunks):
    for start in range(0, len(chunks), 64):
        batch = chunks[start:start+64]
        collection.upsert(ids=[c['id'] for c in batch], documents=[c['text'] for c in batch],
                          metadatas=[c['metadata'] for c in batch], embeddings=[c['embedding'] for c in batch])


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--email', action='append', required=True)
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    folder = Path('storage/ocr-quality-repair')
    folder.mkdir(parents=True, exist_ok=True)
    sources = {hashlib.sha256(path.read_bytes()).hexdigest(): path for path in args.source.glob('*.pdf')}
    if len(sources) != 7:
        raise RuntimeError('Expected exactly seven distinct source PDFs')
    db = Database()
    await db.open()
    report = {'accounts': args.email, 'results': []}
    started = time.monotonic()
    try:
        placeholders = ','.join(['%s'] * len(args.email))
        rows = await db.query(f'''SELECT d.id,d.user_id,d.topic,d.filename,d.sha256,d.chunks,
            d.page_count,d.ocr_pages,d.chunk_count,u.email,u.legacy_workspace
            FROM documents d JOIN users u ON u.id=d.user_id
            WHERE u.email IN ({placeholders}) AND d.status='ready' AND d.index_mode='original' ''', tuple(args.email))
        rows = [row for row in rows if row['sha256'] in sources]
        if not rows:
            raise RuntimeError('No matching documents for the explicitly named accounts')
        for index, (sha, source) in enumerate(sources.items(), 1):
            owners = [row for row in rows if row['sha256'] == sha]
            if not owners:
                continue
            print(f'OCR {index}/7: {source.name}; {len(owners)} copies', flush=True)
            path = folder / source.name
            if not path.exists():
                shutil.copy2(source, path)
            if hashlib.sha256(path.read_bytes()).hexdigest() != sha:
                raise RuntimeError('Input copy does not match original PDF')
            pages = load_pdf(path, source_name=source.name)
            if len(pages) != pages[0].metadata['pdf_total_pages']:
                raise RuntimeError('Refusing to replace index with incomplete page coverage')
            chunks = chunk_documents(pages)
            vectors = get_embeddings().embed_documents([c.page_content for c in chunks])
            for row in owners:
                backup = folder / (row['id'] + '-before.json')
                if not backup.exists():
                    backup.write_text(json.dumps(row, ensure_ascii=False), encoding='utf-8')
                prepared = []
                for i, (chunk, embedding) in enumerate(zip(chunks, vectors)):
                    meta = {**chunk.metadata, 'source': row['filename'], 'topic': row['topic'],
                            'file_sha256': sha, 'chunk_index': i, 'index_signature': 'original',
                            'translated': False, 'language': 'auto'}
                    prepared.append({'id': f'{sha}:{i}', 'text': chunk.page_content,
                                     'metadata': meta, 'embedding': embedding})
                user = {'id': row['user_id'], 'legacy_workspace': bool(row['legacy_workspace'])}
                with user_scope(user), topic_lock(row['topic']):
                    collection = get_collection(row['topic'])
                    existing = collection.get(where={'file_sha256': sha}, include=['documents', 'metadatas', 'embeddings'])
                    previous = [{'id': identity, 'text': text, 'metadata': meta, 'embedding': embedding.tolist()}
                                for identity, text, meta, embedding in zip(existing['ids'], existing['documents'], existing['metadatas'], existing['embeddings'])]
                    new_ids = {c['id'] for c in prepared}
                    old_ids = {c['id'] for c in previous}
                    try:
                        async with db.transaction() as connection:
                            owned = await execute(connection, 'SELECT chunks FROM documents WHERE id=%s AND user_id=%s AND sha256=%s FOR UPDATE',
                                                  (row['id'], row['user_id'], sha))
                            if not owned or owned[0]['chunks'] != row['chunks']:
                                raise RuntimeError('Document changed during repair; retry after current work finishes')
                            write_vectors(collection, prepared)
                            stale = list(old_ids - new_ids)
                            if stale:
                                collection.delete(ids=stale)
                            await execute(connection, 'UPDATE documents SET chunks=%s,chunk_count=%s,page_count=%s,ocr_pages=%s WHERE id=%s AND user_id=%s',
                                          (json.dumps(prepared, ensure_ascii=False), len(prepared), len(pages),
                                           sum(bool(p.metadata['ocr']) for p in pages), row['id'], row['user_id']))
                    except BaseException:
                        write_vectors(collection, previous)
                        added = list(new_ids - old_ids)
                        if added:
                            collection.delete(ids=added)
                        raise
                result = {'email': row['email'], 'topic': row['topic'], 'file': row['filename'],
                          'pages': len(pages), 'chunks_before': row['chunk_count'], 'chunks_after': len(prepared),
                          'ocr_pages': sum(bool(p.metadata['ocr']) for p in pages)}
                report['results'].append(result)
                (folder / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
                print(json.dumps(result, ensure_ascii=False), flush=True)
        report['seconds'] = round(time.monotonic()-started, 2)
        report['passed'] = len(report['results']) == len(rows)
        (folder / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'Updated {len(rows)} documents in {report["seconds"]} seconds', flush=True)
    finally:
        await db.close()


if __name__ == '__main__':
    asyncio.run(main())
