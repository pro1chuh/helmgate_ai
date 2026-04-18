"""
Helm Auto-Router — определяет тип задачи и выбирает подходящую модель.
Это ключевой дифференциатор продукта: пользователь не думает о выборе модели.
"""
from enum import Enum
from dataclasses import dataclass
from app.config import get_settings

settings = get_settings()


class TaskType(str, Enum):
    TEXT = "text"           # Обычный текстовый запрос
    VISION = "vision"       # Анализ изображения
    ASR = "asr"             # Расшифровка аудио
    IMAGE_GEN = "image_gen" # Генерация изображения
    RAG = "rag"             # Ответ по документу


@dataclass
class RouteResult:
    task_type: TaskType
    model: str
    reason: str             # Объяснение выбора (для логов/дебага)


# Триггеры генерации изображений
IMAGE_GEN_TRIGGERS = [
    "нарисуй", "сгенерируй изображение", "создай картинку",
    "generate image", "draw", "create image", "visualize",
    "покажи как выглядит", "изобрази",
]

# MIME-типы изображений
IMAGE_MIME_TYPES = {
    "image/jpeg", "image/png", "image/gif",
    "image/webp", "image/bmp", "image/tiff",
}

# MIME-типы аудио
AUDIO_MIME_TYPES = {
    "audio/mpeg", "audio/mp3", "audio/wav",
    "audio/ogg", "audio/flac", "audio/m4a",
    "audio/webm", "video/webm",
}

# MIME-типы документов (для RAG)
DOCUMENT_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "text/plain", "text/csv", "text/markdown",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def route(
    message: str,
    file_mime_type: str | None = None,
    manual_model: str | None = None,
) -> RouteResult:
    """
    Определяет модель для обработки запроса.

    Args:
        message: Текст сообщения пользователя
        file_mime_type: MIME-тип прикреплённого файла (если есть)
        manual_model: Явный выбор модели пользователем (переопределяет авторутинг)

    Returns:
        RouteResult с моделью и причиной выбора
    """
    # Ручной выбор модели имеет приоритет
    if manual_model:
        return RouteResult(
            task_type=TaskType.TEXT,
            model=manual_model,
            reason="manual override by user",
        )

    # Аудио → ASR
    if file_mime_type and file_mime_type in AUDIO_MIME_TYPES:
        return RouteResult(
            task_type=TaskType.ASR,
            model=settings.MODEL_ASR,
            reason=f"audio file detected ({file_mime_type})",
        )

    # Изображение → Vision LLM
    if file_mime_type and file_mime_type in IMAGE_MIME_TYPES:
        return RouteResult(
            task_type=TaskType.VISION,
            model=settings.MODEL_VISION,
            reason=f"image file detected ({file_mime_type})",
        )

    # Документ → RAG
    if file_mime_type and file_mime_type in DOCUMENT_MIME_TYPES:
        return RouteResult(
            task_type=TaskType.RAG,
            model=settings.MODEL_TEXT,
            reason=f"document file detected ({file_mime_type}), RAG pipeline",
        )

    # Генерация изображений по тексту
    message_lower = message.lower()
    if any(trigger in message_lower for trigger in IMAGE_GEN_TRIGGERS):
        return RouteResult(
            task_type=TaskType.IMAGE_GEN,
            model=settings.MODEL_IMAGE_GEN,
            reason="image generation trigger detected in message",
        )

    # По умолчанию — основная текстовая LLM
    return RouteResult(
        task_type=TaskType.TEXT,
        model=settings.MODEL_TEXT,
        reason="default text routing",
    )
