# central configuration: Reads from environment variables (.env) but has defaults set
import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Comma-separated list of allowed frontend origins. Never use "*"
    # once cookies/auth are involved; kept permissive here only for
    # local dev.
    CORS_ORIGINS: list[str] = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
        if origin.strip()
    ]

    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "25"))
    MAX_UPLOAD_SIZE_BYTES: int = MAX_UPLOAD_SIZE_MB * 1024 * 1024

    ALLOWED_EXTENSIONS: set[str] = {".csv", ".xlsx", ".xls"}


    # how long an uploaded dataset stays in memory before its deleted
    DATASET_TTL_HOURS: float = float(os.getenv("DATASET_TTL_HOURS", "2"))

    # Column type-conversion thresholds: fraction of non-null values that
    # must successfully convert before we trust the inferred type.
    NUMERIC_CONVERSION_THRESHOLD: float = 0.9
    DATE_CONVERSION_THRESHOLD: float = 0.8

    # Row-null threshold for flagging a column as low quality.
    HIGH_NULL_WARNING_THRESHOLD: float = 0.3


    # GEMINI_THINKING_BUDGET for 2.x generation models
    # GEMINI_THINKING_LEVEL for 3.x generation models
    GOOGLE_CLOUD_PROJECT: str = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    GOOGLE_CLOUD_LOCATION: str = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    GEMINI_THINKING_BUDGET: int | None = (
        int(os.getenv("GEMINI_THINKING_BUDGET")) if os.getenv("GEMINI_THINKING_BUDGET") else None
    )
    GEMINI_THINKING_LEVEL: str | None = os.getenv("GEMINI_THINKING_LEVEL") or None

settings = Settings()
