"""Chuẩn bị bản xem trước trong RAM, không lưu PDF/vector vào chủ đề."""

import hashlib
from dataclasses import dataclass, replace
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
from time import monotonic
from uuid import uuid4

from langchain_core.documents import Document

from rag.config import get_settings
from rag.errors import Conflict, InvalidInput
from rag.languages import ocr_codes, validate_language
from rag.loader import load_pdf
from rag.translation import translate_text
from rag.workspace import preview_scope


@dataclass(frozen=True)
class PreparedPDF:
    filename: str
    content: bytes
    original: tuple[Document, ...]
    translated: tuple[Document, ...] = ()
    source_language: str = "auto"
    target_language: str = ""
    provider: str = ""
    quality: str = "careful"

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.content).hexdigest()

    def as_dict(self) -> dict:
        translations = {doc.metadata["page"]: doc.page_content for doc in self.translated}
        return {"file": self.filename, "source_language": self.source_language,
                "target_language": self.target_language, "provider": self.provider, "quality": self.quality,
                "pages": [{"page": doc.metadata["page"], "ocr": doc.metadata["ocr"],
                           "original": doc.page_content, "translation": translations.get(doc.metadata["page"], "")}
                          for doc in self.original]}


def prepare_pdf(filename: str, content: bytes, *, source_language: str = "auto",
                target_language: str = "", provider: str = "groq", force_ocr: bool = False,
                domain: str = "", glossary: str = "", quality: str = "careful") -> PreparedPDF:
    from rag.ingest import validate_pdf_content, validate_pdf_name

    filename = validate_pdf_name(filename)
    validate_pdf_content(content)
    validate_language(source_language, allow_auto=True)
    if target_language:
        validate_language(target_language)
    # Windows: khi người dùng dừng OCR, Poppler có thể còn giữ PDF trong chốc lát.
    # Không để lỗi dọn thư mục tạm che lỗi gốc hoặc KeyboardInterrupt.
    with TemporaryDirectory(prefix="big_rag_preview_", ignore_cleanup_errors=True) as folder:
        path = Path(folder) / filename
        path.write_bytes(content)
        original = tuple(load_pdf(path, source_name=filename, force_ocr=force_ocr,
                                  ocr_languages=ocr_codes(source_language)))
    translated = []
    if target_language:
        if sum(len(doc.page_content) for doc in original) > get_settings().max_translation_chars:
            raise InvalidInput("PDF vượt giới hạn ký tự dịch. Chia nhỏ tài liệu hoặc tăng MAX_TRANSLATION_CHARS.")
        for doc in original:
            text = translate_text(doc.page_content, target_language, source_language=source_language,
                                  provider=provider, domain=domain, glossary=glossary, quality=quality)
            translated.append(Document(page_content=text, metadata={**doc.metadata,
                                       "language": target_language, "translated": True}))
    return PreparedPDF(filename, content, original, tuple(translated), source_language,
                       target_language, provider if target_language else "", quality)


def edit_translation(prepared: PreparedPDF, page: int, text: str) -> PreparedPDF:
    if not prepared.translated or not text.strip():
        raise InvalidInput("Bản dịch trang không được rỗng.")
    if len(text) > get_settings().max_translation_chars:
        raise InvalidInput("Bản dịch quá dài.")
    if page not in {doc.metadata["page"] for doc in prepared.translated}:
        raise InvalidInput("Trang không tồn tại trong bản dịch.")
    documents = tuple(Document(page_content=text.strip(), metadata={**doc.metadata, "edited": True})
                      if doc.metadata["page"] == page else doc for doc in prepared.translated)
    return replace(prepared, translated=documents)


# API local, một worker: token preview hết hạn sau một giờ, giới hạn RAM.
_previews: dict[str, tuple[str, PreparedPDF, float]] = {}
_lock = Lock()
PREVIEW_TTL = 3600
MAX_PREVIEW_BYTES = 150 * 1024 * 1024


def register_preview(topic: str, prepared: PreparedPDF) -> str:
    topic = preview_scope(topic)
    with _lock:
        for token, (_, _, expires) in list(_previews.items()):
            if expires <= monotonic():
                del _previews[token]
        size = len(prepared.content) + sum(len(d.page_content.encode("utf-8")) for d in (*prepared.original, *prepared.translated))
        used = sum(len(p.content) + sum(len(d.page_content.encode("utf-8")) for d in (*p.original, *p.translated))
                   for _, p, _ in _previews.values())
        if len(_previews) >= 20 or used + size > MAX_PREVIEW_BYTES:
            raise Conflict("Bộ nhớ preview đã đầy. Xóa preview cũ hoặc chờ hết hạn rồi thử lại.")
        token = uuid4().hex
        _previews[token] = (topic, prepared, monotonic() + PREVIEW_TTL)
        return token


def get_preview(token: str, topic: str) -> PreparedPDF:
    topic = preview_scope(topic)
    with _lock:
        entry = _previews.get(token)
        if not entry or entry[2] <= monotonic():
            _previews.pop(token, None)
            raise InvalidInput("Preview không tồn tại hoặc đã hết hạn. Hãy tạo lại bản xem trước.")
        if entry[0] != topic:
            raise InvalidInput("Preview thuộc chủ đề khác.")
        return entry[1]


def delete_preview(token: str, topic: str, *, missing_ok: bool = False):
    if not missing_ok:
        get_preview(token, topic)
    topic = preview_scope(topic)
    with _lock:
        if token in _previews and _previews[token][0] != topic:
            raise InvalidInput("Preview thuộc chủ đề khác.")
        _previews.pop(token, None)


def delete_topic_previews(topic: str):
    scope = preview_scope(topic)
    with _lock:
        for token, entry in list(_previews.items()):
            if entry[0] == scope:
                del _previews[token]


def update_preview(token: str, topic: str, page: int, text: str) -> PreparedPDF:
    prepared = edit_translation(get_preview(token, topic), page, text)
    with _lock:
        entry = _previews.get(token)
        if not entry or entry[0] != preview_scope(topic) or entry[2] <= monotonic():
            raise InvalidInput("Preview đã hết hạn. Hãy tạo lại bản xem trước.")
        _previews[token] = (entry[0], prepared, entry[2])
    return prepared
