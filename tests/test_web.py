"""Public API integration tests: real SQL + isolated local RAG/PDF workspaces.

Opt in with BIGRAG_RUN_DB_TESTS=1. Each test creates its own uniquely named
database and drops only that database. Production tables are never modified.
"""
import asyncio
import io
import os
import re
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pymysql
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from starlette.concurrency import run_in_threadpool

from api.db import SCHEMA, connection_options, execute
from api.security import digest
from api.web import COOKIE, create_app


@pytest.fixture
def sql_database(monkeypatch):
    if os.getenv('BIGRAG_RUN_DB_TESTS') != '1':
        pytest.skip('Set BIGRAG_RUN_DB_TESTS=1 to test with an isolated MySQL database')
    name = 'big_rag_tests_' + secrets.token_hex(6)
    assert re.fullmatch(r'big_rag_tests_[a-f0-9]{12}', name)
    options = connection_options(database=False)

    async def prepare():
        connection = await run_in_threadpool(pymysql.connect, **options)
        try:
            await execute(connection, f'CREATE DATABASE `{name}` CHARACTER SET utf8mb4')
            await execute(connection, f'USE `{name}`')
            for sql in SCHEMA:
                await execute(connection, sql)
            await execute(connection, "INSERT INTO app_settings(name,value) VALUES ('legacy_owner',NULL)")
        finally:
            connection.close()

    async def cleanup():
        connection = await run_in_threadpool(pymysql.connect, **options)
        try:
            await execute(connection, f'DROP DATABASE `{name}`')
        finally:
            connection.close()

    asyncio.run(prepare())
    monkeypatch.setenv('MYSQL_DATABASE', name)
    monkeypatch.delenv('PUBLIC_ORIGIN', raising=False)
    monkeypatch.setenv('COOKIE_SECURE', 'false')
    try:
        yield name
    finally:
        asyncio.run(cleanup())


@pytest.fixture
def client(sql_database):
    application = create_app()
    with TestClient(application, base_url='http://testserver') as connection:
        yield connection


def register(client, who='alice', password='safe-password-123'):
    response = client.post('/api/auth/register', json={'name': who.title(), 'email': who + '@example.test', 'password': password})
    assert response.status_code == 201, response.text
    return response


def sql(client, statement, params=()):
    return client.portal.call(client.app.state.db.query, statement, params)


def test_auth_sessions_validation_and_csrf(client):
    health = client.get('/api/health')
    assert health.status_code == 200 and health.json()['backend'] == 'python'
    assert client.get('/api/auth/me').status_code == 401
    response = register(client)
    user = response.json()['user']
    assert user['legacy_workspace'] is True
    cookie = response.headers['set-cookie']
    assert 'HttpOnly' in cookie and 'SameSite=lax' in cookie and 'Max-Age=604800' in cookie
    raw = client.cookies.get(COOKIE)
    stored = sql(client, 'SELECT token_hash,expires_at FROM sessions WHERE user_id=%s', (user['id'],))[0]
    assert stored['token_hash'] == digest(raw)
    hashed = sql(client, 'SELECT password_hash FROM users WHERE id=%s', (user['id'],))[0]['password_hash']
    assert hashed.startswith('$2b$12$') and hashed != 'safe-password-123'
    assert client.get('/api/auth/me').json()['user']['id'] == user['id']
    assert client.post('/api/auth/login', headers={'Origin': 'https://evil.example'}, json={}).status_code == 403
    assert client.post('/api/auth/login', headers={'Origin': 'http://testserver'}, json={'email': 'alice@example.test', 'password': 'safe-password-123'}).status_code == 200
    assert client.post('/api/auth/login', headers={'sec-fetch-site': 'cross-site'}, json={}).status_code == 403
    assert client.post('/api/auth/register', json={'name': 'Dup', 'email': 'ALICE@example.test', 'password': 'safe-password-123'}).status_code == 409
    assert client.post('/api/auth/register', json={'name': 'X', 'email': 'long@example.test', 'password': 'a' * 73}).status_code == 400
    assert client.post('/api/auth/register', content='invalid', headers={'Content-Type': 'application/json'}).status_code == 400
    active_token = client.cookies.get(COOKIE)
    assert client.post('/api/auth/logout').status_code == 200
    assert client.get('/api/auth/me').status_code == 401
    assert not sql(client, 'SELECT token_hash FROM sessions WHERE token_hash=%s', (digest(active_token),))
    login = client.post('/api/auth/login', json={'email': 'alice@example.test', 'password': 'safe-password-123'})
    assert login.status_code == 200
    sql(client, 'UPDATE sessions SET expires_at=%s WHERE token_hash=%s', (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1), digest(client.cookies.get(COOKIE))))
    assert client.get('/api/auth/me').status_code == 401
    for _ in range(5):
        assert client.post('/api/auth/login', json={'email': 'wrong@example.test', 'password': 'wrong-password'}).status_code == 401
    assert client.post('/api/auth/login', json={'email': 'wrong@example.test', 'password': 'wrong-password'}).status_code == 429


def test_library_pdf_vectors_avatars_and_owner_isolation(client, pdf_bytes):
    alice = register(client).json()['user']
    topic = client.post('/api/topics', json={'name': 'Private Library'}).json()['id']
    alice_cookie = client.cookies.get(COOKIE)
    assert client.post('/api/topics', json={'name': 'Private Library'}).status_code == 409
    edited = client.patch(f'/api/topics/{topic}/preferences', json={'bot_name': 'Tutor', 'theme': 'ocean'})
    assert edited.status_code == 200 and edited.json()['bot_name'] == 'Tutor'
    assert client.patch(f'/api/topics/{topic}/preferences', json={'bot_name': 'Tutor', 'theme': 'bad'}).status_code == 400
    imported = client.post('/api/ingest', data={'topic': topic}, files=[('files', ('test.pdf', pdf_bytes, 'application/pdf')), ('files', ('bad.pdf', b'bad', 'application/pdf')), ('files', ('copy.pdf', pdf_bytes, 'application/pdf'))])
    assert imported.status_code == 200, imported.text
    assert [r['status'] for r in imported.json()['results']] == ['indexed', 'error', 'skipped']
    doc = client.get('/api/documents', params={'topic': topic}).json()['documents'][0]
    assert doc['chunk_count'] > 0 and doc['status'] == 'ready'
    saved = sql(client, 'SELECT file_blob,chunks FROM documents WHERE id=%s', (doc['id'],))[0]
    assert saved['file_blob'] == pdf_bytes and saved['chunks'][0]['embedding']
    assert client.get('/api/documents/' + doc['id'] + '/file').content == pdf_bytes
    topics = client.get('/api/topics').json()['topics']
    assert topics[0]['pdf_count'] == 1 and topics[0]['theme'] == 'ocean'
    assert client.put('/api/avatars/profile', json={'preset': 'fox'}).json()['user']['avatar']['preset'] == 'fox'
    assert client.put(f'/api/topics/{topic}/avatar', json={'preset': 'robot'}).status_code == 200
    assert client.put('/api/avatars/profile', json={'preset': 'unknown'}).status_code == 400
    image = io.BytesIO()
    Image.new('RGB', (80, 120), 'red').save(image, format='PNG')
    uploaded = client.post('/api/avatars/profile/image', files={'image': ('avatar.png', image.getvalue(), 'image/png')})
    assert uploaded.status_code == 200, uploaded.text
    avatar_url = uploaded.json()['user']['avatar']['url']
    jpeg = client.get(avatar_url)
    assert jpeg.status_code == 200 and Image.open(io.BytesIO(jpeg.content)).size == (384, 384)
    assert client.post(f'/api/topics/{topic}/avatar/image', files={'image': ('avatar.png', image.getvalue(), 'image/png')}).status_code == 200
    assert client.post('/api/avatars/profile/image', files={'image': ('bad.png', b'bad', 'image/png')}).status_code == 400
    assert client.post('/api/avatars/profile/image', files={'image': ('huge.png', b'x' * (5 * 1024 * 1024 + 1), 'image/png')}).status_code == 400
    bob = register(client, 'bob').json()['user']
    assert not bob['legacy_workspace'] and client.get('/api/topics').json()['topics'] == []
    assert client.get('/api/documents/' + doc['id'] + '/file').status_code == 404
    assert client.delete('/api/documents/' + doc['id']).status_code == 404
    assert client.patch(f'/api/topics/{topic}/preferences', json={'bot_name': 'Hack', 'theme': 'mint'}).status_code == 404
    assert client.get(f'/api/avatars/bot:{topic}/image').status_code == 404
    client.cookies.set(COOKIE, alice_cookie, domain='testserver.local', path='/')
    assert client.get('/api/auth/me').json()['user']['id'] == alice['id']
    assert client.delete('/api/documents/' + doc['id']).status_code == 200
    assert client.get('/api/documents', params={'topic': topic}).json()['documents'] == []


def test_delete_library_cascades_and_preserves_other_libraries(client, pdf_bytes):
    alice = register(client).json()['user']
    topic = client.post('/api/topics', json={'name': 'Delete Me'}).json()['id']
    keep = client.post('/api/topics', json={'name': 'Keep Me'}).json()['id']
    imported = client.post('/api/ingest', data={'topic': topic}, files={'files': ('file.pdf', pdf_bytes, 'application/pdf')})
    assert imported.status_code == 200 and imported.json()['results'][0]['status'] == 'indexed', imported.text
    chat = client.post('/api/conversations', json={'topic': topic}).json()['id']
    sql(client, "INSERT INTO messages(conversation_id,role,content,metadata) VALUES (%s,'user','hello','{}')", (chat,))
    response = client.post('/api/previews', data={'topic': topic}, files={'file': ('preview.pdf', pdf_bytes, 'application/pdf')})
    assert response.status_code == 200, response.text
    assert client.put(f'/api/topics/{topic}/avatar', json={'preset': 'robot'}).status_code == 200
    cookie = client.cookies.get(COOKIE)
    register(client, 'bob')
    assert client.delete(f'/api/topics/{topic}').status_code == 404
    bob_topic = client.post('/api/topics', json={'name': 'Delete Me'}).json()['id']
    client.cookies.set(COOKIE, cookie, domain='testserver.local', path='/')
    deleted = client.delete(f'/api/topics/{topic}')
    assert deleted.status_code == 200, deleted.text
    assert [t['id'] for t in client.get('/api/topics').json()['topics']] == [keep]
    for table, field in [('topics', 'id'), ('documents', 'topic'), ('previews', 'topic'), ('conversations', 'topic')]:
        assert sql(client, f'SELECT * FROM {table} WHERE user_id=%s AND {field}=%s', (alice['id'], topic)) == []
    assert sql(client, 'SELECT * FROM messages WHERE conversation_id=%s', (chat,)) == []
    assert sql(client, 'SELECT * FROM avatars WHERE user_id=%s AND slot=%s', (alice['id'], 'bot:' + topic)) == []
    assert len(sql(client, 'SELECT * FROM topics WHERE id=%s', (bob_topic,))) == 1
    assert client.delete(f'/api/topics/{topic}').status_code == 404
    # Sync and startup restoration must not bring the removed library back.
    assert client.post('/api/library/sync').status_code == 200
    assert [t['id'] for t in client.get('/api/topics').json()['topics']] == [keep]
    assert client.post('/api/topics', json={'name': 'Delete Me'}).status_code == 201
    assert client.get('/api/documents', params={'topic': topic}).json()['documents'] == []


def test_chat_translation_persistence_and_ownership(client, monkeypatch):
    register(client)
    topic = client.post('/api/topics', json={'name': 'Chat'}).json()['id']
    requests = []

    def answer(topic, question, **kwargs):
        requests.append(kwargs)
        return {'answer': 'Python answer [1]', 'sources': [{'file': 'test.pdf', 'page': 1}], 'usage': {'total_tokens': 20}, 'truncated': False}

    monkeypatch.setattr('api.main.ask', answer)
    monkeypatch.setattr('api.main.translate_text', lambda **kwargs: 'Translated text')
    chat = client.post('/api/conversations', json={'topic': topic})
    assert chat.status_code == 201
    cid = chat.json()['id']
    assert chat.json()['created_at'].endswith('+00:00')
    response = client.post(f'/api/conversations/{cid}/messages', json={'question': 'First question'})
    assert response.status_code == 200 and response.json()['conversation_id'] == cid
    saved = client.get(f'/api/conversations/{cid}').json()
    assert saved['title'] == 'First question' and len(saved['messages']) == 2
    assert saved['messages'][1]['sources'][0]['file'] == 'test.pdf'
    client.post(f'/api/conversations/{cid}/messages', json={'question': 'Follow up'})
    assert len(requests[1]['chat_history']) == 2
    assert client.get('/api/conversations', params={'search': 'First', 'topic': topic}).json()['conversations'][0]['id'] == cid
    assert client.patch(f'/api/conversations/{cid}', json={'title': 'Renamed'}).json()['title'] == 'Renamed'
    assert client.post('/api/translate', json={'text': 'Hello', 'target_language': 'vi'}).json()['translation'] == 'Translated text'
    assert len(client.get('/api/languages').json()['languages']) == 19
    alice_cookie = client.cookies.get(COOKIE)
    register(client, 'bob')
    for method in ('get', 'patch', 'delete'):
        response = getattr(client, method)(f'/api/conversations/{cid}', **({'json': {'title': 'Hack'}} if method == 'patch' else {}))
        assert response.status_code == 404
    assert client.post(f'/api/conversations/{cid}/messages', json={'question': 'Hack'}).status_code == 404
    client.cookies.set(COOKIE, alice_cookie, domain='testserver.local', path='/')
    assert client.delete(f'/api/conversations/{cid}').status_code == 200
    assert sql(client, 'SELECT id FROM messages WHERE conversation_id=%s', (cid,)) == []


def test_previews_survive_worker_restart_and_are_private(client, pdf_bytes, monkeypatch):
    monkeypatch.setattr('rag.preview.translate_text', lambda *args, **kwargs: 'A translated page')
    register(client)
    topic = client.post('/api/topics', json={'name': 'Preview'}).json()['id']
    response = client.post('/api/previews', data={'topic': topic, 'target_language': 'vi'}, files={'file': ('preview.pdf', pdf_bytes, 'application/pdf')})
    assert response.status_code == 200, response.text
    preview = response.json()
    pid = preview['id']
    from rag.preview import _previews
    _previews.pop(preview['preview_id'])  # Simulate loss of the worker's RAM cache.
    edited = client.patch(f'/api/previews/{pid}', json={'page': 1, 'text': 'Edited translation'})
    assert edited.status_code == 200 and edited.json()['pages'][0]['translation'] == 'Edited translation'
    assert client.patch(f'/api/previews/{pid}', json={'page': 999, 'text': 'No page'}).status_code == 400
    alice_cookie = client.cookies.get(COOKIE)
    register(client, 'bob')
    assert client.post(f'/api/previews/{pid}/import', json={}).status_code == 404
    assert client.delete(f'/api/previews/{pid}').status_code == 404
    client.cookies.set(COOKIE, alice_cookie, domain='testserver.local', path='/')
    imported = client.post(f'/api/previews/{pid}/import', json={'index_mode': 'translated'})
    assert imported.status_code == 200 and imported.json()['status'] == 'indexed', imported.text
    documents = client.get('/api/documents', params={'topic': topic}).json()['documents']
    assert documents[0]['index_mode'] == 'translated'
    assert client.delete(f'/api/previews/{pid}').status_code == 404
    response = client.post('/api/previews', data={'topic': topic}, files={'file': ('second.pdf', pdf_bytes, 'application/pdf')})
    assert client.delete('/api/previews/' + response.json()['id']).status_code == 200


def test_legacy_data_and_existing_cookie_compatibility(client, pdf_bytes):
    sql(client, "INSERT INTO legacy_topics(id,name) VALUES ('legacy','Legacy')")
    sql(client, 'INSERT INTO legacy_documents(id,topic,filename,sha256,file_blob,page_count,ocr_pages,chunk_count,chunks) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)',
        ('d' * 32, 'legacy', 'old.pdf', digest(pdf_bytes), pdf_bytes, 1, 0, 0, '[]'))
    user = register(client).json()['user']
    assert client.get('/api/documents', params={'topic': 'legacy'}).json()['documents'][0]['filename'] == 'old.pdf'
    assert not sql(client, 'SELECT id FROM legacy_documents')
    token = 'existing-node-cookie-token'
    sql(client, 'INSERT INTO sessions(token_hash,user_id,expires_at) VALUES (%s,%s,%s)', (digest(token), user['id'], datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=1)))
    client.cookies.set(COOKIE, token, domain='testserver.local', path='/')
    assert client.get('/api/auth/me').json()['user']['id'] == user['id']
    register(client, 'bob')
    assert client.get('/api/topics').json()['topics'] == []


def test_concurrent_first_registration_claims_one_owner(client):
    def create(who):
        return client.post('/api/auth/register', json={'name': who, 'email': who + '@example.test', 'password': 'safe-password-123'})

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(create, ['first', 'second']))
    assert all(response.status_code == 201 for response in responses), [r.text for r in responses]
    owners = [response.json()['user'] for response in responses if response.json()['user']['legacy_workspace']]
    assert len(owners) == 1
    assert sql(client, "SELECT value FROM app_settings WHERE name='legacy_owner'")[0]['value'] == owners[0]['id']


def test_schema_health_upload_limits_and_private_worker(client, pdf_bytes, monkeypatch):
    register(client)
    topic = client.post('/api/topics', json={'name': 'Limits'}).json()['id']
    assert client.post('/api/ingest', data={'topic': topic}).status_code == 400
    bad = client.post('/api/ingest', data={'topic': topic}, files={'files': ('../evil.pdf', pdf_bytes, 'application/pdf')})
    assert bad.json()['results'][0]['status'] == 'error'
    assert client.post('/api/auth/login', headers={'Content-Length': str(4 * 1024 * 1024)}, content='{}').status_code == 413
    assert client.post('/api/auth/login', content=iter([b'{"padding":"', b'x' * (3 * 1024 * 1024), b'"}']), headers={'Content-Type': 'application/json'}).status_code == 413
    assert client.get('/inventory').headers.get('content-type', '').startswith('text/html')
    assert client.get('/api/unknown').status_code == 404

    async def missing_schema():
        raise RuntimeError('missing schema')

    monkeypatch.setattr(client.app.state.db, 'check_schema', missing_schema)
    assert client.get('/api/health').status_code == 503
