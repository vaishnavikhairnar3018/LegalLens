"""
LenseScan Backend Configuration.
All secrets loaded from environment variables via .env file.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # --- Application ---
    APP_NAME: str = "LenseScan API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # --- Security ---
    SECRET_KEY: str = "lensescan_super_secret_dev_key_64_bytes_long_random_string_for_testing_123456789"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # --- Database (PostgreSQL) ---
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/lensescan_db"

    # --- CORS ---
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    # --- Upload Limits ---
    MAX_UPLOAD_SIZE_MB: int = 10

    # --- OCR ---
    OCR_LANGUAGES: str = "en,hi"
    DEFAULT_DPI: int = 300

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @property
    def allowed_origins_list(self) -> List[str]:
        """Parse comma-separated origins into a list."""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]

    @property
    def ocr_languages_list(self) -> List[str]:
        """Parse comma-separated OCR language codes into a list."""
        return [lang.strip() for lang in self.OCR_LANGUAGES.split(",")]

    @property
    def max_upload_size_bytes(self) -> int:
        """Convert MB limit to bytes."""
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @property
    def max_request_size_bytes(self) -> int:
        """Whole request: up to 8 photos at the per-photo limit, plus 1 MB for the other form fields."""
        return (8 * self.MAX_UPLOAD_SIZE_MB + 1) * 1024 * 1024


@lru_cache()
def get_settings() -> Settings:
    """Cached settings singleton. Call this instead of Settings() directly."""
    return Settings()
