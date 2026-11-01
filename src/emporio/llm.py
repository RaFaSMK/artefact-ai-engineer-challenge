"""Único lugar que conhece os conectores e opções dos provedores."""

from langchain_core.language_models.chat_models import BaseChatModel

from .config import Settings


def build_model(settings: Settings) -> BaseChatModel:
    if settings.llm_provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=settings.llm_model, base_url=settings.llm_base_url,
            temperature=0, reasoning=settings.ollama_reasoning,
            num_ctx=settings.ollama_context_size, num_predict=settings.llm_max_output_tokens,
            keep_alive="15m", client_kwargs={"timeout": settings.llm_timeout_seconds},
        )
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model=settings.llm_model, base_url=settings.llm_base_url,
        api_key=settings.llm_api_key.get_secret_value(), timeout=settings.llm_timeout_seconds,
        max_retries=1, max_completion_tokens=settings.llm_max_output_tokens,
    )
