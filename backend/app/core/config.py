from functools import lru_cache
from typing import List, Optional, Union
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
    max_upload_mb: int = Field(default=50, description="Maximum upload size in MB")
    chunk_target_tokens: int = Field(default=400, description="Target token count per chunk")
    chunk_overlap_tokens: int = Field(default=50, description="Overlap token count between chunks")
    transcript_window_sec: int = Field(default=60, description="Target duration window in seconds for transcript chunks")
    auto_build_kb: bool = Field(default=True, description="Automatically build knowledge base on ingestion completion")
    kb_batch_tokens: int = Field(default=6000, description="Approximate token budget per KB LLM batch")
    kb_max_toplevel: int = Field(default=10, description="Maximum top-level topics in generated taxonomy")
    kb_max_subtopics: int = Field(default=5, description="Maximum subtopics per top-level topic")
    snippet_chars: int = Field(default=300, description="Character limit for citation snippets")
    tutor_top_k: int = Field(default=8, description="Number of chunks retrieved for tutor prompt")
    tutor_min_score: float = Field(default=0.50, description="Minimum similarity score threshold to avoid refusal")
    tutor_strong_score: float = Field(default=0.65, description="Similarity score threshold indicating strong evidence")
    tutor_history_turns: int = Field(default=6, description="Number of message pairs to include in context")
    tutor_context_chars: int = Field(default=1500, description="Maximum characters per chunk placed in prompt")
    tutor_mock_min_overlap: float = Field(default=0.20, description="Minimum lexical overlap for partial grounding in mock mode")
    quiz_max_questions: int = Field(default=20, description="Maximum questions in a quiz")
    exam_max_questions: int = Field(default=40, description="Maximum questions in a mock exam")
    diagnostic_questions: int = Field(default=8, description="Target question count for diagnostic assessment")
    quiz_context_chunks: int = Field(default=4, description="Max source chunks given to generator per topic")
    quiz_context_chars: int = Field(default=1200, description="Max characters per chunk in quiz prompt")
    quiz_dup_similarity: float = Field(default=0.90, description="Embedding similarity threshold for question deduplication")
    quiz_parallelism: int = Field(default=3, description="Max concurrent LLM calls during question generation")
    quiz_max_rounds: int = Field(default=2, description="Generation and verification rounds to fill shortfall")
    verify_model: Optional[str] = Field(default=None, description="Optional model name for verification")

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
