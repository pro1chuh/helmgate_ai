"""
Redis-кэш для Helm.

Используется для:
  - Кэширования результатов LLM-запросов (идентичные промпты → кэшированный ответ)
  - Хранения счётчиков суточных токенов пользователей
  - Circuit breaker state (общее состояние между воркерами)

Если Redis недоступен — все операции молча деградируют (fallback к None / False).
Это обеспечивает work without Redis for local/offline setups.
"""
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

_redis = None


async def get_redis():
    """Возвращает Redis-клиент (lazy init). При ошибке — None."""
    global _redis
    if _redis is not None:
        return _redis
    try:
        from redis.asyncio import from_url
        from app.config import get_settings
        settings = get_settings()
        _redis = from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=2)
        await _redis.ping()
        logger.info("Redis connected")
    except Exception as exc:
        logger.warning(f"Redis unavailable, caching disabled: {exc}")
        _redis = None
    return _redis


async def close_redis():
    """Закрывает соединение при остановке приложения."""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

async def cache_get(key: str) -> Any | None:
    """Читает значение из кэша. None если нет или Redis недоступен."""
    r = await get_redis()
    if r is None:
        return None
    try:
        raw = await r.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception as exc:
        logger.debug(f"cache_get error [{key}]: {exc}")
        return None


async def cache_set(key: str, value: Any, ttl: int = 3600) -> bool:
    """Записывает значение в кэш с TTL в секундах. False если Redis недоступен."""
    r = await get_redis()
    if r is None:
        return False
    try:
        await r.setex(key, ttl, json.dumps(value, ensure_ascii=False))
        return True
    except Exception as exc:
        logger.debug(f"cache_set error [{key}]: {exc}")
        return False


async def cache_delete(key: str) -> bool:
    r = await get_redis()
    if r is None:
        return False
    try:
        await r.delete(key)
        return True
    except Exception as exc:
        logger.debug(f"cache_delete error [{key}]: {exc}")
        return False


# ---------------------------------------------------------------------------
# Daily token counter (per-user)
# ---------------------------------------------------------------------------

async def increment_daily_tokens(user_id: int, tokens: int) -> int:
    """
    Увеличивает счётчик токенов пользователя за сегодня.
    Ключ живёт до конца суток (UTC). Возвращает новое значение.
    """
    r = await get_redis()
    if r is None:
        return 0
    import datetime
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    key = f"daily_tokens:{user_id}:{today}"
    try:
        total = await r.incrby(key, tokens)
        # TTL = секунд до конца суток + 5 минут запаса
        now = datetime.datetime.utcnow()
        midnight = (now + datetime.timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        ttl = int((midnight - now).total_seconds()) + 300
        await r.expire(key, ttl)
        return int(total)
    except Exception as exc:
        logger.debug(f"increment_daily_tokens error: {exc}")
        return 0


async def get_daily_tokens(user_id: int) -> int:
    """Возвращает количество токенов использованных пользователем сегодня."""
    r = await get_redis()
    if r is None:
        return 0
    import datetime
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    key = f"daily_tokens:{user_id}:{today}"
    try:
        val = await r.get(key)
        return int(val) if val else 0
    except Exception as exc:
        logger.debug(f"get_daily_tokens error: {exc}")
        return 0


# ---------------------------------------------------------------------------
# Circuit breaker state (shared across workers)
# ---------------------------------------------------------------------------

async def cb_get_failures(provider: str) -> int:
    r = await get_redis()
    if r is None:
        return 0
    try:
        val = await r.get(f"cb:failures:{provider}")
        return int(val) if val else 0
    except Exception:
        return 0


async def cb_increment_failures(provider: str, cooldown: int) -> int:
    r = await get_redis()
    if r is None:
        return 0
    try:
        key = f"cb:failures:{provider}"
        val = await r.incr(key)
        await r.expire(key, cooldown * 2)
        return int(val)
    except Exception:
        return 0


async def cb_reset_failures(provider: str) -> None:
    r = await get_redis()
    if r is None:
        return
    try:
        await r.delete(f"cb:failures:{provider}")
        await r.delete(f"cb:open:{provider}")
    except Exception:
        pass


async def cb_is_open(provider: str) -> bool:
    r = await get_redis()
    if r is None:
        return False
    try:
        return bool(await r.exists(f"cb:open:{provider}"))
    except Exception:
        return False


async def cb_open(provider: str, cooldown: int) -> None:
    r = await get_redis()
    if r is None:
        return
    try:
        await r.setex(f"cb:open:{provider}", cooldown, "1")
    except Exception:
        pass
