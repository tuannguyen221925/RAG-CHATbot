"""Compare technical OCR against literal snippets transcribed from the source image."""
import json
import os
import time
import argparse
from pathlib import Path

os.environ.setdefault('PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK', 'True')

import cv2
from paddleocr import PaddleOCR


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mkldnn', action='store_true')
    parser.add_argument('--columns', type=int, default=3)
    parser.add_argument('--latin', action='store_true')
    args = parser.parse_args()
    started = time.monotonic()
    ocr = PaddleOCR(text_detection_model_name='PP-OCRv5_mobile_det',
                    text_recognition_model_name='latin_PP-OCRv5_mobile_rec' if args.latin else 'en_PP-OCRv5_mobile_rec',
                    use_doc_orientation_classify=False, use_doc_unwarping=False,
                    use_textline_orientation=False, device='cpu', enable_mkldnn=args.mkldnn,
                    cpu_threads=4, text_recognition_batch_size=8,
                    text_det_limit_side_len=2048, text_det_limit_type='max')
    image = cv2.imread('tmp/pdfs/embedded-p9.png')
    texts, scores = [], []
    for index in range(args.columns):
        start, end = round(image.shape[1] * index / 3), round(image.shape[1] * (index + 1) / 3)
        column = cv2.resize(image[:, start:end], None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        result = list(ocr.predict(column))[0]
        texts.extend(result['rec_texts'])
        scores.extend(float(s) for s in result['rec_scores'])
        print(f'Column {index+1}: {len(result["rec_texts"])} lines', flush=True)
    text = '\n'.join(texts)
    # Literal API names and code on this actual page, not broad topic words.
    expected = ['import numpy as np', 'np.array', 'np.zeros', 'np.ones', 'np.arange', 'np.linspace',
                'np.full', 'np.eye', 'np.random.random', 'np.empty', 'np.loadtxt', 'np.concatenate',
                'np.transpose', 'np.delete', 'np.insert', 'np.append', 'np.add', 'np.subtract',
                'np.multiply', 'np.divide', 'np.exp', 'np.sqrt', 'np.log', 'np.dot']
    old = Path('storage/ocr-dense-page-sample.txt').read_text(encoding='utf-8')
    report = {'engine': 'paddle-en-v5-column-3x', 'seconds': round(time.monotonic()-started, 2),
              'chars': len(text), 'mean_confidence': sum(scores)/len(scores),
              'before': [s for s in expected if s in old], 'after': [s for s in expected if s in text],
              'expected': expected}
    Path('storage/ocr-quality-candidate.txt').write_text(text, encoding='utf-8')
    Path('storage/ocr-quality-candidate.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
