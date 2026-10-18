"""Cấu hình chung, luôn giải đường dẫn tương đối từ thư mục dự án."""

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=False)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", case_sensitive=False)

    data_dir: Path = ROOT / "data"
    vector_db_dir: Path = ROOT / "vector_db"
    rag_service_token: SecretStr = SecretStr("")
    groq_api_key: SecretStr = SecretStr("")
    groq_model: str = "qwen/qwen3.8-27b"
    translation_model: str = "qwen/qwen3.8-27b"
    groq_reasoning_effort: str = "auto"
    translation_reasoning_effort: str = "auto"
    google_translate_api_key: SecretStr = SecretStr("")
    translation_chunk_size: int = Field(default=1800, ge=200, le=4000)
    max_translation_chars: int = Field(default=200000, ge=1000, le=2000000)
    embedding_model: str = "intfloat/multilingual-e5-small"
    embedding_device: str = "cpu"
    embedding_batch_size: int = Field(default=16, ge=1, le=256)
    ocr_gpu: bool = False
    ocr_dpi: int = Field(default=200, ge=72, le=400)
    ocr_min_text_chars: int = Field(default=40, ge=0)
    ocr_page_timeout: int = Field(default=120, ge=10, le=600)
    ocr_batch_size: int = Field(default=4, ge=1, le=16)
    ocr_engine: str = 'easyocr'
    poppler_path: str = ""
    chunk_size: int = Field(default=900, ge=100, le=2000)
    chunk_overlap: int = Field(default=150, ge=0)
    chunk_unit: str = "tokens"
    chunk_tokens: int = Field(default=480, ge=64, le=8192)
    chunk_overlap_tokens: int = Field(default=72, ge=0)
    retrieval_k: int = Field(default=4, ge=1, le=12)
    max_context_chunks: int = Field(default=12, ge=1, le=12)
    context_token_budget: int = Field(default=1800, ge=128, le=16000)
    max_input_tokens: int = Field(default=3000, ge=512, le=32000)
    rerank_enabled: bool = False
    rerank_candidates: int = Field(default=20, ge=5, le=100)
    rerank_model: str = "BAAI/bge-reranker-v2-m3"
    rerank_device: str = "cpu"
    max_upload_mb: int = Field(default=50, ge=1, le=500)
    max_pdf_pages: int = Field(default=300, ge=1)
    max_output_tokens: int = Field(default=1024, ge=128, le=4096)

    @model_validator(mode="after")
    def validate_settings(self):
        if self.ocr_engine not in ('easyocr', 'paddle'):
            raise ValueError('OCR_ENGINE phải là easyocr hoặc paddle.')
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("CHUNK_OVERLAP phải nhỏ hơn CHUNK_SIZE.")
        if self.chunk_unit not in ("tokens", "characters"):
            raise ValueError("CHUNK_UNIT phải là tokens hoặc characters.")
        if self.chunk_overlap_tokens >= self.chunk_tokens:
            raise ValueError("CHUNK_OVERLAP_TOKENS phải nhỏ hơn CHUNK_TOKENS.")
        if self.context_token_budget >= self.max_input_tokens:
            raise ValueError("CONTEXT_TOKEN_BUDGET phải nhỏ hơn MAX_INPUT_TOKENS.")
        for name in ("data_dir", "vector_db_dir"):
            path = getattr(self, name)
            setattr(self, name, (ROOT / path).resolve() if not path.is_absolute() else path.resolve())
        return self

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    def resolve_poppler(self) -> str | None:
        if self.poppler_path.strip():
            path = Path(self.poppler_path).expanduser()
            return str((ROOT / path).resolve() if not path.is_absolute() else path)
        # Tận dụng bản Poppler người dùng đã giải nén trong dự án Windows.
        matches = sorted(ROOT.glob("Release-*/poppler-*/Library/bin/pdftoppm.exe"))
        return str(matches[-1].parent) if matches else None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
