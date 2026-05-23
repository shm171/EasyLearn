from __future__ import annotations

"""Model factory for chat and embedding providers."""

from functools import lru_cache
from typing import Any

from ai_core.config import get_settings


def _require_key(value: str | None, env_name: str) -> str:
    if not value:
        raise RuntimeError(f"Missing required environment variable: {env_name}")
    return value


def get_chat_model(provider: str | None = None) -> Any:
    """Create a chat model for openai, gemini, or deepseek."""

    settings = get_settings()
    selected = (provider or settings.ai_provider).lower()
    return _get_chat_model_cached(selected)


@lru_cache(maxsize=4)
def _get_chat_model_cached(selected: str) -> Any:
    settings = get_settings()

    if selected == "openai":
        _require_key(settings.openai_api_key, "OPENAI_API_KEY")
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as exc:
            raise RuntimeError("Install langchain-openai to use OpenAI chat models.") from exc
        return ChatOpenAI(model=settings.openai_model, temperature=0.2)

    if selected == "gemini":
        _require_key(settings.google_api_key, "GOOGLE_API_KEY")
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError as exc:
            raise RuntimeError("Install langchain-google-genai to use Gemini chat models.") from exc
        return ChatGoogleGenerativeAI(model=settings.gemini_model, temperature=0.2)

    if selected == "deepseek":
        _require_key(settings.deepseek_api_key, "DEEPSEEK_API_KEY")
        try:
            from langchain_deepseek import ChatDeepSeek
        except ImportError as exc:
            raise RuntimeError("Install langchain-deepseek to use DeepSeek chat models.") from exc
        return ChatDeepSeek(model=settings.deepseek_model, temperature=0.2)

    raise ValueError(f"Unsupported AI provider: {selected}")


def get_embedding_model(provider: str | None = None) -> Any:
    """Create an embedding model for openai, gemini, or huggingface."""

    settings = get_settings()
    selected = (provider or settings.embedding_provider).lower()
    return _get_embedding_model_cached(selected)


@lru_cache(maxsize=4)
def _get_embedding_model_cached(selected: str) -> Any:
    settings = get_settings()

    if selected == "openai":
        _require_key(settings.openai_api_key, "OPENAI_API_KEY")
        try:
            from langchain_openai import OpenAIEmbeddings
        except ImportError as exc:
            raise RuntimeError("Install langchain-openai to use OpenAI embeddings.") from exc
        return OpenAIEmbeddings(model=settings.openai_embedding_model)

    if selected == "gemini":
        _require_key(settings.google_api_key, "GOOGLE_API_KEY")
        try:
            from langchain_google_genai import GoogleGenerativeAIEmbeddings
        except ImportError as exc:
            raise RuntimeError("Install langchain-google-genai to use Gemini embeddings.") from exc
        return GoogleGenerativeAIEmbeddings(model=settings.gemini_embedding_model)

    if selected == "huggingface":
        try:
            from langchain_huggingface import HuggingFaceEmbeddings
        except ImportError as exc:
            raise RuntimeError(
                "Install langchain-huggingface and sentence-transformers to use local HuggingFace embeddings."
            ) from exc
        return HuggingFaceEmbeddings(
            model_name=settings.huggingface_embedding_model,
            cache_folder=settings.huggingface_cache_folder,
            show_progress=False,
        )

    if selected == "deepseek":
        raise ValueError(
            "DeepSeek is supported only as a chat provider, not as an embedding provider. "
            "Please set EMBEDDING_PROVIDER=huggingface, openai, or gemini."
        )

    raise ValueError(f"Unsupported embedding provider: {selected}")


