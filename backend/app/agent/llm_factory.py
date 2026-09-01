# builds the LLM client the API uses

from fastapi import HTTPException

from ..config import settings
from .llm_client import LLMClient, VertexAILLMClient

_cached_client: LLMClient | None = None

# constructs and caches the Vertex AI client
def get_llm_client() -> LLMClient:
    # client construction itself doesn't fail without credentials as authentication happens on API calls
    # this failure is caught in main.py /chat endpoint
    global _cached_client
    if _cached_client is not None:
        return _cached_client

    if not settings.GOOGLE_CLOUD_PROJECT:
        raise HTTPException(
            status_code=503,
            detail="GOOGLE_CLOUD_PROJECT is not set. The rest of the API works without it — only /chat needs it.",
        )

    _cached_client = VertexAILLMClient(
        project=settings.GOOGLE_CLOUD_PROJECT,
        location=settings.GOOGLE_CLOUD_LOCATION,
        model=settings.GEMINI_MODEL,
        thinking_budget=settings.GEMINI_THINKING_BUDGET,
        thinking_level=settings.GEMINI_THINKING_LEVEL
    )
    return _cached_client
