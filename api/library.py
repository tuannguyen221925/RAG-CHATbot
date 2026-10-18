"""Persist canonical PDF/vector copies and restore the local search cache."""
import json
from urllib.parse import urlencode

from .security import digest, identity


async def store_document(db, rag, user, topic, filename, content, prepared=None, index_mode='original'):
    sha = digest(content)
    indexed = await rag(user, '/indexed-document?' + urlencode({'topic': topic, 'sha256': sha}))
    await db.query('''INSERT INTO documents(id,user_id,topic,filename,sha256,file_blob,page_count,ocr_pages,chunk_count,chunks,prepared,index_mode,status)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON DUPLICATE KEY UPDATE page_count=VALUES(page_count),ocr_pages=VALUES(ocr_pages),chunk_count=VALUES(chunk_count),
        chunks=VALUES(chunks),prepared=COALESCE(VALUES(prepared),prepared),status=VALUES(status)''',
        (identity(), user['id'], topic, filename, sha, content, indexed['page_count'], indexed['ocr_pages'],
         len(indexed['chunks']), json.dumps(indexed['chunks']), json.dumps(prepared) if prepared else None, index_mode, 'ready'))


async def sync_library(db, rag, user):
    inventory = await rag(user, '/inventory')
    count = 0
    for topic in inventory['topics']:
        await db.query('INSERT INTO topics(user_id,id,name) VALUES (%s,%s,%s) ON DUPLICATE KEY UPDATE name=VALUES(name)', (user['id'], topic['id'], topic['name']))
        for file in topic['files']:
            content = await rag(user, '/file?' + urlencode({'topic': topic['id'], 'filename': file['filename']}), binary=True)
            await store_document(db, rag, user, topic['id'], file['filename'], content)
            count += 1
    return {'topics': len(inventory['topics']), 'documents': count}


async def restore_library(db, rag):
    for user in await db.query('SELECT id,legacy_workspace FROM users'):
        topics = await db.query('SELECT id,name FROM topics WHERE user_id=%s', (user['id'],))
        present = {topic['id'] for topic in (await rag(user, '/topics'))['topics']}
        for topic in topics:
            if topic['id'] not in present:
                created = await rag(user, '/topics', method='POST', json={'name': topic['name']})
                if created['id'] != topic['id']:
                    raise RuntimeError('Restored topic ID does not match database')
        documents = await db.query("SELECT topic,filename,file_blob,chunks FROM documents WHERE user_id=%s AND status='ready'", (user['id'],))
        for doc in documents:
            await rag(user, '/restore-index', method='POST', data={'topic': doc['topic'], 'chunks': json.dumps(doc['chunks'])},
                      files={'file': (doc['filename'], doc['file_blob'], 'application/pdf')})
        print(f"Restored {len(documents)} documents for workspace {user['id']}.")
