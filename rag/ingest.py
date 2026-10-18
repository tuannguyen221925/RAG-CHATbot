"""Import từng PDF dưới khóa topic; rollback vector nếu import thất bại."""

import hashlib
import json
import re
from pathlib import Path
from tempfile import NamedTemporaryFile

from rag.chunking import chunk_documents
from rag.config import get_settings
from rag.errors import Conflict, InvalidInput
from rag.loader import load_pdf
from rag.topics import WINDOWS_RESERVED, require_topic, topic_lock
from rag.vectorstore import get_collection, get_vectorstore


def validate_pdf_name(filename: str) -> str:
    # Không nhận đường dẫn từ HTTP; CLI truyền Path.name.
    if (not filename or len(filename) > 180 or filename != filename.strip()
            or re.search(r'[<>:"/\\|?*\x00-\x1f]', filename)
            or not filename.lower().endswith(".pdf")
            or filename.split(".")[0].lower() in WINDOWS_RESERVED):
        raise InvalidInput("Tên file PDF không hợp lệ. Chỉ truyền tên file, không truyền đường dẫn.")
    return filename[:-4] + ".pdf"


def validate_pdf_content(content: bytes):
    settings = get_settings()
    if not content or len(content) > settings.max_upload_bytes:
        raise InvalidInput(f"File rỗng hoặc vượt giới hạn {settings.max_upload_mb} MB.")
    if b"%PDF-" not in content[:1024]:
        raise InvalidInput("File không có header PDF hợp lệ.")


def ingest_pdf_bytes(topic: str, filename: str, content: bytes, *, force_ocr: bool = False,
                     prepared=None, index_mode: str = "original") -> dict:
    filename = validate_pdf_name(filename)
    validate_pdf_content(content)
    data, _ = require_topic(topic)
    if index_mode not in ("original", "translated"):
        raise InvalidInput("index_mode phải là original hoặc translated.")
    if prepared is not None:
        from rag.preview import PreparedPDF
        if not isinstance(prepared, PreparedPDF) or prepared.filename != filename or prepared.content != content:
            raise InvalidInput("Bản xem trước không khớp PDF đang import.")
    if index_mode == "translated" and (prepared is None or not prepared.translated):
        raise InvalidInput("Hãy dịch và xem trước toàn bộ PDF trước khi import bản dịch.")
    signature = "original"
    if index_mode == "translated":
        signature = hashlib.sha256(json.dumps(
            [prepared.target_language, [(doc.metadata["page"], doc.page_content) for doc in prepared.translated]],
            ensure_ascii=False).encode("utf-8")).hexdigest()
    digest = hashlib.sha256(content).hexdigest()
    with topic_lock(topic):
        collection = get_collection(topic)
        existing = collection.get(where={"file_sha256": digest}, include=["metadatas"])
        if existing["ids"]:
            metadata = existing["metadatas"][0]
            if metadata.get("index_signature", "original") != signature:
                raise Conflict("PDF đã được lập chỉ mục với nội dung/ngôn ngữ khác. "
                               "Tạo chủ đề khác để import bản mới; bản cũ được giữ nguyên.")
            return {"file": metadata["source"], "topic": topic, "status": "skipped",
                    "chunks": len(existing["ids"]), "pages": 0, "ocr_pages": 0}
        target = data / filename
        # Windows không phân biệt chữ hoa/thường; áp dụng cùng quy tắc ở mọi OS.
        names = {p.name.casefold(): p for p in data.glob("*.pdf")}
        if filename.casefold() in names:
            target = names[filename.casefold()]
            if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                raise Conflict(f"File '{target.name}' đã tồn tại với nội dung khác. Hãy đổi tên file.")
            filename = target.name
        ids = []
        newly_saved = False
        sidecar_saved = False
        sidecar_temp = None
        sidecar = data / ".translations" / f"{digest}.json"
        with NamedTemporaryFile(dir=data, suffix=".upload", delete=False) as handle:
            handle.write(content)
            temp = Path(handle.name)
        try:
            pages = (list(prepared.translated if index_mode == "translated" else prepared.original)
                     if prepared else load_pdf(temp, source_name=filename, force_ocr=force_ocr))
            chunks = chunk_documents(pages)
            if not chunks:
                raise InvalidInput("Không tạo được đoạn văn bản từ PDF.")
            for index, chunk in enumerate(chunks):
                chunk.metadata.update({"source": filename, "topic": topic, "file_sha256": digest,
                                       "chunk_index": index, "index_signature": signature,
                                       "translated": index_mode == "translated",
                                       "language": prepared.target_language if index_mode == "translated"
                                       else prepared.source_language if prepared else "auto"})
            ids = [f"{digest}:{index}" for index in range(len(chunks))]
            store = get_vectorstore(topic)
            for start in range(0, len(chunks), 64):
                store.add_documents(chunks[start:start + 64], ids=ids[start:start + 64])
            if prepared and prepared.translated:
                if sidecar.exists():
                    raise Conflict("Đã có bản dịch lưu cho PDF này. Kiểm tra dữ liệu trước khi import lại.")
                sidecar.parent.mkdir(parents=True, exist_ok=True)
                with NamedTemporaryFile(dir=sidecar.parent, suffix=".tmp", delete=False) as handle:
                    sidecar_temp = Path(handle.name)
                    handle.write(json.dumps(prepared.as_dict(), ensure_ascii=False, indent=2).encode("utf-8"))
                sidecar_temp.replace(sidecar)
                sidecar_saved = True
            if not target.exists():
                temp.replace(target)
                newly_saved = True
            return {"file": filename, "topic": topic, "status": "indexed", "chunks": len(chunks),
                    "pages": len(pages), "ocr_pages": sum(bool(p.metadata["ocr"]) for p in pages),
                    "total_pages": pages[0].metadata.get("pdf_total_pages", len(pages)),
                    "empty_pages": [int(p) for p in pages[0].metadata.get("pdf_empty_pages", "").split(',') if p],
                    "index_mode": index_mode, "language": prepared.target_language
                    if index_mode == "translated" else prepared.source_language if prepared else "auto"}
        except Exception:
            if ids:
                for start in range(0, len(ids), 64):
                    collection.delete(ids=ids[start:start + 64])
            if newly_saved:
                target.unlink(missing_ok=True)
            if sidecar_saved:
                sidecar.unlink(missing_ok=True)
            raise
        finally:
            temp.unlink(missing_ok=True)
            if sidecar_temp:
                sidecar_temp.unlink(missing_ok=True)


def ingest_prepared(topic: str, prepared, *, index_mode: str = "original") -> dict:
    return ingest_pdf_bytes(topic, prepared.filename, prepared.content, prepared=prepared, index_mode=index_mode)


def ingest_pdf(topic: str, path: str | Path, *, force_ocr: bool = False) -> dict:
    path = Path(path)
    if not path.is_file():
        raise InvalidInput(f"Không tìm thấy file: {path}")
    with path.open("rb") as handle:
        content = handle.read(get_settings().max_upload_bytes + 1)
    return ingest_pdf_bytes(topic, path.name, content, force_ocr=force_ocr)
