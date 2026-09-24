import os
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    COMPOSIO_API_KEY: str = Field(default="")
    GEMINI_API_KEY: str = Field(default="")
    VERIFIER_API_KEY: str = Field(default="")
    
    MAX_CONCURRENCY: int = Field(default=10)
    CACHE_DIR: Path = Field(default=Path("data/cache"))
    GEMINI_MODEL: str = Field(default="gemini-2.5-flash")
    VERIFIER_MODEL: str = Field(default="gemini-2.5-pro")
    
    REQUEST_TIMEOUT: float = Field(default=30.0)
    USER_AGENT: str = Field(
        default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )


settings = Settings()
