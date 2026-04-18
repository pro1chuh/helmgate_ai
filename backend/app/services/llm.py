"""
LLM-клиент для MWS GPT API (OpenAI-compatible).
Поддерживает стриминг через Server-Sent Events.
"""
import httpx
import json
from typing import AsyncIterator
from app.config import get_settings

settings = get_settings()


class LLMClient:
    def __init__(self):
        self.base_url = settings.MWS_BASE_URL
        self.api_key = settings.MWS_API_KEY
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def stream_chat(
        self,
        model: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        """
        Стримит ответ от LLM токен за токеном.
        Yields: строки контента (не SSE-обёртки)
        """
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers=self.headers,
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

    async def transcribe(self, audio_path: str) -> str:
        """Расшифровка аудио через Whisper."""
        async with httpx.AsyncClient(timeout=120.0) as client:
            with open(audio_path, "rb") as f:
                response = await client.post(
                    f"{self.base_url}/audio/transcriptions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    files={"file": f},
                    data={"model": settings.MODEL_ASR},
                )
                response.raise_for_status()
                return response.json()["text"]


llm_client = LLMClient()
