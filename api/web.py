"""Public Python backend for React, accounts, MySQL and the local RAG engine.

Run: python -m scripts.serve --reload
"""
import json
import logging
import os
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlencode

import pymysql
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.exceptions import HTTPException

from . import avatars
from .db import Database, ROOT, execute
from .library import store_document, sync_library
from .rag_service import RagService
from .observability import RequestLogMiddleware, log_directory
from .security import AppError, digest, email, hash_password, identity, label, verify_password
from rag.config import get_settings
from rag.ingest import validate_pdf_name
from rag.errors import RAGError

COOKIE = 'big_rag_session'
THEMES = {'mint', 'blush', 'ocean', 'lavender', 'sunset', 'coffee', 'midnight'}


class SecurityMiddleware:
    """Pure ASGI middleware keeps streamed uploads and context propagation intact."""
    def __init__(self, app, database):
        self.app, self.db = app, database

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        request = Request(scope, receive)

        async def secure_send(message):
            if message['type'] == 'http.response.start':
                headers = list(message.get('headers', []))
                headers.extend([(b'x-content-type-options', b'nosniff'), (b'referrer-policy', b'same-origin'), (b'x-frame-options', b'DENY')])
                if scope['path'].startswith('/api'):
                    headers.append((b'cache-control', b'no-store'))
                message = {**message, 'headers': headers}
            await send(message)

        try:
            if request.method not in ('GET', 'HEAD', 'OPTIONS'):
                expected = os.getenv('PUBLIC_ORIGIN') or f"{request.url.scheme}://{request.headers.get('host')}"
                origin = request.headers.get('origin')
                if (origin and origin != expected) or request.headers.get('sec-fetch-site') == 'cross-site':
                    raise AppError('Nguồn yêu cầu không hợp lệ.', 403)
            if scope['path'].startswith('/api') and scope['path'] not in ('/api/health', '/api/auth/register', '/api/auth/login'):
                token = request.cookies.get(COOKIE)
                if not token or len(token) > 128:
                    raise AppError('Vui lòng đăng nhập.', 401)
                rows = await self.db.query('SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=%s AND s.expires_at>NOW()', (digest(token),))
                if not rows:
                    raise AppError('Phiên đăng nhập đã hết hạn.', 401)
                request.state.user = rows[0]
        except AppError as exc:
            return await JSONResponse({'error': str(exc)}, status_code=exc.status)(scope, receive, secure_send)
        except pymysql.MySQLError as exc:
            logging.exception('Session database request failed: %s', exc.args[0] if exc.args else type(exc).__name__)
            return await JSONResponse({'error': 'Chưa kết nối được MySQL.'}, status_code=503)(scope, receive, secure_send)
        await self.app(scope, receive, secure_send)


class RequestLimit:
    """Bound multipart spooling and JSON bodies, including chunked requests."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or not scope['path'].startswith('/api'):
            return await self.app(scope, receive, send)
        headers = dict(scope['headers'])
        multipart = headers.get(b'content-type', b'').startswith(b'multipart/form-data')
        limit = (76 if multipart else 3) * 1024 * 1024
        try:
            declared = int(headers.get(b'content-length', b'0'))
        except ValueError:
            return await JSONResponse({'error': 'Content-Length không hợp lệ.'}, status_code=400)(scope, receive, send)
        if declared > limit:
            return await JSONResponse({'error': 'Nội dung vượt giới hạn tải lên.'}, status_code=413)(scope, receive, send)
        received = 0

        async def bounded_receive():
            nonlocal received
            message = await receive()
            received += len(message.get('body', b''))
            if received > limit:
                raise AppError('Nội dung vượt giới hạn tải lên.', 413)
            return message

        await self.app(scope, bounded_receive, send)


async def body(request):
    try:
        value = await request.json()
    except (ValueError, UnicodeError) as exc:
        raise AppError('JSON không hợp lệ.') from exc
    if not isinstance(value, dict):
        raise AppError('JSON cần là một object.')
    return value


async def pdf_upload(upload):
    if not upload or not hasattr(upload, 'read'):
        raise AppError('Chọn PDF.')
    content = await upload.read(50 * 1024 * 1024 + 1)
    if len(content) > 50 * 1024 * 1024:
        raise AppError('PDF vượt giới hạn tải lên (50 MB/file).')
    name = upload.filename or ''
    try:
        name = validate_pdf_name(name)
    except RAGError as exc:
        raise AppError('Tên PDF không hợp lệ.') from exc
    if len(name) > 180 or name != name.strip() or b'%PDF-' not in content[:1024]:
        raise AppError('Tên hoặc header PDF không hợp lệ.')
    return name, content


def create_app(database=None, service=None):
    db = database or Database()
    rag = service or RagService()

    @asynccontextmanager
    async def lifespan(app):
        logging.getLogger(__name__).info('Starting Python API; logs: %s (api.log, api-error.log)', log_directory())
        try:
            await db.open()
            await db.check_schema()
            if not get_settings().rag_service_token.get_secret_value():
                raise RuntimeError('Missing RAG_SERVICE_TOKEN; run python -m scripts.setup_mysql')
            app.state.dummy_hash = await hash_password(secrets.token_hex(24))
            yield
        finally:
            await rag.close()
            await db.close()

    app = FastAPI(title='BIG_RAG Python API', version='3.0.0', lifespan=lifespan)
    app.state.db, app.state.rag = db, rag

    @app.exception_handler(AppError)
    async def app_error(request, error):
        logging.warning('API %s %s: %s', request.method, request.url.path, error)
        return JSONResponse({'error': str(error)}, status_code=error.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        return JSONResponse({'error': 'Dữ liệu yêu cầu không hợp lệ.'}, status_code=400)

    @app.exception_handler(HTTPException)
    async def http_error(request, error):
        return JSONResponse({'error': str(error.detail)}, status_code=error.status_code)

    @app.exception_handler(pymysql.MySQLError)
    async def database_error(request, error):
        if error.args and error.args[0] == 1062:
            return JSONResponse({'error': 'Email hoặc tên đã tồn tại.'}, status_code=409)
        logging.error('Database request failed: %s', error.args[0] if error.args else type(error).__name__,
                      exc_info=(type(error), error, error.__traceback__))
        return JSONResponse({'error': 'Xử lý thất bại. Kiểm tra kết nối và schema MySQL.'}, status_code=503)

    @app.exception_handler(Exception)
    async def unexpected(request, error):
        rid = getattr(request.state, 'request_id', '-')
        if not getattr(request.state, 'exception_logged', False):
            logging.error('Python API request failed', exc_info=(type(error), error, error.__traceback__),
                          extra={'request_id': rid})
        return JSONResponse({'error': 'Xử lý thất bại. Kiểm tra storage/logs/api-error.log.', 'request_id': rid},
                            status_code=500, headers={'X-Request-ID': rid})

    app.add_middleware(SecurityMiddleware, database=db)
    app.add_middleware(RequestLimit)
    app.add_middleware(RequestLogMiddleware)

    async def session(response, user):
        token = secrets.token_urlsafe(32)
        await db.query('DELETE FROM sessions WHERE expires_at<NOW()')
        await db.query('INSERT INTO sessions(token_hash,user_id,expires_at) VALUES (%s,%s,%s)',
                       (digest(token), user['id'], datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=7)))
        response.set_cookie(COOKIE, token, max_age=7 * 86400, httponly=True, samesite='lax', secure=os.getenv('COOKIE_SECURE') == 'true', path='/')

    async def own_topic(user, topic):
        rows = await db.query('SELECT * FROM topics WHERE user_id=%s AND id=%s', (user['id'], str(topic or '')))
        if not rows:
            raise AppError('Không tìm thấy chủ đề.', 404)
        return rows[0]

    async def own_conversation(user, cid):
        rows = await db.query('SELECT * FROM conversations WHERE user_id=%s AND id=%s', (user['id'], cid))
        if not rows:
            raise AppError('Không tìm thấy cuộc trò chuyện.', 404)
        return rows[0]

    async def messages(cid):
        rows = await db.query('SELECT id,role,content,metadata,created_at FROM messages WHERE conversation_id=%s ORDER BY id', (cid,))
        return [row | (row['metadata'] or {}) for row in rows]

    async def own_preview(user, pid):
        rows = await db.query('SELECT * FROM previews WHERE id=%s AND user_id=%s AND expires_at>NOW()', (pid, user['id']))
        if not rows:
            raise AppError('Preview không tồn tại hoặc đã hết hạn.', 404)
        return rows[0]

    @app.get('/api/health')
    async def health():
        try:
            await db.check_schema()
            return {'status': 'ok', 'database': 'mysql', 'schema': 'ready', 'frontend': 'react', 'backend': 'python', 'rag': 'in-process'}
        except Exception:
            return JSONResponse({'error': 'Chưa kết nối được MySQL hoặc chưa khởi tạo schema.'}, status_code=503)

    @app.post('/api/auth/register')
    async def register(request: Request):
        data = await body(request)
        address, name = email(data.get('email')), label(data.get('name'), 80)
        hashed, uid = await hash_password(data.get('password')), identity()
        async with db.transaction() as connection:
            claimed = await execute(connection, "SELECT value FROM app_settings WHERE name='legacy_owner' FOR UPDATE")
            if not claimed:
                raise AppError('Chạy python -m scripts.setup_mysql trước khi tạo tài khoản.', 503)
            legacy = claimed[0]['value'] is None
            await execute(connection, 'INSERT INTO users(id,email,name,password_hash,legacy_workspace) VALUES (%s,%s,%s,%s,%s)', (uid, address, name, hashed, legacy))
            if legacy:
                await execute(connection, "UPDATE app_settings SET value=%s WHERE name='legacy_owner'", (uid,))
                await execute(connection, 'INSERT INTO topics(user_id,id,name) SELECT %s,id,name FROM legacy_topics', (uid,))
                await execute(connection, "INSERT INTO documents(id,user_id,topic,filename,sha256,file_blob,page_count,ocr_pages,chunk_count,chunks,status) SELECT id,%s,topic,filename,sha256,file_blob,page_count,ocr_pages,chunk_count,chunks,'ready' FROM legacy_documents", (uid,))
                await execute(connection, 'DELETE FROM legacy_documents')
                await execute(connection, 'DELETE FROM legacy_topics')
        user = {'id': uid, 'email': address, 'name': name, 'legacy_workspace': legacy}
        migration = None
        if legacy:
            totals = await db.query('SELECT COUNT(*) AS documents FROM documents WHERE user_id=%s', (uid,))
            migration = {'documents': totals[0]['documents']}
            if not totals[0]['documents']:
                try:
                    migration = await sync_library(db, rag, user)
                except Exception:
                    logging.exception('Legacy library sync pending')
                    migration = {'pending': True}
        response = JSONResponse({'user': await avatars.user_with_avatar(db, user), 'migration': migration}, status_code=201)
        await session(response, user)
        return response

    @app.post('/api/auth/login')
    async def login(request: Request):
        data = await body(request)
        address = email(data.get('email'))
        key = digest(address)
        attempts = await db.query('SELECT COUNT(*) AS n FROM login_attempts WHERE identity_hash=%s AND attempted_at>DATE_SUB(NOW(),INTERVAL 15 MINUTE)', (key,))
        if attempts[0]['n'] >= 5:
            raise AppError('Đăng nhập sai nhiều lần. Thử lại sau 15 phút.', 429)
        users = await db.query('SELECT * FROM users WHERE email=%s', (address,))
        valid = await verify_password(data.get('password'), users[0]['password_hash'] if users else app.state.dummy_hash)
        if not users or not valid:
            await db.query('INSERT INTO login_attempts(identity_hash) VALUES (%s)', (key,))
            raise AppError('Email hoặc mật khẩu không đúng.', 401)
        await db.query('DELETE FROM login_attempts WHERE identity_hash=%s', (key,))
        response = JSONResponse({'user': await avatars.user_with_avatar(db, users[0])})
        await session(response, users[0])
        return response

    @app.get('/api/auth/me')
    async def me(request: Request):
        return {'user': await avatars.user_with_avatar(db, request.state.user)}

    @app.post('/api/auth/logout')
    async def logout(request: Request):
        await db.query('DELETE FROM sessions WHERE token_hash=%s', (digest(request.cookies[COOKIE]),))
        response = JSONResponse({'status': 'ok'})
        response.delete_cookie(COOKIE, path='/', httponly=True, samesite='lax', secure=os.getenv('COOKIE_SECURE') == 'true')
        return response

    @app.put('/api/avatars/profile')
    async def profile_avatar(request: Request):
        await avatars.set_avatar(db, request.state.user['id'], 'profile', (await body(request)).get('preset'))
        return {'user': await avatars.user_with_avatar(db, request.state.user)}

    @app.post('/api/avatars/profile/image')
    async def profile_image(request: Request):
        async with request.form(max_files=1, max_fields=5) as form:
            await avatars.upload_avatar(db, request.state.user['id'], 'profile', form.get('image'))
        return {'user': await avatars.user_with_avatar(db, request.state.user)}

    @app.put('/api/topics/{tid}/avatar')
    async def bot_avatar(tid: str, request: Request):
        await own_topic(request.state.user, tid)
        return {'avatar': await avatars.set_avatar(db, request.state.user['id'], 'bot:' + tid, (await body(request)).get('preset'))}

    @app.post('/api/topics/{tid}/avatar/image')
    async def bot_image(tid: str, request: Request):
        await own_topic(request.state.user, tid)
        async with request.form(max_files=1, max_fields=5) as form:
            return {'avatar': await avatars.upload_avatar(db, request.state.user['id'], 'bot:' + tid, form.get('image'))}

    @app.get('/api/avatars/{slot}/image')
    async def avatar_image(slot: str, request: Request):
        if slot != 'profile':
            if not slot.startswith('bot:'):
                raise AppError('Không tìm thấy avatar.', 404)
            await own_topic(request.state.user, slot[4:])
        rows = await db.query('SELECT file_blob FROM avatars WHERE user_id=%s AND slot=%s', (request.state.user['id'], slot))
        if not rows or not rows[0]['file_blob']:
            raise AppError('Không tìm thấy ảnh avatar.', 404)
        return Response(rows[0]['file_blob'], media_type='image/jpeg')

    @app.get('/api/languages')
    async def languages(request: Request):
        return await rag(request.state.user, '/languages')

    @app.post('/api/library/sync')
    async def library_sync(request: Request):
        return await sync_library(db, rag, request.state.user)

    @app.get('/api/topics')
    async def topics(request: Request):
        user = request.state.user
        rows = await db.query('''SELECT t.*,COUNT(d.id) AS pdf_count,COALESCE(SUM(d.chunk_count),0) AS chunk_count
            FROM topics t LEFT JOIN documents d ON d.user_id=t.user_id AND d.topic=t.id AND d.status='ready'
            WHERE t.user_id=%s GROUP BY t.user_id,t.id ORDER BY t.name''', (user['id'],))
        images = await db.query('SELECT slot,preset,sha256 FROM avatars WHERE user_id=%s AND slot LIKE %s', (user['id'], 'bot:%'))
        by_slot = {image['slot']: image for image in images}
        return {'topics': [row | {'avatar': avatars.metadata(by_slot.get('bot:' + row['id']), 'bot:' + row['id'])} for row in rows]}

    @app.post('/api/topics', status_code=201)
    async def create_topic(request: Request):
        data = await body(request)
        user = request.state.user
        topic = await rag(user, '/topics', method='POST', json={'name': label(data.get('name'), 100)})
        await db.query('INSERT INTO topics(user_id,id,name) VALUES (%s,%s,%s)', (user['id'], topic['id'], topic['name']))
        return topic

    @app.delete('/api/topics/{tid}')
    async def delete_topic(tid: str, request: Request):
        user = request.state.user
        await own_topic(user, tid)
        await rag(user, '/topics/' + quote(tid, safe=''), method='DELETE')
        async with db.transaction() as connection:
            await execute(connection, 'DELETE FROM avatars WHERE user_id=%s AND slot=%s', (user['id'], 'bot:' + tid))
            # Foreign keys also delete documents, previews, conversations and their messages.
            await execute(connection, 'DELETE FROM topics WHERE user_id=%s AND id=%s', (user['id'], tid))
        return {'status': 'deleted'}

    @app.patch('/api/topics/{tid}/preferences')
    async def preferences(tid: str, request: Request):
        user, data = request.state.user, await body(request)
        await own_topic(user, tid)
        bot_name, theme = label(data.get('bot_name'), 80), data.get('theme')
        if not isinstance(theme, str) or theme not in THEMES:
            raise AppError('Theme không được hỗ trợ.')
        await db.query('UPDATE topics SET bot_name=%s,theme=%s WHERE user_id=%s AND id=%s', (bot_name, theme, user['id'], tid))
        return await own_topic(user, tid)

    @app.get('/api/documents')
    async def documents(request: Request):
        topic = request.query_params.get('topic')
        await own_topic(request.state.user, topic)
        rows = await db.query('SELECT id,filename,topic,page_count,ocr_pages,chunk_count,index_mode,status,created_at FROM documents WHERE user_id=%s AND topic=%s ORDER BY created_at DESC', (request.state.user['id'], topic))
        return {'documents': rows}

    @app.get('/api/documents/{did}/file')
    async def document_file(did: str, request: Request):
        rows = await db.query('SELECT filename,file_blob FROM documents WHERE id=%s AND user_id=%s', (did, request.state.user['id']))
        if not rows:
            raise AppError('Không tìm thấy tài liệu.', 404)
        return Response(rows[0]['file_blob'], media_type='application/pdf', headers={'Content-Disposition': "attachment; filename*=UTF-8''" + quote(rows[0]['filename'])})

    @app.delete('/api/documents/{did}')
    async def delete_document(did: str, request: Request):
        user = request.state.user
        rows = await db.query('SELECT topic,sha256 FROM documents WHERE id=%s AND user_id=%s', (did, user['id']))
        if not rows:
            raise AppError('Không tìm thấy tài liệu.', 404)
        try:
            await rag(user, '/document?' + urlencode(rows[0]), method='DELETE')
        except AppError as exc:
            if exc.status != 404:
                raise
        await db.query('DELETE FROM documents WHERE id=%s AND user_id=%s', (did, user['id']))
        return {'status': 'deleted'}

    @app.post('/api/ingest')
    async def ingest(request: Request):
        user, results = request.state.user, []
        async with request.form(max_files=10, max_fields=20) as form:
            topic = str(form.get('topic') or '')
            await own_topic(user, topic)
            uploads = form.getlist('files')
            if not uploads:
                raise AppError('Chọn ít nhất một PDF.')
            if sum(getattr(upload, 'size', 0) or 0 for upload in uploads) > 75 * 1024 * 1024:
                raise AppError('Tổng PDF vượt 75 MB.')
            for upload in uploads:
                name = getattr(upload, 'filename', '')
                try:
                    name, content = await pdf_upload(upload)
                    sha = digest(content)
                    existing = await db.query('SELECT filename,status FROM documents WHERE user_id=%s AND topic=%s AND sha256=%s', (user['id'], topic, sha))
                    if existing and existing[0]['status'] == 'ready':
                        results.append({'file': existing[0]['filename'], 'status': 'skipped'})
                        continue
                    if not existing:
                        await db.query('INSERT INTO documents(id,user_id,topic,filename,sha256,file_blob) VALUES (%s,%s,%s,%s,%s,%s)', (identity(), user['id'], topic, name, sha, content))
                    processed = await rag(user, '/ingest', method='POST', data={'topic': topic, 'force_ocr': 'true' if form.get('force_ocr') == 'true' else 'false'}, files={'files': (name, content, 'application/pdf')})
                    result = processed['results'][0]
                    if result['status'] == 'error':
                        raise AppError(result['error'])
                    await store_document(db, rag, user, topic, result.get('file') or name, content)
                    results.append(result)
                except AppError as exc:
                    logging.exception('Import PDF failed: topic=%r file=%r', topic, name)
                    results.append({'file': name, 'status': 'error', 'error': str(exc)})
        return {'results': results}

    @app.post('/api/previews')
    async def preview(request: Request):
        user = request.state.user
        async with request.form(max_files=1, max_fields=20) as form:
            topic = str(form.get('topic') or '')
            await own_topic(user, topic)
            name, content = await pdf_upload(form.get('file'))
            values = {key: str(form[key]) for key in ('topic', 'source_language', 'target_language', 'provider', 'quality', 'domain', 'glossary', 'force_ocr') if key in form}
            prepared = await rag(user, '/preview', method='POST', data=values, files={'file': (name, content, 'application/pdf')})
            pid = identity()
            await db.query('INSERT INTO previews(id,user_id,topic,filename,file_blob,rag_token,prepared,expires_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)',
                           (pid, user['id'], topic, name, content, prepared['preview_id'], json.dumps(prepared), datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)))
            return {'id': pid, **prepared}

    @app.patch('/api/previews/{pid}')
    async def edit_preview(pid: str, request: Request):
        data = await body(request)
        preview = await own_preview(request.state.user, pid)
        prepared = preview['prepared']
        try:
            page_number = int(data.get('page', 0))
        except (ValueError, TypeError):
            page_number = 0
        page = next((page for page in prepared['pages'] if page['page'] == page_number), None)
        text = data.get('text')
        if not page or not isinstance(text, str) or not text.strip() or len(text) > 200000:
            raise AppError('Nội dung/trang bản dịch không hợp lệ.')
        page['translation'] = text.strip()
        await db.query('UPDATE previews SET prepared=%s WHERE id=%s AND user_id=%s', (json.dumps(prepared), pid, request.state.user['id']))
        return {'id': pid, **prepared}

    async def remove_worker_preview(user, preview):
        try:
            await rag(user, '/preview/' + preview['rag_token'] + '?' + urlencode({'topic': preview['topic']}), method='DELETE')
        except AppError:
            pass  # MySQL preview remains usable even if the in-memory copy expired.

    @app.post('/api/previews/{pid}/import')
    async def import_preview(pid: str, request: Request):
        user, data = request.state.user, await body(request)
        preview = await own_preview(user, pid)
        mode = 'original' if data.get('index_mode') == 'original' else 'translated'
        result = await rag(user, '/ingest-saved', method='POST', data={'topic': preview['topic'], 'prepared': json.dumps(preview['prepared']), 'index_mode': mode}, files={'file': (preview['filename'], preview['file_blob'], 'application/pdf')})
        await store_document(db, rag, user, preview['topic'], result.get('file') or preview['filename'], preview['file_blob'], preview['prepared'], mode)
        await db.query('DELETE FROM previews WHERE id=%s AND user_id=%s', (pid, user['id']))
        await remove_worker_preview(user, preview)
        return result

    @app.delete('/api/previews/{pid}')
    async def delete_preview(pid: str, request: Request):
        user = request.state.user
        preview = await own_preview(user, pid)
        await db.query('DELETE FROM previews WHERE id=%s AND user_id=%s', (pid, user['id']))
        await remove_worker_preview(user, preview)
        return {'status': 'deleted'}

    @app.get('/api/conversations')
    async def conversations(request: Request):
        params = [request.state.user['id']]
        sql = 'SELECT * FROM conversations WHERE user_id=%s'
        if request.query_params.get('topic'):
            sql += ' AND topic=%s'
            params.append(request.query_params['topic'])
        if request.query_params.get('search'):
            sql += ' AND title LIKE %s'
            params.append('%' + request.query_params['search'][:120] + '%')
        return {'conversations': await db.query(sql + ' ORDER BY updated_at DESC LIMIT 200', params)}

    @app.post('/api/conversations', status_code=201)
    async def new_conversation(request: Request):
        user, data = request.state.user, await body(request)
        await own_topic(user, data.get('topic'))
        cid = identity()
        await db.query('INSERT INTO conversations(id,user_id,topic,title) VALUES (%s,%s,%s,%s)', (cid, user['id'], data['topic'], 'Cuộc trò chuyện mới'))
        return await own_conversation(user, cid)

    @app.get('/api/conversations/{cid}')
    async def conversation(cid: str, request: Request):
        chat = await own_conversation(request.state.user, cid)
        return chat | {'messages': await messages(cid)}

    @app.patch('/api/conversations/{cid}')
    async def rename_conversation(cid: str, request: Request):
        user, data = request.state.user, await body(request)
        await own_conversation(user, cid)
        await db.query('UPDATE conversations SET title=%s,updated_at=NOW(3) WHERE user_id=%s AND id=%s', (label(data.get('title')), user['id'], cid))
        return await own_conversation(user, cid)

    @app.delete('/api/conversations/{cid}')
    async def delete_conversation(cid: str, request: Request):
        user = request.state.user
        await own_conversation(user, cid)
        await db.query('DELETE FROM conversations WHERE user_id=%s AND id=%s', (user['id'], cid))
        return {'status': 'deleted'}

    @app.post('/api/conversations/{cid}/messages')
    async def send_message(cid: str, request: Request):
        user, data = request.state.user, await body(request)
        chat = await own_conversation(user, cid)
        question = label(data.get('question'), 4000)
        previous = await messages(cid)
        answer = await rag(user, '/ask', method='POST', json={'topic': chat['topic'], 'question': question, 'answer_language': data.get('answer_language') or 'vi', 'chat_history': [{'role': row['role'], 'content': row['content']} for row in previous[-8:]]})
        async with db.transaction() as connection:
            owned = await execute(connection, 'SELECT id FROM conversations WHERE id=%s AND user_id=%s FOR UPDATE', (cid, user['id']))
            if not owned:
                raise AppError('Cuộc trò chuyện đã bị xóa.', 404)
            info = {'sources': answer.get('sources', []), 'usage': answer.get('usage'), 'retrieval': answer.get('retrieval'), 'truncated': answer.get('truncated')}
            await execute(connection, 'INSERT INTO messages(conversation_id,role,content,metadata) VALUES (%s,%s,%s,%s),(%s,%s,%s,%s)',
                          (cid, 'user', question, '{}', cid, 'assistant', answer['answer'], json.dumps(info)))
            title = question[:80] if not previous and chat['title'] == 'Cuộc trò chuyện mới' else chat['title']
            await execute(connection, 'UPDATE conversations SET title=%s,updated_at=NOW(3) WHERE id=%s', (title, cid))
        return answer | {'conversation_id': cid}

    @app.post('/api/translate')
    async def translate(request: Request):
        return await rag(request.state.user, '/translate', method='POST', json=await body(request))

    @app.api_route('/api/{rest:path}', methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'HEAD'])
    async def missing_api(rest: str):
        raise AppError('Không tìm thấy API.', 404)

    @app.get('/{rest:path}')
    async def frontend(rest: str):
        directory = (ROOT / 'dist').resolve()
        target = (directory / rest).resolve()
        if target.is_relative_to(directory) and target.is_file():
            return FileResponse(target)
        index = directory / 'index.html'
        if not index.is_file():
            raise AppError('Chạy npm run build hoặc mở frontend tại cổng 5173.', 503)
        return FileResponse(index)

    return app


app = create_app()
