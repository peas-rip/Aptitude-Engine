"""Unit tests: LLM gateway retries, failures, and structured-output requests.

A fake OpenAI-compatible client replays scripted outcomes (successes and
provider exceptions) so every branch is exercised without network access.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from openai import (
    APIConnectionError,
    APIStatusError,
    AuthenticationError,
    RateLimitError,
)

from qme.config.settings import Settings
from qme.core.exceptions import LLMError, LLMRateLimitError, LLMResponseFormatError
from qme.core.models import ClassificationResult
from qme.llm.gateway import GatewayResult, LLMGateway

REQUEST = httpx.Request("POST", "https://provider.test/v1/chat/completions")

VALID_CONTENT = (
    '{"category_id": "quantitative_aptitude", "topic_id": "percentages",'
    ' "subtopic_id": null, "concepts": ["percentage"], "question_type": "mcq",'
    ' "tags": [], "confidence": 0.9, "reasoning": null}'
)


def _response(content: str | None) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=11, completion_tokens=7),
    )


def _rate_limit_error(retry_after: str | None = None) -> RateLimitError:
    headers = {"retry-after": retry_after} if retry_after is not None else {}
    return RateLimitError(
        "rate limited",
        response=httpx.Response(429, headers=headers, request=REQUEST),
        body=None,
    )


def _auth_error() -> AuthenticationError:
    return AuthenticationError(
        "bad key",
        response=httpx.Response(401, request=REQUEST),
        body=None,
    )


def _status_error(code: int) -> APIStatusError:
    return APIStatusError(
        f"status {code}",
        response=httpx.Response(code, request=REQUEST),
        body=None,
    )


def _connection_error() -> APIConnectionError:
    return APIConnectionError(request=REQUEST)


class FakeCompletions:
    def __init__(self, outcomes: list) -> None:
        self._outcomes = list(outcomes)
        self.calls: list[dict] = []

    async def create(self, **kwargs) -> SimpleNamespace:
        self.calls.append(kwargs)
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return _response(outcome)


def _fake_client(outcomes: list) -> SimpleNamespace:
    return SimpleNamespace(
        chat=SimpleNamespace(completions=FakeCompletions(outcomes)),
    )


def _settings(**overrides) -> Settings:
    base = {"llm_provider": "groq", "groq_api_key": "test-key", "retry_base_delay_sec": 0.0}
    base.update(overrides)
    return Settings(**base)


def _gateway(outcomes: list, **settings_overrides) -> tuple[LLMGateway, SimpleNamespace]:
    client = _fake_client(outcomes)
    gateway = LLMGateway(settings=_settings(**settings_overrides), client=client)
    return gateway, client


def _messages() -> list[dict[str, str]]:
    return [
        {"role": "system", "content": "classify"},
        {"role": "user", "content": "What is 15% of 240?"},
    ]


async def _complete(gateway: LLMGateway) -> GatewayResult[ClassificationResult]:
    return await gateway.complete(
        messages=_messages(),
        schema=ClassificationResult,
        model="test-model",
        stage="classifier",
    )


class TestSuccess:
    pytestmark = pytest.mark.asyncio

    async def test_valid_reply_returns_typed_result(self) -> None:
        gateway, client = _gateway([VALID_CONTENT])
        result = await _complete(gateway)
        assert isinstance(result.value, ClassificationResult)
        assert result.value.topic_id == "percentages"
        assert result.model == "test-model"
        assert result.prompt_tokens == 11
        assert result.completion_tokens == 7
        assert result.attempts == 1
        assert len(client.chat.completions.calls) == 1

    async def test_request_uses_strict_json_schema(self) -> None:
        gateway, client = _gateway([VALID_CONTENT])
        await _complete(gateway)
        call = client.chat.completions.calls[0]
        response_format = call["response_format"]
        assert response_format["type"] == "json_schema"
        assert response_format["json_schema"]["strict"] is True
        assert response_format["json_schema"]["name"] == "ClassificationResult"
        schema = response_format["json_schema"]["schema"]
        assert schema["additionalProperties"] is False
        assert set(schema["required"]) == set(schema["properties"])
        assert call["temperature"] == 0.0
        assert call["model"] == "test-model"


class TestRateLimiting:
    pytestmark = pytest.mark.asyncio

    async def test_retry_after_header_is_honored(self) -> None:
        gateway, client = _gateway([_rate_limit_error("5"), VALID_CONTENT])
        with patch("qme.llm.gateway.asyncio.sleep", new=AsyncMock()) as sleep:
            result = await _complete(gateway)
        assert result.attempts == 2
        assert sleep.call_args.args[0] == 5.0

    async def test_exhausted_rate_limits_raise_rate_limit_error(self) -> None:
        gateway, client = _gateway([_rate_limit_error("0")] * 3)
        with pytest.raises(LLMRateLimitError) as excinfo:
            await _complete(gateway)
        assert excinfo.value.context["attempts"] == 3
        assert len(client.chat.completions.calls) == 3


class TestHardFailures:
    pytestmark = pytest.mark.asyncio

    async def test_auth_error_fails_immediately_without_retries(self) -> None:
        gateway, client = _gateway([_auth_error()])
        with pytest.raises(LLMError, match="authentication failed"):
            await _complete(gateway)
        assert len(client.chat.completions.calls) == 1

    async def test_client_error_raises_llm_error(self) -> None:
        gateway, client = _gateway([_status_error(400)])
        with pytest.raises(LLMError, match="status 400"):
            await _complete(gateway)
        assert len(client.chat.completions.calls) == 1


class TestTransientFailures:
    pytestmark = pytest.mark.asyncio

    async def test_server_errors_backoff_then_raise(self) -> None:
        gateway, client = _gateway([_status_error(500)] * 3)
        with pytest.raises(LLMError, match="unreachable"):
            await _complete(gateway)
        assert len(client.chat.completions.calls) == 3

    async def test_connection_errors_retried(self) -> None:
        gateway, client = _gateway([_connection_error(), VALID_CONTENT])
        result = await _complete(gateway)
        assert result.attempts == 2


class TestSchemaMisses:
    pytestmark = pytest.mark.asyncio

    async def test_unparseable_reply_is_retried_then_raises(self) -> None:
        gateway, client = _gateway(["not json at all"] * 3)
        with pytest.raises(LLMResponseFormatError) as excinfo:
            await _complete(gateway)
        assert excinfo.value.context["attempts"] == 3
        assert len(client.chat.completions.calls) == 3

    async def test_empty_content_is_retried(self) -> None:
        gateway, client = _gateway([None, VALID_CONTENT])
        result = await _complete(gateway)
        assert result.attempts == 2


class TestConfiguration:
    pytestmark = pytest.mark.asyncio

    async def test_missing_key_raises_before_any_request(self) -> None:
        settings = Settings(llm_provider="groq", groq_api_key="")
        gateway = LLMGateway(settings=settings)
        with pytest.raises(LLMError, match="no API key"):
            await _complete(gateway)

    async def test_unknown_provider_raises(self) -> None:
        gateway = LLMGateway("bogus", settings=_settings())
        with pytest.raises(LLMError, match="unknown LLM provider"):
            await _complete(gateway)

    async def test_custom_provider_without_base_url_raises(self) -> None:
        settings = Settings(llm_provider="custom", custom_api_key="k", custom_base_url="")
        gateway = LLMGateway(settings=settings)
        with pytest.raises(LLMError, match="no base URL"):
            await _complete(gateway)


class TestGeminiProvider:
    def test_gemini_client_points_at_google_openai_compat_endpoint(self) -> None:
        settings = Settings(llm_provider="gemini", gemini_api_key="k")
        client = LLMGateway(settings=settings)._get_client()
        assert str(client.base_url).rstrip("/") == (
            "https://generativelanguage.googleapis.com/v1beta/openai"
        )

    @pytest.mark.asyncio
    async def test_missing_gemini_key_raises_before_any_request(self) -> None:
        settings = Settings(llm_provider="gemini", gemini_api_key="")
        gateway = LLMGateway(settings=settings)
        with pytest.raises(LLMError, match="no API key"):
            await _complete(gateway)


class TestRetryDelay:
    """Gemini free-tier 429s carry no retry-after header; delay rides the body."""

    def test_header_takes_precedence(self) -> None:
        assert LLMGateway._retry_delay(_rate_limit_error("5")) == 5.0

    def test_header_is_capped_at_max_backoff(self) -> None:
        assert LLMGateway._retry_delay(_rate_limit_error("120")) == 60.0

    def test_gemini_retry_info_from_body(self) -> None:
        exc = RateLimitError(
            "quota exceeded",
            response=httpx.Response(429, request=REQUEST),
            body={
                "error": {
                    "code": 429,
                    "message": "You exceeded your current quota.",
                    "details": [
                        {
                            "@type": "type.googleapis.com/google.rpc.RetryInfo",
                            "retryDelay": "33s",
                        }
                    ],
                }
            },
        )
        assert LLMGateway._retry_delay(exc) == 33.0

    def test_message_fallback_when_no_retry_info(self) -> None:
        exc = RateLimitError(
            "Error code: 429 - {'error': {'message': 'Please retry in 12.5s.'}}",
            response=httpx.Response(429, request=REQUEST),
            body={"error": {"message": "Please retry in 12.5s."}},
        )
        assert LLMGateway._retry_delay(exc) == 12.5

    def test_none_when_no_delay_signal(self) -> None:
        exc = RateLimitError(
            "quota",
            response=httpx.Response(429, request=REQUEST),
            body=None,
        )
        assert LLMGateway._retry_delay(exc) is None
