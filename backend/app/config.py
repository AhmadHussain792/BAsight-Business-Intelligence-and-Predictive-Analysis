"""
Central configuration. Reads from environment variables with sane
development defaults so the app runs out of the box, but everything
here should be overridden via .env / real env vars in production.
"""
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

    # How long an uploaded dataset stays in memory before it's evicted.
    DATASET_TTL_HOURS: float = float(os.getenv("DATASET_TTL_HOURS", "2"))

    # Column type-conversion thresholds: fraction of non-null values that
    # must successfully convert before we trust the inferred type.
    NUMERIC_CONVERSION_THRESHOLD: float = 0.9
    DATE_CONVERSION_THRESHOLD: float = 0.8

    # Row-null threshold for flagging a column as low quality.
    HIGH_NULL_WARNING_THRESHOLD: float = 0.3


settings = Settings()
