from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import AsyncIterator
from typing import Any

import httpx

from .deepseek_settings import (
    DEFAULT_DEEPSEEK_BASE_URL,
    DEFAULT_DEEPSEEK_ENDPOINT_PATH,
    DEFAULT_DEEPSEEK_MODEL,
    load_deepseek_settings,
    normalize_endpoint_path,
)

DEFAULT_CONNECT_TIMEOUT_SECONDS = 20.0
DEFAULT_WRITE_TIMEOUT_SECONDS = 30.0
DEFAULT_POOL_TIMEOUT_SECONDS = 30.0
DEFAULT_READ_TIMEOUT_SECONDS = 120.0
DEFAULT_MAX_TOKENS = 1600
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_BACKOFF_SECONDS = 0.25
DEFAULT_MAX_RETRY_BACKOFF_SECONDS = 2.0
logger = logging.getLogger("dns_bot.deepseek")


class DeepSeekApiError(RuntimeError):
    def __init__(self, status_code: int, detail: str) -> None:
        clean_detail = sanitize_secret(detail)
        super().__init__(f"DeepSeek API error {status_code}: {clean_detail}")
        self.status_code = status_code


def sanitize_secret(value: str) -> str:
    return " ".join(value.replace("sk-", "sk-***").split())


def parse_sse_chunk(line: str) -> str | None:
    cleaned = line.strip()
    if not cleaned.startswith("data:"):
        return ""
    data = cleaned.removeprefix("data:").strip()
    if data == "[DONE]":
        return None
    try:
        payload = json.loads(data)
    except json.JSONDecodeError:
        return ""
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    delta = choices[0].get("delta", {})
    content = delta.get("content", "")
    return content if isinstance(content, str) else ""


class DeepSeekClient:
    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_DEEPSEEK_MODEL,
        fallback_model: str = "",
        base_url: str = DEFAULT_DEEPSEEK_BASE_URL,
        endpoint_path: str = DEFAULT_DEEPSEEK_ENDPOINT_PATH,
        timeout: httpx.Timeout | None = None,
        temperature: float = 0.2,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        top_p: float = 1.0,
        thinking: dict[str, object] | None = None,
        retry_attempts: int = DEFAULT_RETRY_ATTEMPTS,
        retry_backoff_seconds: float = DEFAULT_RETRY_BACKOFF_SECONDS,
        max_retry_backoff_seconds: float = DEFAULT_MAX_RETRY_BACKOFF_SECONDS,
    ) -> None:
        self.api_key = api_key.strip()
        self.model = model.strip() or DEFAULT_DEEPSEEK_MODEL
        self.fallback_model = fallback_model.strip()
        self.base_url = base_url.strip().rstrip("/") or DEFAULT_DEEPSEEK_BASE_URL
        self.endpoint_path = normalize_endpoint_path(endpoint_path)
        self.endpoint = f"{self.base_url}{self.endpoint_path}"
        self.timeout = timeout or build_stream_timeout()
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p
        self.thinking = thinking
        self.retry_attempts = max(1, int(retry_attempts))
        self.retry_backoff_seconds = max(0.0, float(retry_backoff_seconds))
        self.max_retry_backoff_seconds = max(self.retry_backoff_seconds, float(max_retry_backoff_seconds))
        self._client: httpx.AsyncClient | None = None

    @classmethod
    def from_env(cls, **overrides: Any) -> "DeepSeekClient":
        api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("DEEPSEEK_API_KEY is not configured.")
        settings = load_deepseek_settings()
        return cls(
            api_key=api_key,
            model=str(overrides.pop("model", settings.model)),
            fallback_model=str(overrides.pop("fallback_model", settings.fallback_model)),
            base_url=str(overrides.pop("base_url", settings.base_url)),
            endpoint_path=str(overrides.pop("endpoint_path", settings.endpoint_path)),
            **overrides,
        )

    async def stream_chat(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        for model_index, model_name in enumerate(self.iter_models()):
            switched_to_fallback = False
            for attempt in range(1, self.retry_attempts + 1):
                logger.info(
                    "deepseek_request_start messages=%s model=%s endpoint=%s attempt=%s",
                    len(messages),
                    model_name,
                    self.endpoint_path,
                    attempt,
                )
                try:
                    async with self.get_client().stream(
                        "POST",
                        self.endpoint,
                        json=self.build_payload(messages, stream=True, model=model_name),
                        headers=self.build_headers(),
                    ) as response:
                        if response.status_code >= 400:
                            detail = await response.aread()
                            raise DeepSeekApiError(response.status_code, detail.decode("utf-8", "replace"))
                        async for line in response.aiter_lines():
                            chunk = parse_sse_chunk(line)
                            if chunk is None:
                                logger.info("deepseek_request_done")
                                return
                            if chunk:
                                yield chunk
                        logger.info("deepseek_request_done")
                        return
                except DeepSeekApiError as exc:
                    logger.error("deepseek_request_error status=%s model=%s attempt=%s", exc.status_code, model_name, attempt)
                    if self.should_switch_to_fallback(exc.status_code, model_index):
                        switched_to_fallback = True
                        break
                    if not self.should_retry_status(exc.status_code) or attempt >= self.retry_attempts:
                        raise
                except httpx.TransportError as exc:
                    logger.warning("deepseek_transport_error model=%s attempt=%s error=%s", model_name, attempt, sanitize_secret(str(exc)))
                    if attempt >= self.retry_attempts:
                        if self.can_switch_to_fallback(model_index):
                            switched_to_fallback = True
                            break
                        raise
                await asyncio.sleep(self.retry_delay(attempt))
            if switched_to_fallback:
                logger.warning("deepseek_fallback_model_switch from_model=%s to_model=%s", model_name, self.fallback_model)
                continue
            break

    async def chat(self, messages: list[dict[str, str]]) -> str:
        last_error: Exception | None = None
        for model_index, model_name in enumerate(self.iter_models()):
            switched_to_fallback = False
            for attempt in range(1, self.retry_attempts + 1):
                logger.info(
                    "deepseek_request_start messages=%s model=%s endpoint=%s attempt=%s",
                    len(messages),
                    model_name,
                    self.endpoint_path,
                    attempt,
                )
                try:
                    response = await self.get_client().post(
                        self.endpoint,
                        json=self.build_payload(messages, stream=False, model=model_name),
                        headers=self.build_headers(),
                    )
                    if response.status_code >= 400:
                        raise DeepSeekApiError(response.status_code, response.text)
                    logger.info("deepseek_request_done")
                    payload = response.json()
                    return extract_chat_content(payload)
                except DeepSeekApiError as exc:
                    last_error = exc
                    logger.error("deepseek_request_error status=%s model=%s attempt=%s", exc.status_code, model_name, attempt)
                    if self.should_switch_to_fallback(exc.status_code, model_index):
                        switched_to_fallback = True
                        break
                    if not self.should_retry_status(exc.status_code) or attempt >= self.retry_attempts:
                        raise
                except httpx.TransportError as exc:
                    last_error = exc
                    logger.warning("deepseek_transport_error model=%s attempt=%s error=%s", model_name, attempt, sanitize_secret(str(exc)))
                    if attempt >= self.retry_attempts:
                        if self.can_switch_to_fallback(model_index):
                            switched_to_fallback = True
                            break
                        raise
                await asyncio.sleep(self.retry_delay(attempt))
            if switched_to_fallback:
                logger.warning("deepseek_fallback_model_switch from_model=%s to_model=%s", model_name, self.fallback_model)
                continue
            break
        if last_error is not None:
            raise last_error
        return ""

    def build_payload(self, messages: list[dict[str, str]], stream: bool, model: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": (model or self.model).strip() or self.model,
            "messages": messages,
            "stream": stream,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
        }
        if isinstance(self.thinking, dict) and self.thinking:
            payload["thinking"] = self.thinking
        return payload

    def build_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def aclose(self) -> None:
        if self._client is None:
            return
        await self._client.aclose()
        self._client = None

    def iter_models(self) -> tuple[str, ...]:
        models = [self.model]
        if self.fallback_model and self.fallback_model != self.model:
            models.append(self.fallback_model)
        return tuple(models)

    def can_switch_to_fallback(self, model_index: int) -> bool:
        return bool(self.fallback_model) and model_index == 0 and self.fallback_model != self.model

    def should_switch_to_fallback(self, status_code: int, model_index: int) -> bool:
        return self.can_switch_to_fallback(model_index) and self.should_retry_status(status_code)

    @staticmethod
    def should_retry_status(status_code: int) -> bool:
        return status_code in {408, 409, 425, 429} or 500 <= status_code <= 504

    def retry_delay(self, attempt: int) -> float:
        delay = self.retry_backoff_seconds * (2 ** max(0, attempt - 1))
        return min(delay, self.max_retry_backoff_seconds)


def extract_chat_content(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    message = choices[0].get("message", {})
    content = message.get("content", "")
    return content if isinstance(content, str) else ""


def build_stream_timeout() -> httpx.Timeout:
    return httpx.Timeout(
        connect=DEFAULT_CONNECT_TIMEOUT_SECONDS,
        write=DEFAULT_WRITE_TIMEOUT_SECONDS,
        pool=DEFAULT_POOL_TIMEOUT_SECONDS,
        read=DEFAULT_READ_TIMEOUT_SECONDS,
    )
