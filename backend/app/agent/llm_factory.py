"""
Builds the LLM client the API actually uses. Kept separate from
llm_client.py so swapping providers or adding config options doesn't touch
the client implementations themselves.
"""
from fastapi import HTTPException

from ..config import settings
from .llm_client import LLMClient, VertexAILLMClient

_cached_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """FastAPI dependency. Lazily constructs and caches the Vertex AI
    client. Client construction itself doesn't fail without credentials
    (auth happens lazily on the actual API call) — that failure is caught
    per-request in main.py's /chat endpoint instead, since it's a request-
    time concern (could recover if credentials are fixed), not a config
    problem to hide the whole route behind."""
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
    )
    return _cached_client
