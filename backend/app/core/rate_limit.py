"""
In-memory rate limiter — скользящее окно 60 секунд на пользователя.
Не требует Redis. При перезапуске счётчики сбрасываются — приемлемо для MVP.
"""
import time
import logging
from collections import defaultdict, deque
from fastapi import HTTPException
from app.core.metrics import rate_limit_hits_total

logger = logging.getLogger(__name__)

# Лимит запросов и размер окна в секундах
_LIMIT = 20
_WINDOW = 60.0

# user_id -> deque с timestamp каждого запроса
_buckets: dict[int, deque] = defaultdict(deque)


def check_rate_limit(user_id: int) -> None:
    """
    Проверяет лимит запросов для пользователя.
    Вызывается перед каждым send_message.
    Выбрасывает HTTP 429 если лимит превышен.
    """
    now = time.monotonic()
    bucket = _buckets[user_id]

    # Удаляем устаревшие записи за пределами окна
    while bucket and now - bucket[0] > _WINDOW:
        bucket.popleft()

    if len(bucket) >= _LIMIT:
        oldest = bucket[0]
        retry_after = int(_WINDOW - (now - oldest)) + 1
        logger.warning(f"Rate limit exceeded for user {user_id}: {len(bucket)} req/min")
        rate_limit_hits_total.inc()
        raise HTTPException(
            status_code=429,
            detail=f"Слишком много запросов. Повторите через {retry_after} секунд.",
            headers={"Retry-After": str(retry_after)},
        )

    bucket.append(now)
