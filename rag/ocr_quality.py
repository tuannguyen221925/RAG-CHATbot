"""Local document OCR that preserves image resolution and separates printed columns."""
import os
from functools import lru_cache
from pathlib import Path
from threading import Lock

import numpy as np
from PIL import Image

from rag.errors import ConfigurationError

_lock = Lock()


def infer_languages(pdf):
    # Use selectable text across several pages; an English lecture may have a Vietnamese cover.
    samples = []
    for page in pdf.pages[:5]:
        try:
            samples.append(page.extract_text() or '')
        except Exception:
            # Broken native text must not prevent the OCR fallback from reading the PDF.
            continue
    text = '\n'.join(samples)
    letters = sum(c.isalpha() for c in text)
    vietnamese = sum(c in 'ăâđêôơưĂÂĐÊÔƠƯáàảãạắằẳẵặấầẩẫậéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ' for c in text)
    return ('en',) if letters >= 400 and vietnamese / max(1, letters) < 0.03 else ('vi', 'en')


@lru_cache(maxsize=2)
def get_reader(latin=True):
    # No document leaves this machine; only public model weights are downloaded.
    os.environ.setdefault('PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK', 'True')
    try:
        from paddleocr import PaddleOCR
        return PaddleOCR(
            text_detection_model_name='PP-OCRv5_mobile_det',
            text_recognition_model_name='latin_PP-OCRv5_mobile_rec' if latin else 'en_PP-OCRv5_mobile_rec',
            use_doc_orientation_classify=False, use_doc_unwarping=False,
            use_textline_orientation=False, device='cpu', enable_mkldnn=True,
            cpu_threads=4, text_recognition_batch_size=8,
            text_det_limit_side_len=2048, text_det_limit_type='max',
        )
    except ImportError as exc:
        raise ConfigurationError('OCR chất lượng cần requirements-ocr-quality.txt. Cài bằng python -m pip install -r requirements-ocr-quality.txt.') from exc


def column_bounds(rgb: np.ndarray) -> list[tuple[int, int]]:
    """Split only at sustained white gutters, never across text/code glyphs."""
    import cv2
    height, width = rgb.shape[:2]
    if width < 600 or height < 300:
        return [(0, width)]
    ink = (cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY) < 150).mean(axis=0)
    if float(ink.mean()) < 0.035:
        return [(0, width)]

    def gutter(fraction):
        left, right = int(width * (fraction - 0.06)), int(width * (fraction + 0.06))
        # A short average prevents one empty pixel inside a glyph becoming a column break.
        span = max(3, width // 400)
        smooth = np.convolve(ink, np.ones(span) / span, mode='same')
        cut = left + int(np.argmin(smooth[left:right]))
        local = float(np.mean(ink[max(0, cut-width//10):min(width, cut+width//10)]))
        return cut if smooth[cut] < min(0.025, local * 0.2) else None

    thirds = [gutter(1/3), gutter(2/3)]
    if all(c is not None for c in thirds):
        cuts = [0, *thirds, width]
    else:
        middle = gutter(0.5)
        cuts = [0, middle, width] if middle is not None else [0, width]
    return list(zip(cuts, cuts[1:]))


def embedded_images(path: Path, number: int) -> list[Image.Image]:
    """Extract body images directly, avoiding a second PDF/JPEG resampling step."""
    import pdfplumber
    from pypdf import PdfReader
    with pdfplumber.open(path) as pdf:
        page = pdf.pages[number - 1]
        area = page.width * page.height
        body = [image for image in page.images if 0.02 <= image['width'] * image['height'] / area < 0.95]
        # A single full-page scan is content, whereas a full-page image behind other images is often decoration.
        if not body:
            body = [image for image in page.images if image['width'] * image['height'] / area >= 0.95]
        names = [i['name'] for i in sorted(body, key=lambda i: (i['top'], i['x0']))]
    if not names:
        return []
    result = []
    try:
        images = list(PdfReader(path).pages[number - 1].images)
        for name in dict.fromkeys(names):
            found = next((im for im in images if im.name.rsplit('.', 1)[0] == name), None)
            if found is not None:
                result.append(found.image.convert('RGB'))
    except Exception:
        for image in result:
            image.close()
        return []  # The rendered full page remains available as fallback.
    # Do not return only some of the required image bodies.
    if len(result) != len(set(names)):
        for image in result:
            image.close()
        return []
    return result


def read_page(path: Path, number: int, rendered: Image.Image, languages=None) -> str:
    import cv2
    images = embedded_images(path, number)
    source_images = images or [rendered]
    output = []
    try:
        with _lock:
            reader = get_reader(latin=not languages or 'vi' in languages)
            for image in source_images:
                with image.convert('RGB') as converted:
                    rgb = np.array(converted)
                for left, right in column_bounds(rgb):
                    crop = rgb[:, left:right]
                    scale = min(3, 2400 / crop.shape[0])
                    if scale > 1:
                        crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
                    # Paddle's ndarray interface expects BGR, unlike EasyOCR.
                    result = list(reader.predict(cv2.cvtColor(crop, cv2.COLOR_RGB2BGR)))[0]
                    output.append('\n'.join(result['rec_texts']))
    finally:
        for image in images:
            image.close()
    return '\n\n'.join(output).strip()
