"""
Helm Auto-Router — определяет тип задачи, выбирает провайдера и модель.

Два режима:
  cloud → NVIDIA NIM (LLM/Vision/ImageGen/Embeddings) + Groq (ASR)
  local → Ollama (всё локально, air-gapped, 152-ФЗ compliant)

Пользователь не думает о выборе модели и провайдера — это делает Helm.
"""
from enum import Enum
from dataclasses import dataclass
from app.config import get_settings

settings = get_settings()


class TaskType(str, Enum):
    TEXT = "text"
    VISION = "vision"
    ASR = "asr"
    IMAGE_GEN = "image_gen"
    RAG = "rag"


class Provider(str, Enum):
    NVIDIA = "nvidia"   # NVIDIA NIM
    GROQ = "groq"       # Groq (ASR + fast LLM)
    OLLAMA = "ollama"   # Локальные модели


@dataclass
class RouteResult:
    task_type: TaskType
    provider: Provider
    model: str
    base_url: str
    api_key: str
    reason: str


# --- Триггеры ---

IMAGE_GEN_TRIGGERS = [
    "нарисуй", "сгенерируй изображение", "создай картинку", "нарисуй картинку",
    "generate image", "draw", "create image", "visualize", "покажи как выглядит",
    "изобрази", "сделай иллюстрацию",
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


# --- Фабрики провайдеров ---

def _nvidia(model: str, task: TaskType, reason: str) -> RouteResult:
    return RouteResult(
        task_type=task,
        provider=Provider.NVIDIA,
        model=model,
        base_url=settings.NVIDIA_BASE_URL,
        api_key=settings.NVIDIA_API_KEY,
        reason=reason,
    )


def _groq(model: str, task: TaskType, reason: str) -> RouteResult:
    return RouteResult(
        task_type=task,
        provider=Provider.GROQ,
        model=model,
        base_url=settings.GROQ_BASE_URL,
        api_key=settings.GROQ_API_KEY,
        reason=reason,
    )


def _ollama(model: str, task: TaskType, reason: str) -> RouteResult:
    return RouteResult(
        task_type=task,
        provider=Provider.OLLAMA,
        model=model,
        base_url=settings.OLLAMA_BASE_URL,
        api_key=settings.OLLAMA_API_KEY,
        reason=reason,
    )


# --- Основная функция роутинга ---

def route(
    message: str,
    file_mime_type: str | None = None,
    manual_model: str | None = None,
    manual_provider: str | None = None,
) -> RouteResult:
    """
    Определяет провайдера и модель для обработки запроса.

    Args:
        message:         Текст сообщения пользователя
        file_mime_type:  MIME-тип прикреплённого файла (если есть)
        manual_model:    Явный выбор модели (переопределяет авторутинг)
        manual_provider: Явный выбор провайдера (nvidia | groq | ollama)
    """
    is_local = settings.DEPLOYMENT_MODE == "local"

    # --- Ручной выбор ---
    if manual_model:
        if is_local or manual_provider == "ollama":
            return _ollama(manual_model, TaskType.TEXT, "manual override → ollama")
        if manual_provider == "groq":
            return _groq(manual_model, TaskType.TEXT, "manual override → groq")
        return _nvidia(manual_model, TaskType.TEXT, "manual override → nvidia")

    # --- Авторутинг ---

    # Аудио → ASR
    if file_mime_type and file_mime_type in AUDIO_MIME_TYPES:
        reason = f"audio file ({file_mime_type})"
        if is_local:
            return _ollama(settings.LOCAL_MODEL_ASR, TaskType.ASR, reason + " → ollama whisper")
        return _groq(settings.CLOUD_MODEL_ASR, TaskType.ASR, reason + " → groq whisper")

    # Изображение → Vision LLM
    if file_mime_type and file_mime_type in IMAGE_MIME_TYPES:
        reason = f"image file ({file_mime_type})"
        if is_local:
            return _ollama(settings.LOCAL_MODEL_VISION, TaskType.VISION, reason + " → ollama llava")
        return _nvidia(settings.CLOUD_MODEL_VISION, TaskType.VISION, reason + " → nvidia llama-4-scout")

    # Документ → RAG pipeline
    if file_mime_type and file_mime_type in DOCUMENT_MIME_TYPES:
        reason = f"document ({file_mime_type}) → RAG"
        if is_local:
            return _ollama(settings.LOCAL_MODEL_TEXT, TaskType.RAG, reason + " → ollama")
        return _nvidia(settings.CLOUD_MODEL_TEXT, TaskType.RAG, reason + " → nvidia")

    # Генерация изображений по тексту
    message_lower = message.lower()
    if any(trigger in message_lower for trigger in IMAGE_GEN_TRIGGERS):
        if is_local:
            # Локальная image gen не поддерживается — отвечаем текстом
            return _ollama(
                settings.LOCAL_MODEL_TEXT, TaskType.TEXT,
                "image gen not available in local mode, fallback to text"
            )
        return _nvidia(settings.CLOUD_MODEL_IMAGE_GEN, TaskType.IMAGE_GEN, "image gen trigger detected")

    # По умолчанию — текстовая LLM
    if is_local:
        return _ollama(settings.LOCAL_MODEL_TEXT, TaskType.TEXT, "default text → ollama")
    return _nvidia(settings.CLOUD_MODEL_TEXT, TaskType.TEXT, "default text → nvidia")


def get_embedding_config() -> tuple[str, str, str]:
    """Возвращает (base_url, api_key, model) для embedding-модели."""
    if settings.DEPLOYMENT_MODE == "local":
        return settings.OLLAMA_BASE_URL, settings.OLLAMA_API_KEY, settings.LOCAL_MODEL_EMBEDDING
    return settings.NVIDIA_BASE_URL, settings.NVIDIA_API_KEY, settings.CLOUD_MODEL_EMBEDDING
