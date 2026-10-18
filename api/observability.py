"""Console/file logs and request IDs without logging request bodies or credentials."""
import logging
import logging.config
import logging.handlers
import os
import secrets
import sys
import time
from contextvars import ContextVar
from pathlib import Path

from filelock import FileLock

request_id = ContextVar('log_request_id', default='-')
logger = logging.getLogger(__name__)


def configure_console():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='backslashreplace')


def log_directory():
    return Path(os.getenv('BIGRAG_LOG_DIR', Path(__file__).resolve().parents[1] / 'storage/logs')).resolve()


class ContextFilter(logging.Filter):
    def filter(self, record):
        if not hasattr(record, 'request_id'):
            record.request_id = request_id.get()
        return True


class RedactingFormatter(logging.Formatter):
    def format(self, record):
        text = super().format(record)
        for key, value in os.environ.items():
            if key.endswith(('_PASSWORD', '_TOKEN', '_API_KEY')) and len(value) >= 4:
                text = text.replace(value, '[REDACTED]')
        return text


class SharedRotatingHandler(logging.handlers.RotatingFileHandler):
    """Close between writes so Windows reload processes can rotate the same log."""
    def __init__(self, filename, **kwargs):
        super().__init__(filename, delay=True, encoding='utf-8', **kwargs)
        self.file_lock = FileLock(str(filename) + '.lock', timeout=5)

    def emit(self, record):
        try:
            with self.file_lock:
                try:
                    super().emit(record)
                finally:
                    if self.stream is not None:
                        self.stream.close()
                        self.stream = None
        except Exception:
            self.handleError(record)


def logging_config(name='api'):
    folder = log_directory()
    folder.mkdir(parents=True, exist_ok=True)
    level = os.getenv('LOG_LEVEL', 'INFO').upper()
    if level not in ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'):
        raise ValueError('LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR or CRITICAL')
    (folder / f'{name}.log').touch(exist_ok=True)
    if name == 'api':
        (folder / 'api-error.log').touch(exist_ok=True)
    file_handler = {'()': SharedRotatingHandler, 'formatter': 'standard', 'filters': ['context'],
                    'filename': str(folder / f'{name}.log'), 'maxBytes': 5*1024*1024, 'backupCount': 3}
    handlers = {'console': {'class': 'logging.StreamHandler', 'stream': 'ext://sys.stderr',
                            'formatter': 'standard', 'filters': ['context']}, 'file': file_handler}
    if name == 'api':
        handlers['errors'] = {**file_handler, 'level': 'ERROR', 'filename': str(folder / 'api-error.log')}
    return {'version': 1, 'disable_existing_loggers': False,
            'filters': {'context': {'()': ContextFilter}},
            'formatters': {'standard': {'()': RedactingFormatter,
                'format': '%(asctime)s %(levelname)s [%(name)s] rid=%(request_id)s %(filename)s:%(lineno)d | %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'}},
            'handlers': handlers, 'root': {'level': level, 'handlers': list(handlers)},
            'loggers': {'uvicorn': {'handlers': [], 'propagate': True, 'level': level},
                        'uvicorn.error': {'handlers': [], 'propagate': True, 'level': level},
                        'httpx': {'level': 'WARNING'}, 'httpcore': {'level': 'WARNING'},
                        'filelock': {'level': 'WARNING'},
                        'dev.frontend': {'handlers': ['file'], 'propagate': False, 'level': 'INFO'}}}


class RequestLogMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        identity = secrets.token_hex(8)
        scope.setdefault('state', {})['request_id'] = identity
        token = request_id.set(identity)
        started, status = time.monotonic(), 500

        async def logged_send(message):
            nonlocal status
            if message['type'] == 'http.response.start':
                status = message['status']
                message = {**message, 'headers': [*message.get('headers', []), (b'x-request-id', identity.encode())]}
            await send(message)

        try:
            await self.app(scope, receive, logged_send)
        except Exception:
            scope['state']['exception_logged'] = True
            logger.exception('Unhandled request: %s %s', scope['method'], scope['path'])
            raise
        finally:
            level = logging.ERROR if status >= 500 else logging.WARNING if status >= 400 else logging.INFO
            # Health polling is noisy; it remains visible with LOG_LEVEL=DEBUG.
            if scope['path'] == '/api/health' and status < 400:
                level = logging.DEBUG
            logger.log(level, 'HTTP %s %s status=%s duration_ms=%.1f', scope['method'], scope['path'],
                       status, (time.monotonic()-started)*1000)
            request_id.reset(token)
