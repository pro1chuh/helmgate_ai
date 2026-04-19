"""
Helm Router — определяет тип задачи и выбирает модель через OpenRouter.

Все LLM-запросы идут через OpenRouter (routerai.ru).
ASR — через Groq (единственный провайдер с audio endpoint).

Типы задач:
  TEXT      → llama-3.3-70b
  CODE      → kat-coder-pro-v2
  REASONING → gemini-2.5-pro
  VISION    → grok-4.20 (vision)
  ASR       → Groq Whisper
  IMAGE_GEN → gemini-2.5-flash-image
  RAG       → llama-3.3-70b (с контекстом документа)
"""
from enum import Enum
from dataclasses import dataclass
from app.config import get_settings

settings = get_settings()


class TaskType(str, Enum):
    TEXT = "text"
    CODE = "code"
    REASONING = "reasoning"
    VISION = "vision"
    ASR = "asr"
    IMAGE_GEN = "image_gen"
    RAG = "rag"


class Provider(str, Enum):
    OPENROUTER = "openrouter"
    GROQ = "groq"


@dataclass
class RouteResult:
    task_type: TaskType
    provider: Provider
    model: str
    base_url: str
    api_key: str
    reason: str


# -------------------------------------------------------
# Mime-type наборы
# -------------------------------------------------------

IMAGE_MIME_TYPES = {
    "image/jpeg", "image/png", "image/gif",
    "image/webp", "image/bmp", "image/tiff",
}

AUDIO_MIME_TYPES = {
    "audio/mpeg", "audio/mp3", "audio/wav",
    "audio/ogg", "audio/flac", "audio/m4a",
    "audio/webm", "video/webm",
}

DOCUMENT_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "text/plain", "text/csv", "text/markdown",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


# -------------------------------------------------------
# Триггеры для keyword-fallback (используется в batch и т.п.)
# -------------------------------------------------------

REASONING_TRIGGERS = [
    "проанализируй", "составь стратегию", "сравни", "оцени риски",
    "дай прогноз", "обоснуй", "аргументируй", "разбери по шагам",
    "составь план", "исследуй", "глубокий анализ", "детальный анализ",
    "analyze", "compare", "evaluate", "strategize", "deep dive",
    "step by step", "reason through", "pros and cons",
]

CODE_TRIGGERS = [
    "напиши код", "напиши функцию", "напиши скрипт", "напиши класс",
    "исправь баг", "исправь ошибку", "отладь", "задебаги",
    "рефактор", "оптимизируй код", "покрой тестами", "напиши тест",
    "sql запрос", "регулярное выражение", "regex",
    "write code", "write a function", "write a script", "fix bug",
    "debug", "refactor", "optimize code", "write tests", "unit test",
    "sql query", "implement",
]

IMAGE_GEN_TRIGGERS = [
    "нарисуй", "сгенерируй изображение", "создай картинку",
    "нарисуй картинку", "покажи как выглядит", "изобрази",
    "сделай иллюстрацию", "создай логотип",
    "generate image", "draw", "create image", "visualize",
    "create a logo", "illustrate",
]


# -------------------------------------------------------
# Фабрики
# -------------------------------------------------------

def _openrouter(model: str, task: TaskType, reason: str) -> RouteResult:
    return RouteResult(
        task_type=task, provider=Provider.OPENROUTER, model=model,
        base_url=settings.OPENROUTER_BASE_URL, api_key=settings.OPENROUTER_API_KEY,
        reason=reason,
    )


def _groq(model: str, task: TaskType, reason: str) -> RouteResult:
    return RouteResult(
        task_type=task, provider=Provider.GROQ, model=model,
        base_url=settings.GROQ_BASE_URL, api_key=settings.GROQ_API_KEY,
        reason=reason,
    )


# -------------------------------------------------------
# Роутинг по типу задачи
# -------------------------------------------------------

def task_to_route(task: TaskType) -> RouteResult:
    """Маппит тип задачи на модель через OpenRouter."""
    if task == TaskType.CODE:
        return _openrouter(settings.MODEL_CODE, TaskType.CODE, f"code → {settings.MODEL_CODE}")
    if task == TaskType.REASONING:
        return _openrouter(settings.MODEL_REASONING, TaskType.REASONING, f"reasoning → {settings.MODEL_REASONING}")
    if task == TaskType.IMAGE_GEN:
        return _openrouter(settings.MODEL_IMAGE_GEN, TaskType.IMAGE_GEN, f"image_gen → {settings.MODEL_IMAGE_GEN}")
    if task == TaskType.VISION:
        return _openrouter(settings.MODEL_VISION, TaskType.VISION, f"vision → {settings.MODEL_VISION}")
    # TEXT, RAG — llama
    return _openrouter(settings.MODEL_TEXT, task, f"{task.value} → {settings.MODEL_TEXT}")


def route(
    message: str,
    file_mime_type: str | None = None,
    manual_model: str | None = None,
    manual_provider: str | None = None,
) -> RouteResult:
    """
    Синхронный роутер (keyword-matching) — используется в batch API и fallback.
    Основной путь (чаты) использует async route() из ai_router.py.
    """
    # Ручной выбор модели
    if manual_model:
        if manual_provider == "groq":
            return _groq(manual_model, TaskType.ASR, "manual → groq")
        return _openrouter(manual_model, TaskType.TEXT, "manual → openrouter")

    # По типу файла
    if file_mime_type:
        if file_mime_type in AUDIO_MIME_TYPES:
            return _groq(settings.MODEL_ASR, TaskType.ASR, f"audio → groq whisper")
        if file_mime_type in IMAGE_MIME_TYPES:
            return _openrouter(settings.MODEL_VISION, TaskType.VISION, f"image → {settings.MODEL_VISION}")
        if file_mime_type in DOCUMENT_MIME_TYPES:
            return _openrouter(settings.MODEL_TEXT, TaskType.RAG, f"doc → RAG {settings.MODEL_TEXT}")

    # Keyword-триггеры
    msg = message.lower()
    if any(t in msg for t in IMAGE_GEN_TRIGGERS):
        return _openrouter(settings.MODEL_IMAGE_GEN, TaskType.IMAGE_GEN, "keyword → image_gen")
    if any(t in msg for t in CODE_TRIGGERS):
        return _openrouter(settings.MODEL_CODE, TaskType.CODE, "keyword → code")
    if any(t in msg for t in REASONING_TRIGGERS):
        return _openrouter(settings.MODEL_REASONING, TaskType.REASONING, "keyword → reasoning")

    return _openrouter(settings.MODEL_TEXT, TaskType.TEXT, f"default → {settings.MODEL_TEXT}")


def get_embedding_config() -> tuple[str, str, str]:
    """Возвращает (base_url, api_key, model) для embedding-модели."""
    # Embeddings через OpenRouter (модели типа text-embedding-3-small)
    return settings.OPENROUTER_BASE_URL, settings.OPENROUTER_API_KEY, "openai/text-embedding-3-small"
