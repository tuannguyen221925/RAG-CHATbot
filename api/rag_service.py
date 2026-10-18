"""Run the existing RAG API in-process; no second HTTP service is required."""
import httpx
import logging

from rag.config import get_settings
from .main import app as worker
from .security import AppError


class RagService:
    def __init__(self, app=worker):
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url='http://rag.internal', timeout=1800)

    async def close(self):
        await self.client.aclose()

    async def __call__(self, user, path, method='GET', binary=False, **options):
        response = await self.client.request(method, path, headers={
            'Authorization': 'Bearer ' + get_settings().rag_service_token.get_secret_value(),
            'X-RAG-User': user['id'], 'X-RAG-Legacy': '1' if user.get('legacy_workspace') else '0',
        }, **options)
        if not response.is_success:
            logging.getLogger(__name__).error('Internal RAG %s %s returned status=%s', method, path.split('?')[0], response.status_code)
            try:
                detail = response.json().get('detail')
            except ValueError:
                detail = None
            raise AppError(detail if isinstance(detail, str) else 'Dịch vụ RAG xử lý thất bại.', response.status_code)
        return response.content if binary else response.json()
