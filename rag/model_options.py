"""Chỉ gửi tham số reasoning mà model Groq hỗ trợ."""

from rag.errors import ConfigurationError


def reasoning_options(model: str, effort: str = "auto") -> dict:
    allowed = ({"low", "medium", "high"} if model in
               {"openai/gpt-oss-20b", "openai/gpt-oss-120b"} else
               {"none", "low", "medium", "high"} if model == "qwen/qwen3.8-27b" else set())
    if effort == "auto":
        effort = "none" if model == "qwen/qwen3.8-27b" else "low" if allowed else "provider"
    if effort == "provider":
        return {}
    if effort not in allowed:
        raise ConfigurationError(f"REASONING_EFFORT={effort} không được hỗ trợ cho {model}. "
                                 "Dùng auto hoặc provider.")
    return {"reasoning_effort": effort}
