"""
Helm AI-Router — использует маленькую LLM для классификации задачи.

Преимущество перед keyword-matching:
  "у меня не работает функция" → понимает что это CODE/TEXT, а не ищет слово "код"
  "составь документацию к классу" → понимает контекст, а не ищет триггер
  "разбери этот договор" → понимает что нужен анализ

Модель-роутер: gemma-3-4b-it (4B, быстрая, дешёвая, ~200-400ms)
"""
import httpx
import json
import logging
from app.config import get_settings
from app.core.router import (
    TaskType, RouteResult, Provider,
    IMAGE_MIME_TYPES, AUDIO_MIME_TYPES, DOCUMENT_MIME_TYPES,
    _nvidia, _groq, _ollama, _openrouter,
)

logger = logging.getLogger(__name__)
settings = get_settings()

# Модель для роутинга — маленькая и быстрая
ROUTER_MODEL = "google/gemma-3-4b-it"

ROUTER_PROMPT = """\
Ты — классификатор задач. Проанализируй сообщение пользователя и верни ТОЛЬКО валидный JSON без пояснений.

Типы задач:
- "text": обычный вопрос, написание текста, перевод, резюме, общение
- "code": написать код, функцию, скрипт, класс, исправить баг, отладить, рефакторинг, SQL, regex, тесты
- "reasoning": глубокий анализ, стратегия, сравнение вариантов, прогноз, оценка рисков, бизнес-план
- "image_gen": нарисовать, сгенерировать или создать изображение/иллюстрацию/логотип

Формат ответа: {{"task": "text"}}

Сообщение пользователя: {message}"""


async def _classify(message: str) -> TaskType:
    """
    Отправляет сообщение в gemma-3-4b-it и получает тип задачи.
    При любой ошибке возвращает TEXT (безопасный дефолт).
    """
    payload = {
        "model": ROUTER_MODEL,
        "messages": [
            {"role": "user", "content": ROUTER_PROMPT.format(message=message[:500])},
        ],
        "temperature": 0.0,   # детерминированный вывод
        "max_tokens": 20,     # нужен только {"task": "..."}
        "stream": False,
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"{settings.OPENROUTER_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {settings.OPENROUTER_API_KEY}"},
                json=payload,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"].strip()

            # Парсим JSON — gemma иногда добавляет ```json обёртку
            content = content.replace("```json", "").replace("```", "").strip()
            data = json.loads(content)
            task_str = data.get("task", "text").lower()

            return {
                "text": TaskType.TEXT,
                "code": TaskType.CODE,
                "reasoning": TaskType.REASONING,
                "image_gen": TaskType.IMAGE_GEN,
            }.get(task_str, TaskType.TEXT)

    except Exception as e:
        logger.warning(f"AI router failed ({type(e).__name__}: {e}), falling back to TEXT")
        return TaskType.TEXT


def _build_cloud_route(task: TaskType) -> RouteResult:
    """Маппит тип задачи на модель в cloud-режиме (OpenRouter)."""
    if task == TaskType.CODE:
        return _openrouter(settings.CLOUD_MODEL_CODE, TaskType.CODE, "ai_router → qwen2.5-coder-32b")
    if task == TaskType.REASONING:
        return _openrouter(settings.CLOUD_MODEL_REASONING, TaskType.REASONING, "ai_router → deepseek-r1")
    if task == TaskType.IMAGE_GEN:
        return _openrouter(settings.CLOUD_MODEL_TEXT, TaskType.IMAGE_GEN, "ai_router → image_gen fallback llama")
    return _openrouter(settings.CLOUD_MODEL_TEXT, TaskType.TEXT, "ai_router → llama-3.3-70b")


def _build_local_route(task: TaskType) -> RouteResult:
    """Маппит тип задачи на модель в local-режиме."""
    return _ollama(settings.LOCAL_MODEL_TEXT, task, f"ai_router → ollama ({task.value})")


async def route(
    message: str,
    file_mime_type: str | None = None,
    manual_model: str | None = None,
    manual_provider: str | None = None,
) -> RouteResult:
    """
    Главная функция роутинга — async версия с AI-классификацией.

    Порядок приоритетов:
      1. Ручной выбор пользователя
      2. Тип прикреплённого файла (детерминированно)
      3. AI-классификация текста
    """
    is_local = settings.DEPLOYMENT_MODE == "local"

    # 1. Ручной выбор
    if manual_model:
        if is_local or manual_provider == "ollama":
            return _ollama(manual_model, TaskType.TEXT, "manual → ollama")
        if manual_provider == "groq":
            return _groq(manual_model, TaskType.TEXT, "manual → groq")
        if manual_provider == "openrouter":
            return _openrouter(manual_model, TaskType.TEXT, "manual → openrouter")
        return _nvidia(manual_model, TaskType.TEXT, "manual → nvidia")

    # 2. По типу файла (детерминированно, без AI)
    if file_mime_type:
        if file_mime_type in AUDIO_MIME_TYPES:
            if is_local:
                return _ollama(settings.LOCAL_MODEL_ASR, TaskType.ASR, f"audio → ollama whisper")
            return _groq(settings.CLOUD_MODEL_ASR, TaskType.ASR, f"audio → groq whisper")

        if file_mime_type in IMAGE_MIME_TYPES:
            if is_local:
                return _ollama(settings.LOCAL_MODEL_VISION, TaskType.VISION, f"image → ollama llava")
            return _nvidia(settings.CLOUD_MODEL_VISION, TaskType.VISION, f"image → llama-3.2-90b-vision")

        if file_mime_type in DOCUMENT_MIME_TYPES:
            if is_local:
                return _ollama(settings.LOCAL_MODEL_TEXT, TaskType.RAG, f"doc → ollama RAG")
            return _nvidia(settings.CLOUD_MODEL_TEXT, TaskType.RAG, f"doc → glm-5.1 RAG")

    # 3. AI-классификация текста
    if is_local:
        # В local-режиме AI-роутер не вызываем (нет доступа к NVIDIA)
        # Используем keyword-fallback из старого роутера
        from app.core.router import route as keyword_route
        return keyword_route(message, file_mime_type, manual_model, manual_provider)

    task = await _classify(message)
    return _build_cloud_route(task)
