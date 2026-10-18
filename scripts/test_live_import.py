"""Explicit live import check. Credentials come from an ephemeral environment variable."""
import argparse
import json
import os
import time
from pathlib import Path

import httpx
import pdfplumber


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('folder', type=Path)
    parser.add_argument('--url', default='http://127.0.0.1:8501')
    parser.add_argument('--name', required=True)
    parser.add_argument('--email', required=True)
    parser.add_argument('--library', default='Machine Learning OCR Test')
    parser.add_argument('--force-ocr', action='store_true')
    parser.add_argument('--output', type=Path, default=Path('storage/live-import-report.json'))
    args = parser.parse_args()
    password = os.environ.pop('BIGRAG_TEST_PASSWORD')
    paths = sorted(args.folder.glob('*.pdf'))
    if len(paths) != 7:
        raise RuntimeError(f'Expected exactly seven PDFs; found {len(paths)}')
    expected = {}
    for path in paths:
        with pdfplumber.open(path) as pdf:
            expected[path.name] = len(pdf.pages)
    report = {'email': args.email, 'library': args.library, 'force_ocr': args.force_ocr,
              'expected_pages': expected, 'results': []}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    def save():
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    with httpx.Client(base_url=args.url, timeout=httpx.Timeout(1800, connect=10)) as client:
        response = client.post('/api/auth/register', json={'name': args.name, 'email': args.email, 'password': password})
        if response.status_code == 409:
            response = client.post('/api/auth/login', json={'email': args.email, 'password': password})
        response.raise_for_status()
        user = response.json()['user']
        del password
        report['user_id'] = user['id']
        print(f"Authenticated {user['name']}; seven PDFs, {sum(expected.values())} pages", flush=True)
        response = client.post('/api/topics', json={'name': args.library})
        if response.status_code == 409:
            topics = client.get('/api/topics').json()['topics']
            topic = next(t['id'] for t in topics if t['name'] == args.library)
        else:
            response.raise_for_status()
            topic = response.json()['id']
        report['topic'] = topic
        save()
        started = time.monotonic()
        for index, path in enumerate(paths, 1):
            print(f'IMPORT {index}/7: {path.name} ({expected[path.name]} pages)', flush=True)
            tick = time.monotonic()
            with path.open('rb') as stream:
                response = client.post('/api/ingest', data={'topic': topic, 'force_ocr': str(args.force_ocr).lower()},
                                       files={'files': (path.name, stream, 'application/pdf')})
            response.raise_for_status()
            result = response.json()['results'][0]
            result['seconds'] = round(time.monotonic() - tick, 2)
            report['results'].append(result)
            save()
            print(json.dumps(result, ensure_ascii=False), flush=True)
        response = client.get('/api/documents', params={'topic': topic})
        response.raise_for_status()
        report['documents'] = response.json()['documents']
        # Inspect real persisted vector metadata in this account's scoped cache.
        from rag.vectorstore import get_collection
        from rag.workspace import user_scope
        with user_scope(user):
            metadata = get_collection(topic).get(include=['metadatas'])['metadatas']
        report['coverage'] = []
        for name, total in expected.items():
            pages = sorted({m['page'] for m in metadata if m['source'] == name})
            ocr_pages = sorted({m['page'] for m in metadata if m['source'] == name and m.get('ocr')})
            missing = sorted(set(range(1, total + 1)) - set(pages))
            report['coverage'].append({'file': name, 'expected': total, 'indexed': len(pages),
                                       'ocr_pages': ocr_pages, 'missing_pages': missing})
        report['seconds'] = round(time.monotonic() - started, 2)
        report['passed'] = (len(report['documents']) == 7 and
                            all(r['status'] in ('indexed', 'skipped') for r in report['results']) and
                            all(not r['missing_pages'] for r in report['coverage']))
        save()
        print(json.dumps({'passed': report['passed'], 'seconds': report['seconds'], 'coverage': report['coverage']}, ensure_ascii=False), flush=True)
        if not report['passed']:
            raise RuntimeError('Import coverage check failed; see saved report')


if __name__ == '__main__':
    main()
