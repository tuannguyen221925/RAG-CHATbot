"""Extract native text and OCR individual pages with bounded image memory."""
import hashlib
import json
import logging
import re
import shutil
from functools import lru_cache
from pathlib import Path
from threading import Lock
from uuid import uuid4

import pdfplumber
from langchain_core.documents import Document

from rag.config import get_settings
from rag.devices import require_device
from rag.errors import ConfigurationError, InvalidInput

_ocr_lock = Lock()
log = logging.getLogger(__name__)
OCR_CACHE_VERSION = 4


def effective_ocr_engine(languages=None):
    if get_settings().ocr_engine == 'paddle' and (not languages or set(languages) <= {'vi', 'en'}):
        return 'paddle'
    return 'easyocr'


@lru_cache(maxsize=3)
def get_ocr_reader(languages: tuple[str, ...] = ("vi", "en")):
    if get_settings().ocr_gpu:
        require_device("cuda")
    import easyocr
    return easyocr.Reader(list(languages), gpu=get_settings().ocr_gpu)


def ocr_page(path: Path, number: int, languages: tuple[str, ...] | None = None) -> str:
    """Render only this page. Never keep a whole PDF's decoded images in RAM."""
    import numpy as np
    from pdf2image import convert_from_path
    from pdf2image.exceptions import PDFInfoNotInstalledError, PDFPopplerTimeoutError

    settings = get_settings()
    for attempt, dpi in enumerate((settings.ocr_dpi, min(400, settings.ocr_dpi + 100))):
        images = []
        try:
            images = convert_from_path(
                str(path), dpi=dpi, first_page=number, last_page=number,
                poppler_path=settings.resolve_poppler(), thread_count=1,
                timeout=settings.ocr_page_timeout,
            )
            if len(images) != 1:
                raise InvalidInput(f"Không render được trang {number} để OCR.")
            if effective_ocr_engine(languages) == 'paddle':
                from rag.ocr_quality import read_page
                recognized = read_page(path, number, images[0], languages)
                if recognized or attempt:
                    return recognized
                continue
            with images[0].convert("RGB") as rgb:
                pixels = np.asarray(rgb)
                with _ocr_lock:
                    reader = get_ocr_reader(languages) if languages else get_ocr_reader()
                    retry_small = False
                    try:
                        lines = reader.readtext(pixels, detail=0, paragraph=True,
                                                batch_size=settings.ocr_batch_size if settings.ocr_gpu else 1,
                                                workers=0, canvas_size=2560)
                    except RuntimeError as exc:
                        if "out of memory" not in str(exc).lower():
                            raise
                        retry_small = True
                    if retry_small:
                        # Leave the exception block first: its traceback can retain GPU tensors.
                        import gc
                        import torch
                        gc.collect()
                        torch.cuda.empty_cache()
                        log.warning("OCR trang %s: giảm batch sau khi thiếu VRAM", number)
                        retry_canvas = False
                        try:
                            lines = reader.readtext(pixels, detail=0, paragraph=True, batch_size=1,
                                                    workers=0, canvas_size=2560)
                        except RuntimeError as exc:
                            if "out of memory" not in str(exc).lower():
                                raise
                            retry_canvas = True
                        if retry_canvas:
                            gc.collect()
                            torch.cuda.empty_cache()
                            lines = reader.readtext(pixels, detail=0, paragraph=True, batch_size=1,
                                                    workers=0, canvas_size=1280)
            recognized = "\n".join(lines).strip()
            if recognized or attempt:
                return recognized
            log.info("OCR trang %s chưa có chữ; thử lại ở %s DPI", number, min(400, dpi + 100))
        except PDFInfoNotInstalledError as exc:
            raise ConfigurationError("OCR cần Poppler. Đặt POPPLER_PATH đến thư mục chứa pdfinfo.exe và pdftoppm.exe.") from exc
        except PDFPopplerTimeoutError as exc:
            raise InvalidInput(f"Render OCR trang {number} quá thời gian {settings.ocr_page_timeout} giây. Thử lại để tiếp tục từ cache.") from exc
        finally:
            for image in images:
                image.close()
    return ""


def needs_ocr(page, text: str, minimum: int) -> bool:
    count = len(re.sub(r"\s", "", text))
    if count < minimum or "\ufffd" in text or "(cid:" in text:
        return True
    # A native title/footer can hide a scanned slide body.
    if count < 180 and page.width and page.height:
        image_area = sum(max(0, min(page.width, img['x1']) - max(0, img['x0'])) *
                         max(0, min(page.height, img['bottom']) - max(0, img['top']))
                         for img in page.images)
        return image_area / (page.width * page.height) >= 0.35
    return False


def _cache_folder(path: Path, languages) -> Path:
    settings = get_settings()
    key = hashlib.sha256(path.read_bytes()).hexdigest()
    options = json.dumps([OCR_CACHE_VERSION, effective_ocr_engine(languages), settings.ocr_dpi, languages or ("vi", "en")])
    return path.parent / '.ocr-cache' / (key + '-' + hashlib.sha256(options.encode()).hexdigest()[:12])


def _cached_ocr(path, number, languages, folder):
    cached = folder / f'{number}.json'
    try:
        saved = json.loads(cached.read_text(encoding='utf-8'))
        if isinstance(saved.get('text'), str):
            return saved['text']
    except (OSError, ValueError, AttributeError):
        pass
    text = ocr_page(path, number, languages) if languages else ocr_page(path, number)
    folder.mkdir(parents=True, exist_ok=True)
    temporary = folder / f'{number}-{uuid4().hex}.tmp'
    try:
        temporary.write_text(json.dumps({'text': text}, ensure_ascii=False), encoding='utf-8')
        temporary.replace(cached)
    finally:
        temporary.unlink(missing_ok=True)
    return text


def discard_ocr_cache(data: Path, sha256: str):
    if not re.fullmatch(r'[a-f0-9]{64}', sha256):
        raise InvalidInput('SHA-256 không hợp lệ.')
    root = data / '.ocr-cache'
    if not root.exists():
        return
    if root.resolve().parent != data.resolve():
        raise InvalidInput('Đường dẫn cache OCR không hợp lệ.')
    for folder in root.glob(sha256 + '-*'):
        if folder.resolve().parent != root.resolve():
            raise InvalidInput('Đường dẫn cache OCR không hợp lệ.')
        if folder.is_dir():
            shutil.rmtree(folder)


def load_pdf(path: str | Path, *, source_name: str | None = None,
             force_ocr: bool = False, ocr_languages: tuple[str, ...] | None = None) -> list[Document]:
    path = Path(path)
    settings = get_settings()
    documents, empty_pages = [], []
    cache = None
    number = 0
    try:
        with pdfplumber.open(path) as pdf:
            total_pages = len(pdf.pages)
            if total_pages > settings.max_pdf_pages:
                raise InvalidInput(f"PDF vượt giới hạn {settings.max_pdf_pages} trang.")
            if settings.ocr_engine == 'paddle' and ocr_languages is None:
                from rag.ocr_quality import infer_languages
                ocr_languages = infer_languages(pdf)
            for number, page in enumerate(pdf.pages, 1):
                try:
                    try:
                        native = (page.extract_text() or '').strip()
                    except Exception:
                        log.warning("Không trích xuất được text trang %s; chuyển sang OCR", number)
                        native = ''
                    use_ocr = force_ocr or needs_ocr(page, native, settings.ocr_min_text_chars)
                    text = native
                    if use_ocr:
                        if cache is None:
                            cache = _cache_folder(path, ocr_languages)
                        log.info("OCR %s: trang %s/%s", source_name or path.name, number, total_pages)
                        recognized = _cached_ocr(path, number, ocr_languages, cache)
                        text = recognized or native
                        if recognized and native and not force_ocr:
                            normalized = re.sub(r'\W', '', recognized).casefold()
                            missing = [line for line in native.splitlines()
                                       if re.sub(r'\W', '', line).casefold() not in normalized]
                            if missing:
                                text += '\n' + '\n'.join(missing)
                    if text.strip():
                        documents.append(Document(page_content=text, metadata={
                            'source': source_name or path.name, 'page': number, 'ocr': use_ocr,
                            'pdf_total_pages': total_pages,
                            'ocr_engine': effective_ocr_engine(ocr_languages) if use_ocr else 'native',
                            'ocr_version': OCR_CACHE_VERSION if use_ocr else 0,
                        }))
                    else:
                        empty_pages.append(number)
                        log.warning("%s: trang %s không có chữ sau OCR", source_name or path.name, number)
                finally:
                    page.close()
    except (ConfigurationError, InvalidInput):
        raise
    except Exception as exc:
        raise InvalidInput(f"Không đọc được PDF '{source_name or path.name}', trang {number}: {exc}. Thử lại sẽ dùng cache OCR đã hoàn tất.") from exc
    if not documents:
        raise InvalidInput("PDF không có văn bản đọc được sau khi trích xuất/OCR.")
    for doc in documents:
        doc.metadata['pdf_empty_pages'] = ','.join(map(str, empty_pages))
    return documents
