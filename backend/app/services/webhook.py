"""
Webhook-диспетчер.

Отправляет HTTP POST-запросы на зарегистрированные endpoint'ы организаций
при наступлении событий в системе.

Поддерживаемые события:
  message.created    — ассистент сгенерировал ответ
  balance.low        — баланс упал ниже порога
  balance.exhausted  — баланс обнулён
  chat.created       — создан новый чат

Безопасность:
  Если для webhook задан secret, к запросу добавляется заголовок:
  X-Helm-Signature: sha256=<HMAC-SHA256(body, secret)>
  Получатель должен верифицировать подпись перед обработкой.
"""
import hashlib
import hmac
import json
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT = 10.0   # секунд на один запрос
_MAX_RETRIES = 2  # попытки при ошибке


async def dispatch_event(
    organization_id: int,
    event: str,
    payload: dict[str, Any],
    db_url: str,
) -> None:
    """
    Находит все активные webhook'и организации подписанные на event
    и отправляет им payload.

    Вызывается как BackgroundTask — ошибки логируются, не прерывают основной поток.
    """
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy import select
    from app.models.organization import Webhook

    engine = create_async_engine(db_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            result = await session.execute(
                select(Webhook).where(
                    Webhook.organization_id == organization_id,
                    Webhook.is_active == True,
                )
            )
            hooks = result.scalars().all()

        for hook in hooks:
            if event not in (hook.events or []):
                continue
            await _send_webhook(hook.url, hook.secret, event, payload)
    except Exception as exc:
        logger.warning(f"dispatch_event error (org={organization_id}, event={event}): {exc}")
    finally:
        await engine.dispose()


async def _send_webhook(
    url: str,
    secret: str | None,
    event: str,
    payload: dict[str, Any],
) -> None:
    """Делает подписанный POST-запрос на URL webhook'а."""
    body = json.dumps(
        {"event": event, "timestamp": int(time.time()), "data": payload},
        ensure_ascii=False,
    ).encode()

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "HelmWebhook/1.0",
        "X-Helm-Event": event,
    }
    if secret:
        sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        headers["X-Helm-Signature"] = f"sha256={sig}"

    for attempt in range(_MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(url, content=body, headers=headers)
                if resp.status_code < 400:
                    logger.debug(f"Webhook {event} → {url}: HTTP {resp.status_code}")
                    return
                logger.warning(
                    f"Webhook {event} → {url}: HTTP {resp.status_code} (attempt {attempt + 1})"
                )
        except Exception as exc:
            logger.warning(
                f"Webhook {event} → {url}: error {exc} (attempt {attempt + 1})"
            )
