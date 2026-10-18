"""Copy the legacy local PDF/vector library into MySQL without re-embedding."""
import asyncio
import json
from urllib.parse import urlencode

from api.db import Database
from api.library import sync_library
from api.rag_service import RagService
from api.security import digest, identity


async def main():
    db, rag = Database(), RagService()
    try:
        await db.open()
        owner = await db.query("SELECT value FROM app_settings WHERE name='legacy_owner'")
        if owner and owner[0]['value']:
            print(await sync_library(db, rag, {'id': owner[0]['value'], 'legacy_workspace': True}))
            return
        user = {'id': '0' * 32, 'legacy_workspace': True}
        inventory = await rag(user, '/inventory')
        documents = chunks = 0
        for topic in inventory['topics']:
            await db.query('INSERT INTO legacy_topics(id,name) VALUES (%s,%s) ON DUPLICATE KEY UPDATE name=VALUES(name)', (topic['id'], topic['name']))
            for file in topic['files']:
                content = await rag(user, '/file?' + urlencode({'topic': topic['id'], 'filename': file['filename']}), binary=True)
                if digest(content) != file['sha256']:
                    raise RuntimeError('PDF hash mismatch')
                indexed = await rag(user, '/indexed-document?' + urlencode({'topic': topic['id'], 'sha256': file['sha256']}))
                await db.query('''INSERT INTO legacy_documents(id,topic,filename,sha256,file_blob,page_count,ocr_pages,chunk_count,chunks)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE file_blob=VALUES(file_blob),chunks=VALUES(chunks),
                    chunk_count=VALUES(chunk_count),page_count=VALUES(page_count),ocr_pages=VALUES(ocr_pages)''',
                    (identity(), topic['id'], file['filename'], file['sha256'], content, indexed['page_count'], indexed['ocr_pages'], len(indexed['chunks']), json.dumps(indexed['chunks'])))
                documents += 1
                chunks += len(indexed['chunks'])
        print({'database': 'mysql', 'topics': len(inventory['topics']), 'documents': documents, 'chunks': chunks})
    finally:
        await rag.close()
        await db.close()


if __name__ == '__main__':
    asyncio.run(main())
