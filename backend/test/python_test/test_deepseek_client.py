import asyncio
import httpx

from app.deepseek_client import DEFAULT_DEEPSEEK_MODEL, DeepSeekApiError, DeepSeekClient, build_stream_timeout, parse_sse_chunk
from app.deepseek_settings import DeepSeekSettings, save_deepseek_settings


def test_parse_sse_chunk_returns_content_delta() -> None:
    line = 'data: {"choices":[{"delta":{"content":"Привет"}}]}'

    assert parse_sse_chunk(line) == "Привет"


def test_parse_sse_chunk_returns_none_on_done() -> None:
    assert parse_sse_chunk("data: [DONE]") is None


def test_deepseek_api_error_hides_token() -> None:
    error = DeepSeekApiError(401, "bad token sk-secret")

    assert "sk-secret" not in str(error)
    assert "401" in str(error)


def test_build_stream_timeout_uses_finite_read_timeout() -> None:
    timeout = build_stream_timeout()

    assert isinstance(timeout, httpx.Timeout)
    assert timeout.read == 120.0


def test_default_deepseek_model_is_chat() -> None:
    assert DEFAULT_DEEPSEEK_MODEL == "deepseek-chat"


def test_deepseek_client_chat_reuses_persistent_async_client() -> None:
    calls = {"created": 0, "closed": 0}

    class FakeResponse:
        status_code = 200
        text = ""

        def json(self):
            return {"choices": [{"message": {"content": "ok"}}]}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            calls["created"] += 1

        async def post(self, *args, **kwargs):
            return FakeResponse()

        async def aclose(self) -> None:
            calls["closed"] += 1

    original = httpx.AsyncClient
    httpx.AsyncClient = FakeAsyncClient
    try:
        client = DeepSeekClient(api_key="test-key")
        assert asyncio.run(client.chat([{"role": "user", "content": "one"}])) == "ok"
        assert asyncio.run(client.chat([{"role": "user", "content": "two"}])) == "ok"
        asyncio.run(client.aclose())
    finally:
        httpx.AsyncClient = original

    assert calls["created"] == 1
    assert calls["closed"] == 1


def test_deepseek_client_from_env_uses_runtime_settings(tmp_path, monkeypatch) -> None:
    settings_path = tmp_path / "deepseek_settings.json"
    save_deepseek_settings(
        DeepSeekSettings(
            model="deepseek-chat",
            base_url="https://example.test",
            endpoint_path="/legacy/chat/completions",
        ),
        path=settings_path,
    )
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(
        "app.deepseek_client.load_deepseek_settings",
        lambda: DeepSeekSettings(
            model="deepseek-chat",
            base_url="https://example.test",
            endpoint_path="/legacy/chat/completions",
        ),
    )

    client = DeepSeekClient.from_env()

    assert client.model == "deepseek-chat"
    assert client.endpoint == "https://example.test/legacy/chat/completions"


def test_deepseek_client_chat_retries_temporary_timeout() -> None:
    calls = {"post": 0}

    class FakeResponse:
        status_code = 200
        text = ""

        def json(self):
            return {"choices": [{"message": {"content": "ok-after-retry"}}]}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def post(self, *args, **kwargs):
            calls["post"] += 1
            if calls["post"] == 1:
                raise httpx.ReadTimeout("temporary timeout")
            return FakeResponse()

        async def aclose(self) -> None:
            return None

    original = httpx.AsyncClient
    httpx.AsyncClient = FakeAsyncClient
    try:
        client = DeepSeekClient(api_key="test-key")
        assert asyncio.run(client.chat([{"role": "user", "content": "retry"}])) == "ok-after-retry"
        asyncio.run(client.aclose())
    finally:
        httpx.AsyncClient = original

    assert calls["post"] == 2


def test_deepseek_client_chat_uses_fallback_model_after_primary_api_error() -> None:
    requested_models: list[str] = []

    class ErrorResponse:
        status_code = 429
        text = "rate limited"

    class SuccessResponse:
        status_code = 200
        text = ""

        def json(self):
            return {"choices": [{"message": {"content": "fallback-answer"}}]}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def post(self, *args, **kwargs):
            requested_models.append(kwargs["json"]["model"])
            if len(requested_models) == 1:
                return ErrorResponse()
            return SuccessResponse()

        async def aclose(self) -> None:
            return None

    original = httpx.AsyncClient
    httpx.AsyncClient = FakeAsyncClient
    try:
        client = DeepSeekClient(
            api_key="test-key",
            model="deepseek-reasoner",
            fallback_model="deepseek-chat",
        )
        assert asyncio.run(client.chat([{"role": "user", "content": "fallback"}])) == "fallback-answer"
        asyncio.run(client.aclose())
    finally:
        httpx.AsyncClient = original

    assert requested_models == ["deepseek-reasoner", "deepseek-chat"]
