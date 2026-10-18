from types import SimpleNamespace

import numpy as np
from PIL import Image

from rag.ocr_quality import column_bounds, embedded_images, infer_languages, read_page


def test_real_white_gutters_split_three_columns_without_cutting_text():
    image = np.full((700, 1020, 3), 255, dtype=np.uint8)
    for start in (10, 350, 690):
        for y in range(20, 680, 16):
            image[y:y+6, start:start+310] = 0
    bounds = column_bounds(image)
    assert len(bounds) == 3
    assert 320 <= bounds[0][1] <= 350 and 660 <= bounds[1][1] <= 690
    assert bounds[0][0] == 0 and bounds[-1][1] == 1020
    # Continuous code lines must not be sliced into arbitrary thirds.
    image[:, 300:730] = 0
    assert column_bounds(image) == [(0, 1020)]


def test_native_document_language_preserves_vietnamese_and_english():
    def document(text):
        return SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda: text)])
    assert infer_languages(document('Introduction to machine learning and Python arrays. ' * 25)) == ('en',)
    assert infer_languages(document('Tài liệu tiếng Việt hướng dẫn lập trình và xử lý dữ liệu. ' * 25)) == ('vi', 'en')
    assert infer_languages(document('')) == ('vi', 'en')
    def broken_text():
        raise ValueError('invalid native font encoding')
    broken = SimpleNamespace(extract_text=broken_text)
    healthy = document('Introduction to machine learning and Python arrays. ' * 25).pages[0]
    assert infer_languages(SimpleNamespace(pages=[broken, healthy])) == ('en',)


def test_quality_reader_preserves_literal_code_and_column_order(monkeypatch, tmp_path):
    calls = []
    image = Image.new('RGB', (900, 700), 'white')
    monkeypatch.setattr('rag.ocr_quality.embedded_images', lambda *a: [image])
    monkeypatch.setattr('rag.ocr_quality.column_bounds', lambda a: [(0, 300), (300, 600), (600, 900)])
    def predict(pixels):
        calls.append(pixels.shape)
        return iter([{'rec_texts': [['>>> import numpy as np'], ['>>> np.arange(10,25,5)'], ['>>> np.linspace(0,2,9)']][len(calls)-1]}])
    monkeypatch.setattr('rag.ocr_quality.get_reader', lambda **k: SimpleNamespace(predict=predict))
    text = read_page(tmp_path / 'sample.pdf', 1, image, ('en',))
    assert text == '>>> import numpy as np\n\n>>> np.arange(10,25,5)\n\n>>> np.linspace(0,2,9)'
    assert len(calls) == 3


def test_smaller_content_figures_are_kept_with_the_main_image(monkeypatch, tmp_path):
    from contextlib import nullcontext
    images = [{'name': name, 'width': width, 'height': height, 'top': 0, 'x0': i}
              for i, (name, width, height) in enumerate([
                  ('background', 100, 100), ('main', 60, 50), ('second', 40, 25), ('logo', 5, 5)])]
    monkeypatch.setattr('pdfplumber.open', lambda path: nullcontext(SimpleNamespace(
        pages=[SimpleNamespace(width=100, height=100, images=images)])))
    originals = [SimpleNamespace(name=name+'.jpg', image=Image.new('RGB', (width, height)))
                 for name, width, height in [('background',100,100),('main',60,50),('second',40,25),('logo',5,5)]]
    monkeypatch.setattr('pypdf.PdfReader', lambda path: SimpleNamespace(pages=[SimpleNamespace(images=originals)]))
    selected = embedded_images(tmp_path/'test.pdf', 1)
    assert [image.size for image in selected] == [(60,50),(40,25)]
    for image in selected:
        image.close()


def test_changing_engine_cannot_reuse_the_old_ocr_cache(tmp_path, monkeypatch):
    from rag.config import get_settings
    from rag.loader import _cache_folder
    path = tmp_path/'test.pdf'
    path.write_bytes(b'pdf-content-for-cache-key')
    old = _cache_folder(path, ('en',))
    monkeypatch.setenv('OCR_ENGINE', 'paddle')
    get_settings.cache_clear()
    new = _cache_folder(path, ('en',))
    assert old != new


def test_other_languages_keep_the_easyocr_engine_and_cache(tmp_path, monkeypatch):
    from rag.config import get_settings
    from rag.loader import _cache_folder, effective_ocr_engine
    path = tmp_path/'test.pdf'
    path.write_bytes(b'pdf-content-for-cache-key')
    old = _cache_folder(path, ('es', 'en'))
    monkeypatch.setenv('OCR_ENGINE', 'paddle')
    get_settings.cache_clear()
    assert effective_ocr_engine(('es', 'en')) == 'easyocr'
    assert effective_ocr_engine(('en',)) == 'paddle'
    assert _cache_folder(path, ('es', 'en')) == old
