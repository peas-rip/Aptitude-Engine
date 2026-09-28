"""LLM gateway: provider-pluggable client with enforced structured output.

Design rules:
- Structured outputs only: every call sends ``response_format`` with a strict
  JSON Schema and the reply is Pydantic-validated (never free-form parsing).
- Provider decided by ``QME_LLM_PROVIDER`` (gemini free default, groq free
  alternative, openai paid fallback, or any OpenAI-compatible endpoint via
  ``custom``); keys are validated on first call, never at import, so CLI/health
  work without a key.
- 429s honor ``retry-after`` when present, else parse the delay from the error
  body (Gemini omits the header); 5xx/connection errors back off exponentially;
  auth and schema failures fail loudly with context (no silent retries on
  bad keys). Usage (tokens + duration) rides back for provenance/cost tracking.
"""

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from openai import (
    APIConnectionError,
    APIStatusError,
    AsyncOpenAI,
    AuthenticationError,
    RateLimitError,
)
from pydantic import BaseModel

from qme.config.settings import Settings, get_settings
from qme.core.exceptions import LLMError, LLMRateLimitError, LLMResponseFormatError
from qme.llm.structured_output import parse_model, strict_schema

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_MAX_BACKOFF_SEC = 60.0


@dataclass
class GatewayResult(Generic[T]):
    """A validated value plus the provenance/cost facts about the call."""

    value: T
    model: str
    prompt_tokens: int
    completion_tokens: int
    duration_ms: int
    attempts: int


class LLMGateway:
    """Async structured-output client. Inject ``client``/``settings`` in tests."""

    def __init__(
        self,
        provider: str | None = None,
        *,
        settings: Settings | None = None,
        client: Any | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._provider = (provider or self._settings.llm_provider).strip().lower()
        self._client = client

    async def complete(
        self,
        *,
        messages: list[dict[str, str]],
        schema: type[T],
        model: str,
        temperature: float = 0.0,
        stage: str = "llm",
    ) -> GatewayResult[T]:
        """One structured completion with bounded retries; returns validated data."""
        client = self._get_client()
        request_schema = strict_schema(schema)
        max_attempts = max(1, self._settings.max_retries)
        last: Exception | None = None
        rate_limited = False

        for attempt in range(1, max_attempts + 1):
            started = time.perf_counter()
            try:
                response = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": schema.__name__,
                            "strict": True,
                            "schema": request_schema,
                        },
                    },
                    temperature=temperature,
                )
            except RateLimitError as exc:
                rate_limited = True
                last = exc
                delay = self._retry_delay(exc) or min(
                    _MAX_BACKOFF_SEC, self._settings.retry_base_delay_sec * 2**attempt
                )
                logger.warning(
                    "LLM rate limited | stage=%s | attempt=%d/%d | sleeping %.1fs",
                    stage,
                    attempt,
                    max_attempts,
                    delay,
                )
                await asyncio.sleep(delay)
                continue
            except AuthenticationError as exc:
                # Bad keys do not heal; never burn retries on them.
                raise LLMError(
                    f"authentication failed for provider {self._provider!r}; check the API key",
                    context={"stage": stage, "provider": self._provider, "error": str(exc)[:300]},
                ) from exc
            except APIStatusError as exc:
                last = exc
                if exc.status_code >= 500:
                    delay = min(_MAX_BACKOFF_SEC, self._settings.retry_base_delay_sec * 2**attempt)
                    logger.warning(
                        "LLM server error %s | stage=%s | attempt=%d/%d | sleeping %.1fs",
                        exc.status_code,
                        stage,
                        attempt,
                        max_attempts,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise LLMError(
                    f"LLM request rejected with status {exc.status_code}",
                    context={"stage": stage, "provider": self._provider, "error": str(exc)[:300]},
                ) from exc
            except APIConnectionError as exc:
                last = exc
                delay = min(_MAX_BACKOFF_SEC, self._settings.retry_base_delay_sec * 2**attempt)
                logger.warning(
                    "LLM connection error | stage=%s | attempt=%d/%d | sleeping %.1fs",
                    stage,
                    attempt,
                    max_attempts,
                    delay,
                )
                await asyncio.sleep(delay)
                continue

            duration_ms = int((time.perf_counter() - started) * 1000)
            content = response.choices[0].message.content if response.choices else None
            if not content:
                last = LLMResponseFormatError("empty completion content", context={"stage": stage})
                logger.warning(
                    "LLM empty content | stage=%s | attempt=%d/%d", stage, attempt, max_attempts
                )
                continue
            try:
                value = parse_model(schema, content)
            except LLMResponseFormatError as exc:
                last = exc
                logger.warning(
                    "LLM schema miss | stage=%s | attempt=%d/%d | %s",
                    stage,
                    attempt,
                    max_attempts,
                    exc.context.get("error", ""),
                )
                continue

            usage = response.usage
            return GatewayResult(
                value=value,  # type: ignore[arg-type]
                model=model,
                prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
                duration_ms=duration_ms,
                attempts=attempt,
            )

        if rate_limited and isinstance(last, RateLimitError):
            raise LLMRateLimitError(
                f"rate limited by {self._provider!r} after {max_attempts} attempts",
                context={"stage": stage, "provider": self._provider, "attempts": max_attempts},
            ) from last
        if isinstance(last, (APIConnectionError, APIStatusError)):
            raise LLMError(
                f"LLM unreachable after {max_attempts} attempts ({self._provider!r})",
                context={"stage": stage, "provider": self._provider, "attempts": max_attempts},
            ) from last
        raise LLMResponseFormatError(
            f"no schema-valid response after {max_attempts} attempts",
            context={"stage": stage, "model": model, "attempts": max_attempts},
        ) from last

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        settings = self._settings
        provider = self._provider
        if provider == "gemini":
            key, base_url = settings.gemini_api_key, settings.gemini_base_url
        elif provider == "groq":
            key, base_url = settings.groq_api_key, settings.groq_base_url
        elif provider == "openai":
            key, base_url = settings.openai_api_key, settings.openai_base_url
        elif provider == "custom":
            key, base_url = settings.custom_api_key, settings.custom_base_url
        else:
            raise LLMError(
                f"unknown LLM provider {provider!r}; use gemini | groq | openai | custom",
                context={"provider": provider},
            )
        if not base_url:
            raise LLMError(
                f"no base URL configured for provider {provider!r}",
                context={"provider": provider},
            )
        if not key:
            raise LLMError(
                f"no API key configured for provider {provider!r}",
                context={"provider": provider, "settings_key": f"{provider}_api_key"},
            )
        self._client = AsyncOpenAI(api_key=key, base_url=base_url)
        return self._client

    @staticmethod
    def _retry_delay(exc: RateLimitError) -> float | None:
        """Seconds to wait for a 429, capped. Header first, then error body.

        Gemini free-tier 429s omit ``retry-after``; the delay rides in the
        error body instead (``RetryInfo.retryDelay: "33s"`` and/or a message
        like "Please retry in 33.5s"). Both are parsed here so retries wait
        out the quota window instead of burning attempts against the limit.
        """
        try:
            raw = exc.response.headers.get("retry-after")
            if raw is not None:
                return min(_MAX_BACKOFF_SEC, max(0.0, float(raw)))
        except (AttributeError, TypeError, ValueError):
            pass

        body = getattr(exc, "body", None)
        if isinstance(body, dict):
            error = body.get("error", body)
            details = error.get("details") if isinstance(error, dict) else None
            if isinstance(details, list):
                for detail in details:
                    if not isinstance(detail, dict):
                        continue
                    retry_delay = detail.get("retryDelay")
                    if isinstance(retry_delay, str):
                        parsed = LLMGateway._seconds(retry_delay)
                        if parsed is not None:
                            return min(_MAX_BACKOFF_SEC, parsed)

        match = re.search(
            r"(?:retry in|try again in)\s+([0-9]+(?:\.[0-9]+)?)\s*s",
            str(exc),
            re.IGNORECASE,
        )
        if match:
            return min(_MAX_BACKOFF_SEC, float(match.group(1)))
        return None

    @staticmethod
    def _seconds(value: str) -> float | None:
        """Parse a protobuf duration fragment like ``33s`` / ``0.500s``."""
        match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)s?", value.strip())
        return float(match.group(1)) if match else None
