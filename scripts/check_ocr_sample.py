"""Run the actual OCR reader on one dense page and save a quality smoke check."""
import argparse
import json
import time
from pathlib import Path

from rag.config import get_settings
from rag.loader import ocr_page


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('pdf', type=Path)
    parser.add_argument('--page', type=int, required=True)
    args = parser.parse_args()
    tick = time.monotonic()
    text = ocr_page(args.pdf, args.page)
    lower = text.casefold()
    expected = ['python', 'numpy', 'array', 'creating', 'operations', 'import']
    matched = [word for word in expected if word in lower]
    report = {'file': args.pdf.name, 'page': args.page, 'ocr_batch_size': get_settings().ocr_batch_size,
              'chars': len(text), 'matched_keywords': matched, 'seconds': round(time.monotonic() - tick, 2),
              'passed': len(text) > 1000 and len(matched) >= 4}
    output = Path('storage/ocr-dense-page-sample.json')
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    output.with_suffix('.txt').write_text(text, encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False), flush=True)
    if not report['passed']:
        raise RuntimeError('Dense OCR page smoke check failed')


if __name__ == '__main__':
    main()
