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
    bkt_p_init: float = Field(default=0.30, description="Prior mastery for a student with no history on a topic")
    bkt_p_learn: float = Field(default=0.15, description="Probability of learning on each opportunity")
    bkt_p_slip: float = Field(default=0.10, description="Base slip probability")
    bkt_guess_mcq: float = Field(default=0.25, description="Guess probability for MCQ")
    bkt_guess_short: float = Field(default=0.10, description="Guess probability for short answer")
    bkt_guess_numerical: float = Field(default=0.05, description="Guess probability for numerical questions")
    bkt_min: float = Field(default=0.02, description="Minimum clamped mastery probability")
    bkt_max: float = Field(default=0.98, description="Maximum clamped mastery probability")
    grade_correct_threshold: float = Field(default=0.70, description="Score threshold to count as correct")
    mastery_weak_below: float = Field(default=0.40, description="Mastery threshold below which topic is weak")
    mastery_strong_above: float = Field(default=0.75, description="Mastery threshold above which topic is strong")
    feedback_max_chars: int = Field(default=700, description="Maximum characters for feedback text")
    forget_base_days: float = Field(default=3.0, description="Memory stability with 0 correct answers")
    forget_per_correct: float = Field(default=0.5, description="Stability multiplier increment per correct answer")
    forget_max_days: float = Field(default=60.0, description="Maximum stability in days")
    review_due_below: float = Field(default=0.70, description="Retrievability below which a topic is due for review")
    prereq_ok_above: float = Field(default=0.50, description="Effective mastery at/above which a prerequisite counts as satisfied")
    chat_nudge_enabled: bool = Field(default=True, description="Enable mastery nudge on grounded tutor answers")
    chat_nudge_delta: float = Field(default=0.02, description="Mastery bump per grounded tutor answer on a topic")
    chat_nudge_cap: float = Field(default=0.55, description="Maximum stored mastery achievable via chat alone")
    chat_nudge_max_per_topic_per_day: int = Field(default=3, description="Maximum chat nudges per student topic per day")
    chat_struggle_asks: int = Field(default=3, description="Tutor questions on a topic within 7 days signalling struggle")
    tutor_personalize: bool = Field(default=True, description="Personalize tutor depth by student topic mastery")
    dash_recent_attempts: int = Field(default=10, description="Recent attempts displayed on student dashboard")
    study_session_min: int = Field(default=20, description="Study plan block length in minutes")
    llm_timeout_sec: int = Field(default=60, description="LLM call timeout in seconds")
    ingest_max_concurrent: int = Field(default=2, description="Max concurrent background ingestion jobs")
    slow_request_ms: int = Field(default=2000, description="Threshold in ms to log slow requests as warning")
    image_caption_enabled: bool = Field(default=False, description="Enable slide and figure image captioning")
    image_caption_model: Optional[str] = Field(default=None, description="Model to use for image captioning (fallback llm_model)")
    image_caption_max_per_source: int = Field(default=30, description="Max images captioned per source")
    image_min_px: int = Field(default=150, description="Min width/height in px for captioning")
    eval_judge_model: Optional[str] = Field(default=None, description="Model to use as evaluation judge (fallback llm_model)")
    eval_out_dir: str = Field(default="./eval/results", description="Output directory for eval results")
    auth_required: bool = Field(default=True, description="Require authentication for protected endpoints")
    jwt_secret: str = Field(default="change-me-in-.env", description="Secret key for JWT signing")
    jwt_algorithm: str = Field(default="HS256", description="Algorithm for JWT signing")
    jwt_expire_minutes: int = Field(default=10080, description="JWT expiration in minutes (7 days default)")
    auth_max_failed_attempts: int = Field(default=5, description="Maximum failed login attempts before lockout")
    auth_lockout_minutes: int = Field(default=15, description="Lockout duration in minutes")

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
