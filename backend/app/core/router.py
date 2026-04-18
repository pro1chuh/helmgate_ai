"""
Helm Auto-Router — определяет тип задачи, выбирает провайдера и модель.

Cloud режим:
  Текст        → NVIDIA NIM / GLM-5.1
  Reasoning    → NVIDIA NIM / DeepSeek V3.2
  Код          → NVIDIA NIM / Qwen2.5-Coder-32B
  Vision       → NVIDIA NIM / Llama-3.2-90B-Vision
  ASR          → Groq / Whisper-large-v3-turbo
  Embeddings   → NVIDIA NIM / nv-embedqa-e5-v5

Local режим (air-gapped, 152-ФЗ):
  Всё          → Ollama
"""
from enum import Enum
from dataclasses import dataclass
from app.config import get_settings

settings = get_settings()


class TaskType(str, Enum):
    TEXT = "text"
    REASONING = "reasoning"
    CODE = "code"
    VISION = "vision"
    ASR = "asr"
    IMAGE_GEN = "image_gen"
    RAG = "rag"


class Provider(str, Enum):
    NVIDIA = "nvidia"
    GROQ = "groq"
    OLLAMA = "ollama"


@dataclass
class RouteResult:
    task_type: TaskType
    provider: Provider
    model: str
    base_url: str
    api_key: str
    reason: str


# -------------------------------------------------------
# Триггеры для определения типа задачи
# -------------------------------------------------------

REASONING_TRIGGERS = [
    # RU
    "проанализируй", "составь стратегию", "сравни", "оцени риски",
    "дай прогноз", "обоснуй", "аргументируй", "разбери по шагам",
    "составь план", "исследуй", "глубокий анализ", "детальный анализ",
    # EN
    "analyze", "compare", "evaluate", "strategize", "deep dive",
    "step by step", "reason through", "pros and cons",
]

CODE_TRIGGERS = [
    # RU
    "напиши код", "напиши функцию", "напиши скрипт", "напиши класс",
    "исправь баг", "исправь ошибку", "отладь", "задебаги",
    "рефактор", "оптимизируй код", "покрой тестами", "напиши тест",
    "sql запрос", "регулярное выражение", "regex",
    # EN
    "write code", "write a function", "write a script", "fix bug",
    "debug", "refactor", "optimize code", "write tests", "unit test",
    "sql query", "implement",
]

IMAGE_GEN_TRIGGERS = [
    # RU
    "нарисуй", "сгенерируй изображение", "создай картинку",
    "нарисуй картинку", "покажи как выглядит", "изобрази",
    "сделай иллюстрацию", "создай логотип",
    # EN
    "generate image", "draw", "create image", "visualize",
    "create a logo", "illustrate",
]

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
# Фабрики провайдеров
# -------------------------------------------------------

def _nvidia(model: str, task: TaskType, reason: str) -> RouteResult:
    return RouteResult(
        task_type=task, provider=Provider.NVIDIA, model=model,
        base_url=settings.NVIDIA_BASE_URL, api_key=settings.NVIDIA_API_KEY,
        reason=reason,
    )


def _groq(model: str, task: TaskType, reason: str) -> RouteResult:
    return RouteResult(
        task_type=task, provider=Provider.GROQ, model=model,
        base_url=settings.GROQ_BASE_URL, api_key=settings.GROQ_API_KEY,
        reason=reason,
    )


def _ollama(model: str, task: TaskType, reason: str) -> RouteResult:
    return RouteResult(
        task_type=task, provider=Provider.OLLAMA, model=model,
        base_url=settings.OLLAMA_BASE_URL, api_key=settings.OLLAMA_API_KEY,
        reason=reason,
    )


# -------------------------------------------------------
# Основная функция роутинга
# -------------------------------------------------------

def route(
    message: str,
    file_mime_type: str | None = None,
    manual_model: str | None = None,
    manual_provider: str | None = None,
) -> RouteResult:
    """
    Определяет провайдера и модель для запроса.
    Порядок приоритетов:
      1. Ручной выбор пользователя
      2. Тип прикреплённого файла
      3. Триггерные слова в тексте
      4. Дефолт — GLM-5.1
    """
    is_local = settings.DEPLOYMENT_MODE == "local"

    # 1. Ручной выбор
    if manual_model:
        if is_local or manual_provider == "ollama":
            return _ollama(manual_model, TaskType.TEXT, "manual → ollama")
        if manual_provider == "groq":
            return _groq(manual_model, TaskType.TEXT, "manual → groq")
        return _nvidia(manual_model, TaskType.TEXT, "manual → nvidia")

    # 2. По типу файла
    if file_mime_type:
        if file_mime_type in AUDIO_MIME_TYPES:
            reason = f"audio ({file_mime_type})"
            if is_local:
                return _ollama(settings.LOCAL_MODEL_ASR, TaskType.ASR, reason)
            return _groq(settings.CLOUD_MODEL_ASR, TaskType.ASR, reason + " → groq whisper")

        if file_mime_type in IMAGE_MIME_TYPES:
            reason = f"image ({file_mime_type})"
            if is_local:
                return _ollama(settings.LOCAL_MODEL_VISION, TaskType.VISION, reason)
            return _nvidia(settings.CLOUD_MODEL_VISION, TaskType.VISION, reason + " → llama-3.2-90b-vision")

        if file_mime_type in DOCUMENT_MIME_TYPES:
            reason = f"document ({file_mime_type}) → RAG"
            if is_local:
                return _ollama(settings.LOCAL_MODEL_TEXT, TaskType.RAG, reason)
            return _nvidia(settings.CLOUD_MODEL_TEXT, TaskType.RAG, reason + " → glm-5.1")

    # 3. По триггерам в тексте
    msg = message.lower()

    if any(t in msg for t in IMAGE_GEN_TRIGGERS):
        # Image gen пока недоступна через стандартный NIM endpoint
        # Роутим в текст с пометкой (добавим позже)
        if is_local:
            return _ollama(settings.LOCAL_MODEL_TEXT, TaskType.TEXT, "image gen → fallback text (local)")
        return _nvidia(settings.CLOUD_MODEL_TEXT, TaskType.IMAGE_GEN, "image gen trigger → fallback glm-5.1")

    if any(t in msg for t in CODE_TRIGGERS):
        if is_local:
            return _ollama(settings.LOCAL_MODEL_CODE, TaskType.CODE, "code trigger → qwen2.5-coder (local)")
        return _nvidia(settings.CLOUD_MODEL_CODE, TaskType.CODE, "code trigger → qwen2.5-coder-32b")

    if any(t in msg for t in REASONING_TRIGGERS):
        if is_local:
            return _ollama(settings.LOCAL_MODEL_TEXT, TaskType.REASONING, "reasoning trigger → llama (local)")
        return _nvidia(settings.CLOUD_MODEL_REASONING, TaskType.REASONING, "reasoning trigger → deepseek-v3.2")

    # 4. Дефолт — GLM-5.1
    if is_local:
        return _ollama(settings.LOCAL_MODEL_TEXT, TaskType.TEXT, "default → llama3.2 (local)")
    return _nvidia(settings.CLOUD_MODEL_TEXT, TaskType.TEXT, "default → glm-5.1")


def get_embedding_config() -> tuple[str, str, str]:
    """Возвращает (base_url, api_key, model) для embedding-модели."""
    if settings.DEPLOYMENT_MODE == "local":
        return settings.OLLAMA_BASE_URL, settings.OLLAMA_API_KEY, settings.LOCAL_MODEL_EMBEDDING
    return settings.NVIDIA_BASE_URL, settings.NVIDIA_API_KEY, settings.CLOUD_MODEL_EMBEDDING
