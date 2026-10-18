from types import SimpleNamespace

import pytest
from PIL import Image

from rag.errors import InvalidInput
from rag.loader import _cached_ocr, discard_ocr_cache, load_pdf, needs_ocr, ocr_page


def test_render_is_one_page_and_images_are_closed(tmp_path, monkeypatch):
    calls, images = [], []
    def render(path, **kwargs):
        calls.append(kwargs)
        image = Image.new('RGB', (80, 100), 'white')
        images.append(image)
        return [image]
    monkeypatch.setattr('pdf2image.convert_from_path', render)
    monkeypatch.setattr('rag.loader.get_ocr_reader', lambda: SimpleNamespace(readtext=lambda *a, **k: ['read']))
    assert ocr_page(tmp_path / 'test.pdf', 12) == 'read'
    assert calls[0]['first_page'] == calls[0]['last_page'] == 12
    assert calls[0]['thread_count'] == 1
    with pytest.raises(ValueError):
        images[0].getpixel((0, 0))


def test_empty_ocr_retries_at_higher_resolution(tmp_path, monkeypatch):
    calls, attempts = [], iter([[], ['recovered text']])
    def render(path, **kwargs):
        calls.append(kwargs['dpi'])
        return [Image.new('RGB', (80, 100), 'white')]
    monkeypatch.setattr('pdf2image.convert_from_path', render)
    monkeypatch.setattr('rag.loader.get_ocr_reader', lambda: SimpleNamespace(readtext=lambda *a, **k: next(attempts)))
    assert ocr_page(tmp_path / 'test.pdf', 2) == 'recovered text'
    assert calls == [200, 300]


def test_gpu_oom_retries_with_smaller_canvas(tmp_path, monkeypatch):
    canvases = []
    def read(*args, **kwargs):
        canvases.append(kwargs['canvas_size'])
        if len(canvases) <= 2:
            raise RuntimeError('CUDA out of memory')
        return ['recovered']
    monkeypatch.setattr('pdf2image.convert_from_path', lambda *a, **k: [Image.new('RGB', (80, 100))])
    monkeypatch.setattr('rag.loader.get_ocr_reader', lambda: SimpleNamespace(readtext=read))
    monkeypatch.setattr('torch.cuda.empty_cache', lambda: None)
    assert ocr_page(tmp_path / 'test.pdf', 2) == 'recovered'
    assert canvases == [2560, 2560, 1280]


def test_native_title_does_not_hide_scanned_slide_body():
    page = SimpleNamespace(width=100, height=100, images=[{'x0': 0, 'x1': 100, 'top': 20, 'bottom': 100}])
    assert needs_ocr(page, 'Native title and footer ' * 3, 40)
    assert not needs_ocr(page, 'A long fully selectable body of native text. ' * 20, 40)
    assert needs_ocr(page, 'Unreadable (cid:999) font mapping ' * 10, 40)


def test_completed_page_cache_survives_later_page_failure(tmp_path, monkeypatch):
    calls = []
    def read(path, number):
        calls.append(number)
        if number == 2 and calls.count(2) == 1:
            raise RuntimeError('interrupted')
        return 'page ' + str(number)
    monkeypatch.setattr('rag.loader.ocr_page', read)
    path, folder = tmp_path / 'test.pdf', tmp_path / 'cache'
    assert _cached_ocr(path, 1, None, folder) == 'page 1'
    with pytest.raises(RuntimeError):
        _cached_ocr(path, 2, None, folder)
    assert _cached_ocr(path, 1, None, folder) == 'page 1'
    assert _cached_ocr(path, 2, None, folder) == 'page 2'
    assert calls == [1, 2, 2]


def test_empty_forced_ocr_keeps_native_text(pdf_bytes, tmp_path, monkeypatch):
    path = tmp_path / 'native.pdf'
    path.write_bytes(pdf_bytes)
    monkeypatch.setattr('rag.loader.ocr_page', lambda *args: '')
    pages = load_pdf(path, force_ocr=True)
    assert len(pages) == 1 and 'retrieval augmented' in pages[0].page_content
    assert pages[0].metadata['pdf_total_pages'] == 1
    assert pages[0].metadata['pdf_empty_pages'] == ''


def test_page_failure_is_not_silently_imported(pdf_bytes, tmp_path, monkeypatch):
    path = tmp_path / 'broken.pdf'
    path.write_bytes(pdf_bytes)
    def fail(*args):
        raise RuntimeError('OCR engine crashed')
    monkeypatch.setattr('rag.loader.ocr_page', fail)
    with pytest.raises(InvalidInput, match='trang 1'):
        load_pdf(path, force_ocr=True)


def test_deleting_pdf_discards_only_its_ocr_cache(tmp_path):
    digest = 'a' * 64
    cache = tmp_path / '.ocr-cache'
    removed = cache / (digest + '-options')
    kept = cache / ('b' * 64 + '-options')
    for folder in (removed, kept):
        folder.mkdir(parents=True)
        (folder / '1.json').write_text('{"text":"private text"}', encoding='utf-8')
    discard_ocr_cache(tmp_path, digest)
    assert not removed.exists() and kept.exists()
    with pytest.raises(InvalidInput):
        discard_ocr_cache(tmp_path, '../')
