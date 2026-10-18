"""Internal RAG engine, called in-process by api.web (not a public API)."""
import hashlib
import hmac
import re
import logging
import json
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from rag.chain import ask
from rag.config import get_settings
from rag.errors import ConfigurationError, Conflict, InvalidInput, RAGError, TopicNotFound
from rag.ingest import ingest_pdf_bytes, ingest_prepared, validate_pdf_content, validate_pdf_name
from rag.languages import COUNTRIES, LANGUAGES, PROVIDERS
from rag.loader import discard_ocr_cache
from rag.preview import PreparedPDF, delete_preview, get_preview, prepare_pdf, register_preview, update_preview
from rag.topics import create_topic, delete_topic, list_topics, require_topic, topic_lock
from rag.translation import translate_text
from rag.vectorstore import get_collection, topic_stats
from rag.workspace import user_scope

async def internal_workspace(request: Request):
    if request.url.path == '/health':
        yield
        return
    expected = get_settings().rag_service_token.get_secret_value()
    incoming = request.headers.get('authorization', '').removeprefix('Bearer ')
    identity = request.headers.get('x-rag-user', '')
    if not expected or not hmac.compare_digest(expected, incoming) or not re.fullmatch(r'[a-f0-9]{32}', identity):
        raise HTTPException(401, 'Dịch vụ này chỉ dành cho backend Python.')
    with user_scope({'id': identity, 'legacy_workspace': request.headers.get('x-rag-legacy') == '1'}):
        yield

app = FastAPI(title='BIG_RAG GPU service', version='2.0.0', dependencies=[Depends(internal_workspace)])

@app.exception_handler(RAGError)
async def rag_error(request, exc):
    status = 404 if isinstance(exc, TopicNotFound) else 409 if isinstance(exc, Conflict) else 503 if isinstance(exc, ConfigurationError) else 400
    logging.log(logging.ERROR if status >= 500 else logging.WARNING,
                'RAG %s %s failed: %s', request.method, request.url.path, exc,
                exc_info=(type(exc), exc, exc.__traceback__))
    return JSONResponse(status_code=status, content={'detail': str(exc)})

@app.exception_handler(Exception)
async def unexpected(request, exc):
    logging.exception('RAG xử lý thất bại')
    return JSONResponse(status_code=500, content={'detail': 'Xử lý RAG thất bại. Kiểm tra storage/logs/api-error.log.'})

@app.get('/health')
def health(): return {'status': 'ok'}

class TopicCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)

@app.get('/topics')
def topics(): return {'topics': list_topics()}

@app.post('/topics', status_code=201)
def add_topic(payload: TopicCreate): return create_topic(payload.name)

@app.delete('/topics/{topic}')
def remove_topic(topic: str): return delete_topic(topic)

@app.get('/stats')
def stats(topic: str): return topic_stats(topic)

@app.get('/inventory')
def inventory():
    result = []
    for info in list_topics():
        data, _ = require_topic(info['id'])
        files = [{'filename': p.name, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in data.glob('*.pdf')]
        result.append({**info, 'files': files})
    return {'topics': result}

@app.get('/file')
def file(topic: str, filename: str):
    data, _ = require_topic(topic)
    path = data / validate_pdf_name(filename)
    if not path.is_file(): raise TopicNotFound('Không tìm thấy PDF.')
    return FileResponse(path, media_type='application/pdf', filename=path.name)

@app.get('/indexed-document')
def indexed(topic: str, sha256: str):
    if not re.fullmatch(r'[a-f0-9]{64}', sha256): raise InvalidInput('SHA-256 không hợp lệ.')
    with topic_lock(topic):
        data = get_collection(topic).get(where={'file_sha256': sha256}, include=['documents', 'metadatas', 'embeddings'])
    chunks = [{'id': identity, 'text': text, 'metadata': metadata, 'embedding': vector.tolist()}
              for identity, text, metadata, vector in zip(data['ids'], data['documents'] or [], data['metadatas'] or [], data['embeddings'] if data['embeddings'] is not None else [])]
    return {'chunks': chunks, 'page_count': len({c['metadata']['page'] for c in chunks}),
            'ocr_pages': len({c['metadata']['page'] for c in chunks if c['metadata'].get('ocr')})}

@app.delete('/document')
def remove_document(topic: str, sha256: str):
    if not re.fullmatch(r'[a-f0-9]{64}', sha256): raise InvalidInput('SHA-256 không hợp lệ.')
    with topic_lock(topic):
        collection = get_collection(topic)
        existing = collection.get(where={'file_sha256': sha256}, include=['metadatas'])
        if not existing['ids']: raise TopicNotFound('Không tìm thấy tài liệu.')
        names = {m['source'] for m in existing['metadatas']}
        collection.delete(ids=existing['ids'])
        data, _ = require_topic(topic)
        for name in names: (data / validate_pdf_name(name)).unlink(missing_ok=True)
        (data / '.translations' / f'{sha256}.json').unlink(missing_ok=True)
        discard_ocr_cache(data, sha256)
    return {'status': 'deleted'}

@app.post('/ingest')
async def ingest(topic: str = Form(...), files: list[UploadFile] | None = File(None),
                 force_ocr: bool = Form(False), preview_ids: list[str] | None = Form(None), index_mode: str = Form('original')):
    results = []
    try:
        await run_in_threadpool(require_topic, topic)
        if bool(files) == bool(preview_ids): raise InvalidInput('Truyền files hoặc preview_ids.')
        if index_mode not in ('original', 'translated') or files and index_mode == 'translated':
            raise InvalidInput('Import bản dịch cần preview_ids.')
        for token in preview_ids or []:
            try:
                result = await run_in_threadpool(ingest_prepared, topic, get_preview(token, topic), index_mode=index_mode)
                results.append(result)
                delete_preview(token, topic, missing_ok=True)
            except RAGError as exc:
                logging.exception('Import preview failed: topic=%r preview=%r', topic, token)
                results.append({'preview_id': token, 'status': 'error', 'error': str(exc)})
        for upload in files or []:
            try:
                content = await upload.read(get_settings().max_upload_bytes + 1)
                results.append(await run_in_threadpool(ingest_pdf_bytes, topic, upload.filename or '', content, force_ocr=force_ocr))
            except RAGError as exc:
                logging.exception('Import PDF failed: topic=%r file=%r', topic, upload.filename)
                results.append({'file': upload.filename, 'status': 'error', 'error': str(exc)})
    finally:
        for upload in files or []: await upload.close()
    return {'topic': topic, 'results': results}

class AskRequest(BaseModel):
    topic: str
    question: str = Field(min_length=1, max_length=4000)
    k: int | None = Field(default=None, ge=1, le=12)
    answer_language: str = 'vi'
    chat_history: list[dict] = Field(default_factory=list, max_length=8)

@app.post('/ask')
def answer(payload: AskRequest):
    return ask(payload.topic, payload.question, k=payload.k, answer_language=payload.answer_language, chat_history=payload.chat_history)

@app.get('/languages')
def languages(): return {'languages': LANGUAGES, 'countries': COUNTRIES, 'providers': PROVIDERS}

@app.post('/ingest-saved')
async def ingest_saved(topic: str = Form(...), file: UploadFile = File(...), prepared: str = Form(...), index_mode: str = Form('original')):
    """Confirm a MySQL preview even after restarting the GPU service."""
    from langchain_core.documents import Document
    try:
        content = await file.read(get_settings().max_upload_bytes + 1)
        filename = validate_pdf_name(file.filename or '')
        validate_pdf_content(content)
        try: saved = json.loads(prepared)
        except (TypeError, ValueError): raise InvalidInput('Bản xem trước không hợp lệ.')
        if saved.get('file') != filename or not saved.get('pages'): raise InvalidInput('Bản xem trước không khớp PDF.')
        original, translated = [], []
        for page in saved['pages']:
            metadata = {'page': int(page['page']), 'ocr': bool(page.get('ocr')), 'source': filename}
            original.append(Document(page_content=page['original'], metadata=metadata))
            if page.get('translation'):
                translated.append(Document(page_content=page['translation'], metadata={**metadata, 'language': saved['target_language'], 'translated': True}))
        if index_mode == 'translated' and len(original) != len(translated): raise InvalidInput('Bản dịch chưa đủ trang.')
        document = PreparedPDF(filename, content, tuple(original), tuple(translated), saved.get('source_language','auto'), saved.get('target_language',''), saved.get('provider','groq'), saved.get('quality','careful'))
        return await run_in_threadpool(ingest_prepared, topic, document, index_mode=index_mode)
    finally: await file.close()

@app.post('/restore-index')
async def restore_index(topic: str = Form(...), file: UploadFile = File(...), chunks: str = Form(...)):
    """Restore the Chroma cache from vectors and PDF stored in MySQL."""
    try:
        content = await file.read(get_settings().max_upload_bytes + 1)
        filename = validate_pdf_name(file.filename or '')
        validate_pdf_content(content)
        digest = hashlib.sha256(content).hexdigest()
        saved = json.loads(chunks)
        if not saved or any(c['metadata'].get('file_sha256') != digest or c['metadata'].get('topic') != topic or c['metadata'].get('source') != filename for c in saved):
            raise InvalidInput('Vector không khớp PDF/chủ đề.')
        def restore():
            with topic_lock(topic):
                data, _ = require_topic(topic)
                target = data / filename
                if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() != digest: raise Conflict('PDF cùng tên có nội dung khác.')
                collection = get_collection(topic)
                for start in range(0, len(saved), 64):
                    batch = saved[start:start+64]
                    collection.upsert(ids=[c['id'] for c in batch], documents=[c['text'] for c in batch], metadatas=[c['metadata'] for c in batch], embeddings=[c['embedding'] for c in batch])
                target.write_bytes(content)
            return {'status':'restored','chunks':len(saved)}
        return await run_in_threadpool(restore)
    finally: await file.close()

class TranslationRequest(BaseModel):
    text: str
    target_language: str
    source_language: str = 'auto'
    provider: str = 'groq'
    domain: str = ''
    glossary: str = ''
    quality: str = 'careful'

@app.post('/translate')
def translate(payload: TranslationRequest):
    return {'translation': translate_text(**payload.model_dump()), 'target_language': payload.target_language}

@app.post('/preview')
async def preview(topic: str = Form(...), file: UploadFile = File(...), source_language: str = Form('auto'),
                  target_language: str = Form(''), provider: str = Form('groq'), force_ocr: bool = Form(False),
                  domain: str = Form(''), glossary: str = Form(''), quality: str = Form('careful')):
    try:
        await run_in_threadpool(require_topic, topic)
        content = await file.read(get_settings().max_upload_bytes + 1)
        prepared = await run_in_threadpool(prepare_pdf, file.filename or '', content, source_language=source_language,
                    target_language=target_language, provider=provider, force_ocr=force_ocr, domain=domain, glossary=glossary, quality=quality)
        return {'preview_id': register_preview(topic, prepared), 'expires_in': 3600, **prepared.as_dict()}
    finally: await file.close()

class PreviewEdit(BaseModel):
    page: int
    text: str

@app.patch('/preview/{token}')
def edit_preview(token: str, topic: str, payload: PreviewEdit): return update_preview(token, topic, payload.page, payload.text).as_dict()

@app.delete('/preview/{token}')
def remove_preview(token: str, topic: str):
    delete_preview(token, topic)
    return {'status': 'deleted'}
