"""
LLM-клиент с поддержкой нескольких провайдеров.
Все провайдеры используют OpenAI-compatible API — один клиент для всех.

Используется единый пул соединений (keep-alive) вместо создания
нового httpx.AsyncClient на каждый запрос. Это экономит TLS handshake
на каждом обращении к routerai.ru (~50-150ms).
"""
import httpx
import json
from typing import AsyncIterator
from app.core.router import RouteResult, TaskType
from app.config import get_settings

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
    ) -> AsyncIterator[str]:
        """
        Стримит ответ от провайдера токен за токеном.
        Работает одинаково для NVIDIA NIM, Groq и Ollama.
        """
        payload = {
            "model": route.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

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
                    delta = chunk["choices"][0]["delta"]
                    content = delta.get("content", "")
                    if content:
                        yield content
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue

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

    async def generate_image(self, route: RouteResult, prompt: str) -> str:
        """
        Генерация изображения. Возвращает URL или base64.
        """
        payload = {
            "model": route.model,
            "prompt": prompt,
            "n": 1,
            "size": "1024x1024",
            "response_format": "url",
        }
        response = await self._client.post(
            f"{route.base_url}/images/generations",
            headers=self._headers(route.api_key),
            json=payload,
            timeout=180.0,
        )
        response.raise_for_status()
        return response.json()["data"][0]["url"]

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
