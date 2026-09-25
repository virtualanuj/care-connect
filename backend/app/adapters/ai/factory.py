from app.adapters.ai.dev_llm_provider import DevLLMProvider
from app.adapters.ai.gemini_llm_provider import GeminiLLMProvider
from app.config import Settings
from app.domain.ports import LLMProvider


def build_llm_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "fake":
        return DevLLMProvider()
    if settings.llm_provider == "fake-down":
        return DevLLMProvider(down=True)
    return GeminiLLMProvider(api_key=settings.gemini_api_key, model=settings.gemini_model)
