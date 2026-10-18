from fastapi.testclient import TestClient
from api.main import app

def headers(identity='a', legacy=False):
    return {'Authorization': 'Bearer test-service-token', 'X-RAG-User': identity * 32, 'X-RAG-Legacy': '1' if legacy else '0'}

def test_internal_service_requires_secret_and_private_workspace():
    with TestClient(app) as client:
        assert client.get('/health').status_code == 200
        assert client.get('/topics').status_code == 401
        assert client.get('/topics', headers={'X-RAG-User':'a'*32}).status_code == 401
        assert client.post('/topics', headers=headers(), json={'name':'Private'}).status_code == 201
        assert len(client.get('/topics', headers=headers()).json()['topics']) == 1
        assert client.get('/topics', headers=headers('b')).json()['topics'] == []
        assert client.get('/topics', headers=headers('b', True)).json()['topics'] == []

def test_mysql_saved_preview_import_survives_empty_ram(pdf_bytes):
    import json
    with TestClient(app, headers=headers()) as client:
        client.post('/topics',json={'name':'Saved'})
        saved={'file':'saved.pdf','source_language':'en','target_language':'vi','pages':[{'page':1,'ocr':False,'original':'Original source text','translation':'Bản dịch đã chỉnh sửa trong MySQL'}]}
        result=client.post('/ingest-saved',data={'topic':'saved','prepared':json.dumps(saved),'index_mode':'translated'},files={'file':('saved.pdf',pdf_bytes,'application/pdf')})
        assert result.status_code == 200 and result.json()['language']=='vi'
        import hashlib
        chunks=client.get('/indexed-document',params={'topic':'saved','sha256':hashlib.sha256(pdf_bytes).hexdigest()}).json()['chunks']
        assert chunks[0]['text']=='Bản dịch đã chỉnh sửa trong MySQL'
        assert client.delete('/document',params={'topic':'saved','sha256':hashlib.sha256(pdf_bytes).hexdigest()}).status_code == 200
        imported=client.post('/ingest-saved',data={'topic':'saved','prepared':json.dumps(saved),'index_mode':'translated'},files={'file':('saved.pdf',pdf_bytes,'application/pdf')})
        assert imported.status_code == 200

def test_mysql_vectors_restore_without_embedding(pdf_bytes,monkeypatch):
    import hashlib,json
    with TestClient(app, headers=headers()) as client:
        client.post('/topics',json={'name':'Restored'})
        sha=hashlib.sha256(pdf_bytes).hexdigest()
        chunks=[{'id':sha+':0','text':'Recovered knowledge','metadata':{'file_sha256':sha,'source':'saved.pdf','topic':'restored','page':1,'ocr':False},'embedding':[0.1]*16}]
        monkeypatch.setattr('rag.vectorstore.get_embeddings',lambda: (_ for _ in ()).throw(AssertionError('Restore should use saved vectors')))
        restored=client.post('/restore-index',data={'topic':'restored','chunks':json.dumps(chunks)},files={'file':('saved.pdf',pdf_bytes,'application/pdf')})
        assert restored.status_code == 200
        assert client.get('/file',params={'topic':'restored','filename':'saved.pdf'}).content == pdf_bytes
        assert client.get('/indexed-document',params={'topic':'restored','sha256':sha}).json()['chunks'][0]['text']=='Recovered knowledge'
