import argparse
import json
import logging
import sys

from rag.chain import ask
from rag.errors import RAGError
from rag.ingest import ingest_pdf
from rag.languages import LANGUAGES
from rag.topics import create_topic, list_topics


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="BIG_RAG – quản lý PDF và hỏi đáp theo chủ đề")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("topics", help="Xem danh sách chủ đề")
    create = sub.add_parser("create-topic", help="Tạo chủ đề")
    create.add_argument("name")
    ingest = sub.add_parser("ingest", help="Import một hoặc nhiều PDF")
    ingest.add_argument("topic")
    ingest.add_argument("files", nargs="+")
    ingest.add_argument("--force-ocr", action="store_true")
    question = sub.add_parser("ask", help="Hỏi đáp theo mã chủ đề")
    question.add_argument("topic")
    question.add_argument("question")
    question.add_argument("--k", type=int)
    question.add_argument("--language", choices=list(LANGUAGES), default="vi")
    args = parser.parse_args()
    try:
        if args.command == "topics":
            result = list_topics()
        elif args.command == "create-topic":
            result = create_topic(args.name)
        elif args.command == "ask":
            result = ask(args.topic, args.question, k=args.k, answer_language=args.language)
        else:
            result = []
            failed = False
            for path in args.files:
                try:
                    result.append(ingest_pdf(args.topic, path, force_ocr=args.force_ocr))
                except Exception as exc:
                    failed = True
                    if not isinstance(exc, RAGError):
                        logging.exception("Import thất bại")
                    result.append({"file": path, "status": "error", "error": str(exc)
                                   if isinstance(exc, RAGError) else "Kiểm tra log và model embedding."})
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 1 if failed else 0
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except RAGError as exc:
        parser.exit(1, f"Lỗi: {exc}\n")
    except Exception:
        logging.exception("BIG_RAG gặp lỗi")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
