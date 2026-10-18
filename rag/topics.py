"""Chủ đề dùng slug an toàn trên Windows; tên hiển thị giữ nguyên tiếng Việt."""

import json
import re
import shutil
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from filelock import FileLock

from rag.config import get_settings
from rag.errors import Conflict, InvalidInput, TopicNotFound
from rag.workspace import workspace_roots

WINDOWS_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
                    *(f"lpt{i}" for i in range(1, 10))}


def validate_topic(topic: str) -> str:
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", topic) or topic in WINDOWS_RESERVED:
        raise InvalidInput("Mã chủ đề chỉ gồm a-z, 0-9, dấu - hoặc _, tối đa 64 ký tự.")
    return topic


def slugify(name: str) -> str:
    text = unicodedata.normalize("NFKD", name.strip().lower().replace("đ", "d"))
    text = text.encode("ascii", "ignore").decode("ascii")
    return validate_topic(re.sub(r"[^a-z0-9]+", "-", text).strip("-"))


def topic_paths(topic: str) -> tuple[Path, Path]:
    topic = validate_topic(topic)
    data_root, vector_root = workspace_roots()
    return data_root / topic, vector_root / topic


def topic_lock(topic: str) -> FileLock:
    validate_topic(topic)
    folder = workspace_roots()[1] / ".locks"
    folder.mkdir(parents=True, exist_ok=True)
    return FileLock(str(folder / f"{topic}.lock"), timeout=600)


def require_topic(topic: str) -> tuple[Path, Path]:
    paths = topic_paths(topic)
    if not (paths[0] / ".topic.json").is_file():
        raise TopicNotFound(f"Không tìm thấy chủ đề '{topic}'. Hãy tạo chủ đề trước.")
    return paths


def create_topic(name: str) -> dict:
    name = name.strip()
    if not name or len(name) > 100:
        raise InvalidInput("Tên chủ đề phải có từ 1 đến 100 ký tự.")
    topic = slugify(name)
    data, vectors = topic_paths(topic)
    with topic_lock(topic):
        if (data / ".topic.json").exists():
            raise Conflict(f"Chủ đề '{topic}' đã tồn tại.")
        data.mkdir(parents=True, exist_ok=True)
        vectors.mkdir(parents=True, exist_ok=True)
        info = {"id": topic, "name": name, "created_at": datetime.now(timezone.utc).isoformat()}
        temp = data / ".topic.tmp"
        temp.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(data / ".topic.json")
    return {**info, "pdf_count": len(list(data.glob("*.pdf")))}


def list_topics() -> list[dict]:
    root = workspace_roots()[0]
    root.mkdir(parents=True, exist_ok=True)
    result = []
    for folder in sorted(root.iterdir()):
        manifest = folder / ".topic.json"
        if not folder.is_dir() or not manifest.is_file():
            continue
        validate_topic(folder.name)
        info = json.loads(manifest.read_text(encoding="utf-8"))
        result.append({**info, "id": folder.name, "pdf_count": len(list(folder.glob("*.pdf")))})
    return result


def delete_topic(topic: str) -> dict:
    from chromadb.errors import NotFoundError
    from rag.preview import delete_topic_previews
    from rag.vectorstore import COLLECTION, _client

    data, vectors = topic_paths(topic)
    # Resolve both targets before touching files; reject symlinks/junctions outside this workspace.
    for target, root in zip((data, vectors), workspace_roots()):
        if target.resolve().parent != root.resolve():
            raise InvalidInput("Đường dẫn thư viện không hợp lệ.")
    with topic_lock(topic):
        # Chroma owns its open SQLite files on Windows. Delete the collection through its API.
        # Keep the empty storage container so recreating this slug works with the cached client.
        if vectors.exists():
            try:
                _client(str(vectors)).delete_collection(COLLECTION)
            except NotFoundError:
                pass
        if data.exists():
            shutil.rmtree(data)
        delete_topic_previews(topic)
    return {"status": "deleted"}
