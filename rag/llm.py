from functools import lru_cache

from langchain_groq import ChatGroq

from rag.config import get_settings
from rag.errors import ConfigurationError
from rag.model_options import reasoning_options


@lru_cache(maxsize=1)
def get_llm() -> ChatGroq:
    settings = get_settings()
    key = settings.groq_api_key.get_secret_value().strip()
    if not key or key == "your_groq_api_key_here":
        raise ConfigurationError("Chưa có GROQ_API_KEY hợp lệ trong .env.")
    return ChatGroq(model=settings.groq_model, api_key=key, temperature=0,
                    max_tokens=settings.max_output_tokens, timeout=60, max_retries=2,
                    **reasoning_options(settings.groq_model, settings.groq_reasoning_effort))
