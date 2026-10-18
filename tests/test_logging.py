import logging
import threading
import time

from fastapi.testclient import TestClient
from fastapi.routing import APIRoute

from api.observability import ContextFilter, RedactingFormatter, SharedRotatingHandler, request_id
from api.web import COOKIE, create_app
from scripts.logs import follow_log


def test_request_error_has_correlated_traceback_without_query_or_body(caplog):
    app = create_app()

    def broken():
        raise RuntimeError('synthetic-log-check')
    app.router.routes.insert(0, APIRoute('/api/auth/login', broken, methods=['GET']))

    # Without the lifespan context there is no startup SQL connection. The auth
    # path is intentionally excluded from session lookup by SecurityMiddleware.
    client = TestClient(app, raise_server_exceptions=False)
    context_filter = ContextFilter()
    caplog.handler.addFilter(context_filter)
    try:
        with caplog.at_level(logging.INFO):
            response = client.get('/api/auth/login?token=not-for-logs')
        assert response.status_code == 500
        rid = response.headers['x-request-id']
        assert response.json()['request_id'] == rid and rid != '-'
        records = [record for record in caplog.records if record.name == 'api.observability']
        assert any(record.exc_info and str(record.exc_info[1]) == 'synthetic-log-check' for record in records)
        assert all(record.request_id == rid for record in records)
        assert any('status=500' in record.getMessage() for record in records)
        assert all('not-for-logs' not in record.getMessage() for record in records)
        assert request_id.get() == '-'
    finally:
        caplog.handler.removeFilter(context_filter)
        client.close()


def test_file_logs_redact_secrets_and_rotate_without_open_handles(tmp_path, monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY', 'test-key-must-not-be-logged')
    handler = SharedRotatingHandler(tmp_path/'api.log', maxBytes=500, backupCount=2)
    handler.setFormatter(RedactingFormatter('%(levelname)s rid=%(request_id)s %(message)s'))
    handler.addFilter(ContextFilter())
    token = request_id.set('test-request')
    try:
        for i in range(20):
            record = logging.LogRecord('test', logging.ERROR, __file__, 1,
                                       'error %s test-key-must-not-be-logged', (i,), None)
            handler.handle(record)
            assert handler.stream is None
        text = ''.join(path.read_text(encoding='utf-8') for path in tmp_path.glob('api.log*') if not path.name.endswith('.lock'))
        assert '[REDACTED]' in text and 'rid=test-request' in text
        assert 'test-key-must-not-be-logged' not in text
        assert (tmp_path/'api.log.1').exists()
    finally:
        request_id.reset(token)
        handler.close()


def test_per_file_import_failure_is_logged_even_when_http_is_successful(caplog):
    class FakeDatabase:
        async def query(self, statement, params=()):
            if 'FROM sessions' in statement:
                return [{'id': 'test-user'}]
            if 'FROM topics' in statement:
                return [{'id': 'test-topic'}]
            raise AssertionError('Invalid PDF must be rejected before storing it')

    client = TestClient(create_app(database=FakeDatabase()))
    try:
        client.cookies.set(COOKIE, 'test-session')
        with caplog.at_level(logging.ERROR):
            response = client.post('/api/ingest', data={'topic': 'test-topic'},
                                   files={'files': ('broken.pdf', b'not-a-pdf', 'application/pdf')})
        assert response.status_code == 200
        assert response.json()['results'][0]['status'] == 'error'
        failures = [record for record in caplog.records if 'Import PDF failed' in record.getMessage()]
        assert len(failures) == 1 and failures[0].exc_info
        assert 'broken.pdf' in failures[0].getMessage()
    finally:
        client.close()


def test_tail_sees_file_created_after_start_and_handles_rotation(tmp_path, capsys):
    path, stop = tmp_path/'api.log', threading.Event()
    thread = threading.Thread(target=follow_log, args=(path, stop))
    thread.start()
    try:
        time.sleep(0.25)
        path.write_text('first-log-line\n', encoding='utf-8')
        time.sleep(0.3)
        path.replace(tmp_path/'api.log.1')
        path.write_text('second-log-line\n', encoding='utf-8')
        time.sleep(0.3)
    finally:
        stop.set()
        thread.join(timeout=2)
    output = capsys.readouterr().out
    assert output.count('first-log-line') == 1 and output.count('second-log-line') == 1
