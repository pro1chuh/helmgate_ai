"""
Batch API — обработка нескольких сообщений за один запрос.

Полезно для:
  - Автоматической обработки документов (анализ нескольких секций)
  - Тестирования промптов
  - Массовой генерации контента

Стриминг не поддерживается — возвращает полные ответы.
Максимум 10 сообщений за запрос.
"""
import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from datetime import datetime
from app.database import get_db
from app.core.auth import get_current_user
from app.core.rate_limit import check_rate_limit
from app.models.user import User
from app.models.chat import Chat, Message
from app.services.llm import llm_client
from app.core.ai_router import route
from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/batch", tags=["batch"])
settings = get_settings()

_BATCH_MAX = 10
_BATCH_TIMEOUT = 300  # 5 минут на весь батч


class BatchMessageIn(BaseModel):
    content: str = Field(..., max_length=10000)
    system_prompt: str | None = None
    manual_model: str | None = None


class BatchMessageOut(BaseModel):
    index: int
    content: str
    response: str | None
    model: str | None
    error: str | None
    input_tokens: int
    output_tokens: int


class BatchRequest(BaseModel):
    messages: list[BatchMessageIn] = Field(..., min_length=1, max_length=_BATCH_MAX)
    save_to_chat_id: int | None = None  # если указан — сохраняет в чат


class BatchResponse(BaseModel):
    results: list[BatchMessageOut]
    total_input_tokens: int
    total_output_tokens: int
    processed: int
    failed: int


SYSTEM_PROMPT = """Ты — Helm, корпоративный AI-ассистент.
Отвечай на русском языке, если не попросили иначе.
Будь конкретным, профессиональным и полезным."""


@router.post("", response_model=BatchResponse)
async def batch_process(
    body: BatchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Обрабатывает список сообщений последовательно и возвращает все ответы.
    Максимум 10 сообщений за запрос. Таймаут 5 минут на всё.
    """
    # Rate limiting — считаем как N запросов
    check_rate_limit(current_user.id)

    from app.services.billing import check_balance
    if not await check_balance(current_user.organization_id, db):
        raise HTTPException(status_code=402, detail="Баланс организации исчерпан.")

    # Валидируем chat если нужно
    chat = None
    if body.save_to_chat_id:
        result = await db.execute(
            select(Chat).where(
                Chat.id == body.save_to_chat_id,
                Chat.user_id == current_user.id,
            )
        )
        chat = result.scalar_one_or_none()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")

    results: list[BatchMessageOut] = []
    total_input = 0
    total_output = 0
    failed = 0

    async def _process_one(idx: int, msg: BatchMessageIn) -> BatchMessageOut:
        nonlocal total_input, total_output, failed
        try:
            route_result = await route(
                message=msg.content,
                manual_model=msg.manual_model,
            )
            sys_prompt = msg.system_prompt or SYSTEM_PROMPT
            messages = [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": msg.content},
            ]
            usage_out: dict = {}
            tokens = []
            async for token in llm_client.stream_chat(
                route=route_result,
                messages=messages,
                usage_out=usage_out,
            ):
                tokens.append(token)

            response_text = "".join(tokens)
            inp = usage_out.get("input_tokens", max(1, len(msg.content) // 4))
            out = usage_out.get("output_tokens", max(1, len(response_text) // 4))
            total_input += inp
            total_output += out

            # Сохраняем в чат если нужно
            if chat:
                db.add(Message(chat_id=chat.id, role="user", content=msg.content))
                db.add(Message(chat_id=chat.id, role="assistant", content=response_text, model_used=route_result.model))
                await db.commit()

            return BatchMessageOut(
                index=idx,
                content=msg.content,
                response=response_text,
                model=route_result.model,
                error=None,
                input_tokens=inp,
                output_tokens=out,
            )
        except Exception as exc:
            failed += 1
            logger.error(f"Batch item {idx} failed: {exc}")
            return BatchMessageOut(
                index=idx,
                content=msg.content,
                response=None,
                model=None,
                error=str(exc),
                input_tokens=0,
                output_tokens=0,
            )

    try:
        async with asyncio.timeout(_BATCH_TIMEOUT):
            for idx, msg in enumerate(body.messages):
                result = await _process_one(idx, msg)
                results.append(result)
    except TimeoutError:
        raise HTTPException(
            status_code=408,
            detail=f"Батч не завершился за {_BATCH_TIMEOUT} секунд. "
                   "Уменьшите количество сообщений или длину промптов."
        )

    # Биллинг за весь батч
    if current_user.organization_id and total_input > 0:
        from app.services.billing import log_and_deduct
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        engine = create_async_engine(settings.DATABASE_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with session_factory() as session:
                await log_and_deduct(
                    organization_id=current_user.organization_id,
                    user_id=current_user.id,
                    model="batch/mixed",
                    task_type="batch",
                    input_tokens=total_input,
                    output_tokens=total_output,
                    db=session,
                )
        finally:
            await engine.dispose()

    return BatchResponse(
        results=results,
        total_input_tokens=total_input,
        total_output_tokens=total_output,
        processed=len(results) - failed,
        failed=failed,
    )
