"""Read-only native text coverage audit for an input PDF folder."""
import argparse
import json
import re
from pathlib import Path

import pdfplumber


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('folder', type=Path)
    parser.add_argument('--output', type=Path, default=Path('storage/pdf-audit.json'))
    args = parser.parse_args()
    report = []
    for path in sorted(args.folder.glob('*.pdf')):
        pages = []
        with pdfplumber.open(path) as pdf:
            for number, page in enumerate(pdf.pages, 1):
                text = page.extract_text() or ''
                pages.append({'page': number, 'chars': len(re.sub(r'\s', '', text)),
                              'images': len(page.images), 'width': float(page.width), 'height': float(page.height)})
                page.close()
        entry = {'file': path.name, 'bytes': path.stat().st_size, 'total_pages': len(pages),
                 'ocr_candidates': [p['page'] for p in pages if p['chars'] < 40], 'pages': pages}
        report.append(entry)
        print(json.dumps({k: v for k, v in entry.items() if k != 'pages'}, ensure_ascii=False), flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
