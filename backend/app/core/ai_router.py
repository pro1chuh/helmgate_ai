"""
Helm AI-Router — классифицирует запрос через LLM и выбирает нужную модель.

Преимущество перед keyword-matching:
  "у меня не работает функция" → понимает что это CODE, без слова "код"
  "составь документацию к классу" → понимает контекст
  "разбери этот договор" → понимает что нужен анализ

Модель-роутер: gemma-3-4b-it (4B, быстрая, дешёвая, ~200-400ms)
Все запросы идут через OpenRouter.

Оптимизации:
  1. _quick_classify  — мгновенный pre-check по структурным сигналам (```, def, SELECT…)
  2. _classify_cached — LRU-кеш на 500 записей по MD5 первых 120 символов
  3. _classify        — использует общий httpx-пул из llm_client
"""
import hashlib
import json
import logging
from app.config import get_settings
from app.core.metrics import classifier_cache_hits_total, classifier_quick_hits_total
from app.core.router import (
    TaskType, RouteResult,
    IMAGE_MIME_TYPES, AUDIO_MIME_TYPES, DOCUMENT_MIME_TYPES,
    _openrouter, _groq, task_to_route,
)

logger = logging.getLogger(__name__)
settings = get_settings()

# ---------------------------------------------------------------------------
# Quick pre-check: структурные сигналы кода
# ---------------------------------------------------------------------------

_CODE_STRUCTURAL = (
    "```",
    "def ",
    "class ",
    "import ",
    "SELECT ",
    "INSERT INTO",
    "UPDATE ",
    "function ",
    "const ",
    "async def ",
    "public static",
    "<?php",
    "#include",
)


def _quick_classify(message: str) -> TaskType | None:
    """
    Мгновенный pre-check по структурным сигналам кода.
    Возвращает TaskType.CODE если сигнал однозначен, иначе None.
    """
    if len(message) < 10:
        return None
    msg_head = message[:300]
    for signal in _CODE_STRUCTURAL:
        if signal in msg_head:
            logger.debug(f"Quick classify → CODE (signal: {signal!r})")
            return TaskType.CODE
    return None


# ---------------------------------------------------------------------------
# LRU-кеш классификации
# ---------------------------------------------------------------------------

_classify_cache: dict[str, TaskType] = {}
_CACHE_MAX = 500


def _cache_key(message: str) -> str:
    return hashlib.md5(message[:120].lower().strip().encode()).hexdigest()


async def _classify_cached(message: str) -> TaskType:
    """
    1. Quick pre-check (структурные сигналы)
    2. LRU-кеш
    3. AI-классификатор (gemma-3-4b-it)
    """
    quick = _quick_classify(message)
    if quick is not None:
        classifier_quick_hits_total.inc()
        return quick

    key = _cache_key(message)
    if key in _classify_cache:
        logger.debug(f"AI router cache hit: {key[:8]}")
        classifier_cache_hits_total.inc()
        return _classify_cache[key]

    result = await _classify(message)

    if len(_classify_cache) >= _CACHE_MAX:
        del _classify_cache[next(iter(_classify_cache))]
    _classify_cache[key] = result
    return result


ROUTER_PROMPT = """\
Ты — классификатор задач. Проанализируй сообщение и верни ТОЛЬКО валидный JSON без пояснений.

Типы задач:
- "text": обычный вопрос, объяснение, перевод, резюме, общение, помощь с текстом
- "code": написать/исправить/объяснить код, функцию, скрипт, класс, баг, SQL, regex, тесты, рефакторинг
- "reasoning": глубокий анализ, сравнение вариантов, стратегия, прогноз, оценка рисков, бизнес-план
- "image_gen": нарисовать, сгенерировать или создать изображение, иллюстрацию, логотип

Примеры:
- "привет" → {{"task": "text"}}
- "напиши функцию сортировки" → {{"task": "code"}}
- "почему падает этот код?" → {{"task": "code"}}
- "сравни микросервисы и монолит" → {{"task": "reasoning"}}
- "нарисуй логотип стартапа" → {{"task": "image_gen"}}

Формат: {{"task": "text"}}

Сообщение: {message}"""


async def _classify(message: str) -> TaskType:
    """
    Отправляет сообщение в gemma-3-4b-it через OpenRouter и получает тип задачи.
    При любой ошибке возвращает TEXT (безопасный дефолт).
    """
    from app.services.llm import llm_client

    payload = {
        "model": settings.MODEL_ROUTER,
        "messages": [
            {"role": "user", "content": ROUTER_PROMPT.format(message=message[:500])},
        ],
        "temperature": 0.0,
        "max_tokens": 20,
        "stream": False,
    }

    try:
        response = await llm_client._client.post(
            f"{settings.OPENROUTER_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {settings.OPENROUTER_API_KEY}"},
            json=payload,
            timeout=5.0,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"].strip()
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


async def route(
    message: str,
    file_mime_type: str | None = None,
    manual_model: str | None = None,
    manual_provider: str | None = None,
) -> RouteResult:
    """
    Главная функция роутинга (async, с AI-классификацией).

    Порядок приоритетов:
      1. Ручной выбор модели
      2. Тип прикреплённого файла (детерминированно, без AI)
      3. AI-классификация текста (gemma-3-4b-it)
    """
    # 1. Ручной выбор
    if manual_model:
        if manual_provider == "groq":
            return _groq(manual_model, TaskType.ASR, "manual → groq")
        return _openrouter(manual_model, TaskType.TEXT, "manual → openrouter")

    # 2. По типу файла
    if file_mime_type:
        if file_mime_type in AUDIO_MIME_TYPES:
            return _groq(settings.MODEL_ASR, TaskType.ASR, "audio → groq whisper")
        if file_mime_type in IMAGE_MIME_TYPES:
            return _openrouter(settings.MODEL_VISION, TaskType.VISION, f"image → {settings.MODEL_VISION}")
        if file_mime_type in DOCUMENT_MIME_TYPES:
            return _openrouter(settings.MODEL_TEXT, TaskType.RAG, f"doc → RAG {settings.MODEL_TEXT}")

    # 3. AI-классификация
    task = await _classify_cached(message)
    return task_to_route(task)
