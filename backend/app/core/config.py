from functools import lru_cache
from typing import Union, List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    gemini_api_key: str = Field(default="", description="Gemini API Key")
    llm_model: str = Field(default="gemini-2.5-flash", description="Gemini text model")
    embedding_model: str = Field(default="gemini-embedding-001", description="Gemini embedding model")
    llm_mock: bool = Field(default=True, description="Enable mock mode for LLM and embeddings")
    database_url: str = Field(default="sqlite:///./storage/folio.db", description="Database connection URL")
    upload_dir: str = Field(default="./storage/uploads", description="Directory to store uploaded course assets")
    chroma_dir: str = Field(default="./storage/chroma", description="Persistent directory for ChromaDB")
    cors_origins: Union[str, List[str]] = Field(
        default="http://localhost:3000,http://localhost:5173",
        description="Allowed CORS origins (comma-separated string or list)",
    )
    debug: bool = Field(default=True, description="Enable debug mode and dev endpoints")

    @property
    def parsed_cors_origins(self) -> List[str]:
        """Return CORS origins as a list of strings."""
        if isinstance(self.cors_origins, list):
            return self.cors_origins
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Singleton getter for application settings."""
    return Settings()
