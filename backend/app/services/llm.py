import hashlib
import json
import logging
import re
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

    def _call_with_backoff(self, operation: Any, *args: Any, **kwargs: Any) -> Any:
        """Execute a callable with exponential backoff on transient and rate limit errors (3 retries)."""
        import concurrent.futures
        import time

        delays = [2.0, 4.0, 8.0]
        last_exc: Optional[Exception] = None
        timeout_sec = self._settings.llm_timeout_sec

        for attempt in range(len(delays) + 1):
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(operation, *args, **kwargs)
                    try:
                        return future.result(timeout=timeout_sec)
                    except concurrent.futures.TimeoutError as te:
                        raise TimeoutError(f"LLM call timed out after {timeout_sec}s") from te
            except Exception as exc:
                last_exc = exc
                err_str = str(exc).lower()
                is_transient = any(
                    token in err_str
                    for token in ["429", "503", "quota", "rate limit", "resourceexhausted", "unavailable", "timeout", "timed out"]
                )
                if attempt < len(delays) and is_transient:
                    sleep_sec = delays[attempt]
                    logger.warning(
                        "LLM transient/rate-limit error: %s. Retrying in %.1fs (attempt %d/%d)...",
                        exc,
                        sleep_sec,
                        attempt + 1,
                        len(delays),
                    )
                    time.sleep(sleep_sec)
                else:
                    break

        if last_exc:
            err_str = str(last_exc).lower()
            if "timeout" in err_str or "timed out" in err_str:
                raise AppError(
                    message="The AI model took too long to respond. Please try again.",
                    code="llm_timeout",
                    status_code=502,
                )
            if any(token in err_str for token in ["429", "quota", "rate limit", "resourceexhausted"]):
                raise AppError(
                    message="Rate limit reached. Please retry in a minute.",
                    code="llm_error",
                    status_code=502,
                )
            raise AppError(
                message=f"LLM operation failed: {last_exc}",
                code="llm_error",
                status_code=502,
            )

    def caption_image(
        self,
        image_bytes: bytes,
        mime: str,
        model: Optional[str] = None,
        context_hint: Optional[str] = None,
    ) -> str:
        """Caption figure/slide image using Gemini multimodal vision."""
        if self._mock:
            snip = (context_hint or "diagram").strip()[:40]
            return f"(mock) Figure: diagram showing {snip}"

        from google.genai import types

        caption_model = model or self._settings.image_caption_model or self._settings.llm_model
        prompt = (
            "Provide a factual description of this figure/diagram in 2-4 sentences. "
            "Transcribe visible text, labels, axes, and equations accurately without speculation. "
            "If this image is purely decorative (e.g. background pattern, icon, logo, divider), "
            "respond ONLY with the single word DECORATIVE."
        )

        def _call():
            return self._client.models.generate_content(
                model=caption_model,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type=mime),
                    prompt,
                ],
            )

        response = self._call_with_backoff(_call)
        return (response.text or "").strip()

    def generate_text(
        self, prompt: str, system: Optional[str] = None, model: Optional[str] = None
    ) -> str:
        """Generate plain text completion."""
        if self._mock:
            prompt_snip = prompt.strip().replace("\n", " ")[:60]
            return f"Mock LLM response for prompt: {prompt_snip}"

        from google.genai import types

        config = (
            types.GenerateContentConfig(system_instruction=system)
            if system
            else None
        )
        target_model = model or self._settings.llm_model

        def _call():
            return self._client.models.generate_content(
                model=target_model,
                contents=prompt,
                config=config,
            )

        response = self._call_with_backoff(_call)
        return response.text or ""

    def generate_json(
        self,
        prompt: str,
        schema: Type[T],
        system: Optional[str] = None,
        max_retries: int = 2,
        model: Optional[str] = None,
    ) -> T:
        """Generate structured output adhering to a Pydantic schema with retry on invalid output."""
        if self._mock:
            return self._build_mock_instance(schema)

        from google.genai import types

        current_prompt = prompt
        last_error: Optional[Exception] = None
        target_model = model or self._settings.llm_model

        for attempt in range(max_retries + 1):
            try:
                config = types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schema,
                    system_instruction=system,
                )
                def _call():
                    return self._client.models.generate_content(
                        model=target_model,
                        contents=current_prompt,
                        config=config,
                    )

                response = self._call_with_backoff(_call)
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
            except AppError:
                raise
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

                def _call_embed():
                    return self._client.models.embed_content(
                        model=self._settings.embedding_model,
                        contents=batch,
                        config=config,
                    )

                response = self._call_with_backoff(_call_embed)
                for emb in response.embeddings:
                    results.append(list(emb.values))
            return results
        except AppError as app_err:
            if "rate limit" in app_err.message.lower() or "quota" in app_err.message.lower():
                raise AppError(
                    message="Embedding failed: rate limit reached. Please retry in a minute.",
                    code="llm_error",
                    status_code=502,
                )
            raise
        except Exception as exc:
            err_str = str(exc).lower()
            if any(token in err_str for token in ["429", "quota", "rate limit", "resourceexhausted"]):
                raise AppError(
                    message="Embedding failed: rate limit reached. Please retry in a minute.",
                    code="llm_error",
                    status_code=502,
                )
            logger.exception("Gemini embed_texts failed: %s", exc)
            raise AppError(
                message=f"Embedding generation failed: {exc}",
                code="llm_error",
                status_code=502,
            )

    def _mock_embedding(self, text: str, dim: int = 64) -> List[float]:
        """Compute deterministic 64-dim unit vector derived from word tokens."""
        words = set(re.findall(r"\b[a-zA-Z0-9]+\b", text.lower()))
        if not words:
            seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")
            rng = np.random.default_rng(seed)
            vec = rng.standard_normal(dim)
        else:
            vec = np.zeros(dim, dtype=float)
            for w in words:
                w_seed = int.from_bytes(hashlib.sha256(w.encode("utf-8")).digest()[:8], "big")
                w_rng = np.random.default_rng(w_seed)
                vec += w_rng.standard_normal(dim)

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
