import hashlib
import json
import logging
from functools import lru_cache
from typing import Any, List, Literal, Optional, Type, TypeVar, get_args, get_origin, Union
import numpy as np
import pydantic
from pydantic import BaseModel
from pydantic_core import PydanticUndefined

from app.core.config import Settings, get_settings
from app.core.errors import AppError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """Wrapper around Gemini API (via google-genai) with full mock support."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._mock = settings.llm_mock
        self._client: Any = None

        if self._mock:
            logger.warning(
                "LLMClient initialized in MOCK mode (LLM_MOCK=True). "
                "Deterministic mock outputs will be returned without calling Gemini API."
            )
        else:
            try:
                from google import genai
                self._client = genai.Client(api_key=settings.gemini_api_key)
            except Exception as exc:
                logger.error("Failed to initialize Google GenAI Client: %s", exc)
                raise AppError(
                    message=f"Failed to initialize Gemini client: {exc}",
                    code="llm_error",
                    status_code=500,
                )

    def generate_text(self, prompt: str, system: Optional[str] = None) -> str:
        """Generate plain text completion."""
        if self._mock:
            prompt_snip = prompt.strip().replace("\n", " ")[:60]
            return f"Mock LLM response for prompt: {prompt_snip}"

        try:
            from google.genai import types

            config = (
                types.GenerateContentConfig(system_instruction=system)
                if system
                else None
            )
            response = self._client.models.generate_content(
                model=self._settings.llm_model,
                contents=prompt,
                config=config,
            )
            return response.text or ""
        except Exception as exc:
            logger.exception("Gemini generate_text failed: %s", exc)
            raise AppError(
                message=f"LLM generation failed: {exc}",
                code="llm_error",
                status_code=502,
            )

    def generate_json(
        self,
        prompt: str,
        schema: Type[T],
        system: Optional[str] = None,
        max_retries: int = 2,
    ) -> T:
        """Generate structured output adhering to a Pydantic schema with retry on invalid output."""
        if self._mock:
            return self._build_mock_instance(schema)

        from google.genai import types

        current_prompt = prompt
        last_error: Optional[Exception] = None

        for attempt in range(max_retries + 1):
            try:
                config = types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schema,
                    system_instruction=system,
                )
                response = self._client.models.generate_content(
                    model=self._settings.llm_model,
                    contents=current_prompt,
                    config=config,
                )
                raw_text = response.text or "{}"
                return schema.model_validate_json(raw_text)
            except (pydantic.ValidationError, ValueError, json.JSONDecodeError) as val_err:
                last_error = val_err
                logger.warning(
                    "LLM JSON validation error on attempt %d: %s",
                    attempt + 1,
                    val_err,
                )
                if attempt < max_retries:
                    current_prompt = (
                        f"{prompt}\n\n"
                        f"[Notice: Previous output attempt failed with validation error: {val_err}. "
                        f"Ensure response strictly conforms to the requested schema.]"
                    )
            except Exception as exc:
                logger.exception("Gemini generate_json call error: %s", exc)
                raise AppError(
                    message=f"LLM API request failed: {exc}",
                    code="llm_error",
                    status_code=502,
                )

        raise AppError(
            message=f"Failed to produce valid JSON output conforming to {schema.__name__}: {last_error}",
            code="llm_invalid_output",
            status_code=502,
        )

    def embed_texts(
        self, texts: List[str], task: Literal["document", "query"] = "document"
    ) -> List[List[float]]:
        """Compute text embeddings in batches (max 50 per batch)."""
        if not texts:
            return []

        if self._mock:
            return [self._mock_embedding(t) for t in texts]

        from google.genai import types

        batch_size = 50
        results: List[List[float]] = []
        task_type = "RETRIEVAL_DOCUMENT" if task == "document" else "RETRIEVAL_QUERY"

        try:
            for i in range(0, len(texts), batch_size):
                batch = texts[i : i + batch_size]
                config = types.EmbedContentConfig(task_type=task_type)
                response = self._client.models.embed_content(
                    model=self._settings.embedding_model,
                    contents=batch,
                    config=config,
                )
                for emb in response.embeddings:
                    results.append(list(emb.values))
            return results
        except Exception as exc:
            logger.exception("Gemini embed_texts failed: %s", exc)
            raise AppError(
                message=f"Embedding generation failed: {exc}",
                code="llm_error",
                status_code=502,
            )

    def _mock_embedding(self, text: str, dim: int = 64) -> List[float]:
        """Compute deterministic 64-dim unit vector derived from SHA256 hash of text."""
        seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")
        rng = np.random.default_rng(seed)
        vec = rng.standard_normal(dim)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return [float(x) for x in vec]

    def _build_mock_instance(self, schema: Type[T]) -> T:
        """Best-effort reconstruction of dummy instance conforming to schema."""
        try:
            return schema.model_validate({})
        except Exception:
            pass

        values: dict[str, Any] = {}
        for field_name, field_info in schema.model_fields.items():
            if field_info.default is not PydanticUndefined and field_info.default is not None:
                values[field_name] = field_info.default
            elif field_info.default_factory is not None:
                values[field_name] = field_info.default_factory()
            else:
                values[field_name] = self._mock_field_value(
                    field_name, field_info.annotation
                )
        return schema(**values)

    def _mock_field_value(self, field_name: str, field_type: Any) -> Any:
        """Construct fallback value based on type annotation."""
        origin = get_origin(field_type)
        if origin is Union:
            args = [a for a in get_args(field_type) if a is not type(None)]
            return self._mock_field_value(field_name, args[0]) if args else None
        if origin in (list, List):
            return []
        if origin in (dict, dict):
            return {}
        if isinstance(field_type, type) and issubclass(field_type, BaseModel):
            return self._build_mock_instance(field_type)
        if field_type is int:
            return 1
        if field_type is float:
            return 1.0
        if field_type is bool:
            return True
        if field_type is str:
            return f"mock_{field_name}"
        return None


@lru_cache
def get_llm_client() -> LLMClient:
    """Dependency / singleton provider for LLMClient."""
    settings = get_settings()
    return LLMClient(settings)
