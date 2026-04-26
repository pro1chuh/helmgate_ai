"""
LLM-клиент с поддержкой нескольких провайдеров.
Все провайдеры используют OpenAI-compatible API — один клиент для всех.

Используется единый пул соединений (keep-alive) вместо создания
нового httpx.AsyncClient на каждый запрос. Это экономит TLS handshake
на каждом обращении к routerai.ru (~50-150ms).
"""
import asyncio
import httpx
import json
import logging
import re
import time
from typing import AsyncIterator
from app.core.router import RouteResult, TaskType
from app.config import get_settings
from app.core.metrics import (
    llm_requests_total,
    llm_first_token_seconds,
    llm_stream_duration_seconds,
    llm_tokens_total,
)

logger = logging.getLogger(__name__)

# Статус-коды при которых имеет смысл повторить запрос
_RETRY_STATUSES = {429, 500, 502, 503, 504}
# Сетевые ошибки при которых повторяем
_RETRY_ERRORS = (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.RemoteProtocolError)
# Количество попыток и базовая задержка
_MAX_RETRIES = 5
_BACKOFF_BASE = 1.0  # секунды: 1, 2, 4, 8 — между попытками

settings = get_settings()

_LIMITS = httpx.Limits(max_keepalive_connections=10, max_connections=20)


class LLMClient:

    def __init__(self) -> None:
        # Обычные запросы (транскрибация, embeddings, generate_image, роутер)
        self._client = httpx.AsyncClient(timeout=120.0, limits=_LIMITS)
        # Стриминг — отдельный клиент, чтобы долгий стрим не блокировал пул
        self._stream_client = httpx.AsyncClient(timeout=120.0, limits=_LIMITS)

    async def aclose(self) -> None:
        """Закрывает оба пула соединений. Вызывается при остановке приложения."""
        await self._client.aclose()
        await self._stream_client.aclose()

    def _headers(self, api_key: str) -> dict:
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    async def stream_chat(
        self,
        route: RouteResult,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        usage_out: dict | None = None,
    ) -> AsyncIterator[str]:
        """
        Стримит ответ от провайдера токен за токеном.
        Работает с любым OpenAI-compatible API (OpenRouter, Groq).

        Retry: до 5 попыток с exponential backoff (1s, 2s, 4s, 8s).
        Если токены уже начали идти — повтор не делается (нельзя дублировать ответ).
        Повторяем при: сетевых ошибках и HTTP 429/500/502/503/504.

        usage_out: если передан словарь, после завершения стрима он будет
        заполнен реальными значениями {"input_tokens": N, "output_tokens": M}
        из ответа провайдера (stream_options.include_usage).
        Если провайдер не вернул usage — остаётся fallback (подсчёт по символам).
        """
        payload = {
            "model": route.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            # Запрашиваем реальное количество токенов от провайдера
            # Поддерживается OpenRouter, OpenAI, большинством совместимых API
            "stream_options": {"include_usage": True},
        }

        # Метки для Prometheus
        provider = route.base_url.split("//")[-1].split("/")[0]  # hostname
        task_label = route.task_type.value if hasattr(route, "task_type") else "unknown"

        stream_start = time.monotonic()

        # Circuit breaker — проверяем перед запросом
        from app.services.cache import cb_is_open, cb_increment_failures, cb_reset_failures, cb_open
        if await cb_is_open(provider):
            logger.warning(f"Circuit breaker OPEN for provider {provider}, request blocked")
            raise httpx.ConnectError(f"Circuit breaker open for {provider}")

        for attempt in range(_MAX_RETRIES):
            tokens_yielded = False
            first_token_recorded = False
            actual_input_tokens: int | None = None
            actual_output_tokens: int | None = None
            fallback_output_chars = 0

            try:
                async with self._stream_client.stream(
                    "POST",
                    f"{route.base_url}/chat/completions",
                    headers=self._headers(route.api_key),
                    json=payload,
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)

                            # Захватываем реальное usage (приходит в последнем чанке)
                            if chunk.get("usage"):
                                usage = chunk["usage"]
                                actual_input_tokens = usage.get("prompt_tokens")
                                actual_output_tokens = usage.get("completion_tokens")

                            choices = chunk.get("choices", [])
                            if not choices:
                                continue
                            delta = choices[0]["delta"]
                            content = delta.get("content", "")
                            if content:
                                if not first_token_recorded:
                                    llm_first_token_seconds.labels(
                                        provider=provider,
                                        model=route.model,
                                        task_type=task_label,
                                    ).observe(time.monotonic() - stream_start)
                                    first_token_recorded = True
                                tokens_yielded = True
                                fallback_output_chars += len(content)
                                llm_tokens_total.labels(model=route.model).inc(
                                    max(1, len(content) // 4)
                                )
                                yield content
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue

                # Заполняем usage_out реальными токенами или fallback-оценкой
                if usage_out is not None:
                    if actual_input_tokens is not None and actual_output_tokens is not None:
                        usage_out["input_tokens"] = actual_input_tokens
                        usage_out["output_tokens"] = actual_output_tokens
                        usage_out["source"] = "api"
                    else:
                        # Fallback: оцениваем по символам
                        input_chars = sum(len(str(m.get("content", "") or "")) for m in messages)
                        usage_out["input_tokens"] = max(1, input_chars // 4)
                        usage_out["output_tokens"] = max(1, fallback_output_chars // 4)
                        usage_out["source"] = "estimated"

                llm_requests_total.labels(
                    provider=provider, model=route.model,
                    task_type=task_label, status="ok",
                ).inc()
                llm_stream_duration_seconds.labels(
                    provider=provider, model=route.model,
                ).observe(time.monotonic() - stream_start)

                # Circuit breaker — сбрасываем счётчик ошибок при успехе
                await cb_reset_failures(provider)
                return  # успешно завершили стрим

            except _RETRY_ERRORS as e:
                if tokens_yielded or attempt == _MAX_RETRIES - 1:
                    llm_requests_total.labels(
                        provider=provider, model=route.model,
                        task_type=task_label, status="error",
                    ).inc()
                    # Circuit breaker — фиксируем ошибку
                    failures = await cb_increment_failures(provider, settings.CIRCUIT_BREAKER_COOLDOWN_SECONDS)
                    if failures >= settings.CIRCUIT_BREAKER_FAILURE_THRESHOLD:
                        await cb_open(provider, settings.CIRCUIT_BREAKER_COOLDOWN_SECONDS)
                        logger.error(
                            f"Circuit breaker OPENED for {provider} after {failures} failures, "
                            f"cooldown {settings.CIRCUIT_BREAKER_COOLDOWN_SECONDS}s"
                        )
                    raise
                wait = _BACKOFF_BASE * (2 ** attempt)
                logger.warning(
                    f"stream_chat attempt {attempt + 1}/{_MAX_RETRIES} failed "
                    f"({type(e).__name__}: {e}), retry in {wait:.0f}s"
                )
                await asyncio.sleep(wait)

            except httpx.HTTPStatusError as e:
                if tokens_yielded or attempt == _MAX_RETRIES - 1:
                    llm_requests_total.labels(
                        provider=provider, model=route.model,
                        task_type=task_label, status="error",
                    ).inc()
                    # Circuit breaker — только для 5xx ошибок
                    if e.response.status_code >= 500:
                        failures = await cb_increment_failures(provider, settings.CIRCUIT_BREAKER_COOLDOWN_SECONDS)
                        if failures >= settings.CIRCUIT_BREAKER_FAILURE_THRESHOLD:
                            await cb_open(provider, settings.CIRCUIT_BREAKER_COOLDOWN_SECONDS)
                            logger.error(
                                f"Circuit breaker OPENED for {provider} (HTTP {e.response.status_code})"
                            )
                    raise
                if e.response.status_code not in _RETRY_STATUSES:
                    llm_requests_total.labels(
                        provider=provider, model=route.model,
                        task_type=task_label, status="error",
                    ).inc()
                    raise
                wait = _BACKOFF_BASE * (2 ** attempt)
                logger.warning(
                    f"stream_chat attempt {attempt + 1}/{_MAX_RETRIES} failed "
                    f"(HTTP {e.response.status_code}), retry in {wait:.0f}s"
                )
                await asyncio.sleep(wait)

    async def transcribe(self, route: RouteResult, audio_path: str) -> str:
        """
        Расшифровка аудио.
        Cloud: Groq Whisper (быстрый, точный)
        Local: Ollama Whisper
        """
        with open(audio_path, "rb") as f:
            response = await self._client.post(
                f"{route.base_url}/audio/transcriptions",
                headers={"Authorization": f"Bearer {route.api_key}"},
                files={"file": (audio_path, f, "audio/mpeg")},
                data={"model": route.model},
            )
            response.raise_for_status()
            return response.json()["text"]

    @staticmethod
    def _extract_image_url_from_chat_response(data: dict) -> str:
        """Extract an image URL/data URI from OpenAI-compatible chat responses."""
        choices = data.get("choices") or []
        if not choices:
            raise ValueError("Image response has no choices")

        message = choices[0].get("message") or {}

        for image in message.get("images") or []:
            image_url = image.get("image_url") or image.get("url")
            url = image_url.get("url") if isinstance(image_url, dict) else image_url
            if url:
                return url

        content = message.get("content") or ""
        content_parts = content if isinstance(content, list) else [{"text": str(content)}]

        for part in content_parts:
            if not isinstance(part, dict):
                continue

            image_url = part.get("image_url") or part.get("url")
            url = image_url.get("url") if isinstance(image_url, dict) else image_url
            if url:
                return url

            text = str(part.get("text") or part.get("content") or "")
            data_uri = re.search(r"data:image/[^;\s]+;base64,[A-Za-z0-9+/=\r\n]+", text)
            if data_uri:
                return data_uri.group(0).replace("\n", "").replace("\r", "")

            markdown_url = re.search(r"!\[[^\]]*\]\((https?://[^)\s]+)\)", text)
            if markdown_url:
                return markdown_url.group(1)

            plain_url = re.search(r"https?://\S+", text)
            if plain_url:
                return plain_url.group(0).rstrip(").,")

        raise ValueError(f"Unexpected image response format: {list(message.keys())}")

    async def generate_image(self, route: RouteResult, prompt: str) -> str:
        """
        Генерация изображения через /images/generations.
        Возвращает URL картинки (или data-URI если провайдер вернул base64).
        Совместим с routerai.ru / OpenRouter / DALL-E.
        """
        payload = {
            "model": route.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }
        provider = route.base_url.split("//")[-1].split("/")[0]
        t0 = time.monotonic()

        try:
            response = await self._client.post(
                f"{route.base_url}/chat/completions",
                headers=self._headers(route.api_key),
                json=payload,
                timeout=180.0,
            )
            response.raise_for_status()
            data = response.json()

            llm_requests_total.labels(
                provider=provider, model=route.model,
                task_type="image_gen", status="ok",
            ).inc()
            llm_stream_duration_seconds.labels(
                provider=provider, model=route.model,
            ).observe(time.monotonic() - t0)

            # Провайдер может вернуть url или b64_json
            return self._extract_image_url_from_chat_response(data)

        except Exception:
            llm_requests_total.labels(
                provider=provider, model=route.model,
                task_type="image_gen", status="error",
            ).inc()
            raise

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """
        Векторизация текстов для RAG.
        Провайдер выбирается автоматически из get_embedding_config().
        """
        from app.core.router import get_embedding_config
        base_url, api_key, model = get_embedding_config()

        payload = {"model": model, "input": texts}
        response = await self._client.post(
            f"{base_url}/embeddings",
            headers=self._headers(api_key),
            json=payload,
            timeout=60.0,
        )
        response.raise_for_status()
        data = response.json()["data"]
        return [item["embedding"] for item in sorted(data, key=lambda x: x["index"])]


llm_client = LLMClient()
