"""Real-image regression check for literal NumPy APIs and executable code tokens."""
import json
import hashlib
import re
import time
from pathlib import Path

from rag.loader import OCR_CACHE_VERSION, ocr_page
from rag.config import get_settings

EXPECTED = ['import numpy as np', 'np.array', 'np.zeros', 'np.ones', 'np.arange', 'np.linspace',
            'np.full', 'np.eye', 'np.random.random', 'np.empty', 'np.loadtxt', 'np.concatenate',
            'np.transpose', 'np.delete', 'np.insert', 'np.append', 'np.add', 'np.subtract',
            'np.multiply', 'np.divide', 'np.exp', 'np.sqrt', 'np.log', 'e.dot(f)']
CODE = ['import numpy as np', 'np.arange(10,25,5)', 'np.linspace(0,2,9)']


def assess(text):
    compact = re.sub(r'\s+', '', text)
    return {'api_matches': [s for s in EXPECTED if s in text],
            'code_matches': [s for s in CODE if re.sub(r'\s+', '', s) in compact]}


def main():
    path = Path('C:/Users/khanh/Desktop/Mchine Learning/ML_Chap1_p2.pdf')
    started = time.monotonic()
    text = ocr_page(path, 9, ('en',))
    before = Path('storage/ocr-dense-page-sample.txt').read_text(encoding='utf-8')
    report = {'source': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
              'ocr_engine': get_settings().ocr_engine, 'ocr_version': OCR_CACHE_VERSION,
              'page': 9, 'before': assess(before), 'after': assess(text),
              'seconds': round(time.monotonic()-started, 2), 'expected_apis': len(EXPECTED), 'expected_code': len(CODE)}
    report['passed'] = len(report['after']['api_matches']) >= 16 and len(report['after']['code_matches']) == len(CODE)
    Path('storage/ocr-quality-final.txt').write_text(text, encoding='utf-8')
    Path('storage/ocr-quality-final.json').write_text(json.dumps(report,ensure_ascii=False,indent=2), encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False), flush=True)
    if not report['passed']:
        raise RuntimeError('Literal OCR regression check failed')


if __name__ == '__main__':
    main()
