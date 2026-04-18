"""
Чаты и сообщения — основной функционал продукта.
Стриминг через Server-Sent Events.
"""
import base64
import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Generic, TypeVar
from datetime import datetime
from app.database import get_db
from app.models.chat import Chat, Message, Document
from app.models.user import User, UserFact
from app.core.auth import get_current_user
from app.core.ai_router import route
from app.core.router import TaskType
from app.services.llm import llm_client
from app.config import get_settings
import json

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/chats", tags=["chats"])

SYSTEM_PROMPT = """Ты — Helm, корпоративный AI-ассистент.
Отвечай на русском языке, если не попросили иначе.
Будь конкретным, профессиональным и полезным."""


# --- Schemas ---

class ChatOut(BaseModel):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    model_used: str | None
    created_at: datetime

    model_config = {"from_attributes": True, "protected_namespaces": ()}


class SendMessageRequest(BaseModel):
    content: str
    file_id: int | None = None
    file_mime_type: str | None = None
    manual_model: str | None = None


T = TypeVar("T")

class PagedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    limit: int
    has_more: bool


# --- Helpers ---

def build_facts_context(facts: list[UserFact]) -> str:
    if not facts:
        return ""
    lines = [f"- {f.key}: {f.value}" for f in facts]
    return "\n\nЧто известно о пользователе:\n" + "\n".join(lines)


def _estimate_tokens(text: str) -> int:
    """Грубая оценка токенов: 1 токен ~ 4 символа (работает для RU и EN)."""
    return max(1, len(text) // 4)


async def build_messages_history(
    chat_id: int,
    db: AsyncSession,
    max_tokens: int = 6000,  # оставляем запас под system prompt и ответ модели
) -> list[dict]:
    """
    Загружает историю чата с обрезкой по токенам.
    Берёт последние сообщения (самые свежие важнее) и обрезает старые
    если суммарный объём превышает max_tokens.
    """
    result = await db.execute(
        select(Message)
        .where(Message.chat_id == chat_id)
        .order_by(Message.created_at)
        .limit(100)  # берём с запасом, потом обрезаем по токенам
    )
    messages = result.scalars().all()
    history = [{"role": m.role, "content": m.content} for m in messages]

    # Обрезаем с начала пока укладываемся в лимит
    total = sum(_estimate_tokens(m["content"]) for m in history)
    while history and total > max_tokens:
        removed = history.pop(0)
        total -= _estimate_tokens(removed["content"])

    return history


async def _get_document(file_id: int, user_id: int, db: AsyncSession) -> Document | None:
    result = await db.execute(
        select(Document).where(Document.id == file_id, Document.user_id == user_id)
    )
    return result.scalar_one_or_none()


def _build_vision_messages(messages: list[dict], image_path: str, mime_type: str) -> list[dict]:
    """
    Заменяет последнее user-сообщение на мультимодальный формат (текст + изображение).
    Совместимо с OpenAI-compatible API (NVIDIA NIM, Ollama).
    """
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")

    result = []
    for i, msg in enumerate(messages):
        if msg["role"] == "user" and i == len(messages) - 1:
            result.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": msg["content"]},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{b64}"},
                    },
                ],
            })
        else:
            result.append(msg)
    return result


# --- Endpoints ---

@router.get("", response_model=PagedResponse[ChatOut])
async def list_chats(
    page: int = 1,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import func as sqlfunc
    limit = min(max(limit, 1), 100)
    offset = (page - 1) * limit

    count_result = await db.execute(
        select(sqlfunc.count()).select_from(Chat).where(Chat.user_id == current_user.id)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(Chat)
        .where(Chat.user_id == current_user.id)
        .order_by(Chat.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    items = list(result.scalars().all())
    return PagedResponse(items=items, total=total, page=page, limit=limit, has_more=(offset + len(items)) < total)


@router.post("", response_model=ChatOut, status_code=201)
async def create_chat(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    chat = Chat(user_id=current_user.id)
    db.add(chat)
    await db.commit()
    await db.refresh(chat)
    return chat


@router.delete("/{chat_id}", status_code=204)
async def delete_chat(
    chat_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Chat).where(Chat.id == chat_id, Chat.user_id == current_user.id)
    )
    chat = result.scalar_one_or_none()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    await db.delete(chat)
    await db.commit()


@router.get("/{chat_id}/messages", response_model=PagedResponse[MessageOut])
async def get_messages(
    chat_id: int,
    page: int = 1,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import func as sqlfunc
    result = await db.execute(
        select(Chat).where(Chat.id == chat_id, Chat.user_id == current_user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Chat not found")

    limit = min(max(limit, 1), 200)
    offset = (page - 1) * limit

    count_result = await db.execute(
        select(sqlfunc.count()).select_from(Message).where(Message.chat_id == chat_id)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(Message)
        .where(Message.chat_id == chat_id)
        .order_by(Message.created_at)
        .offset(offset)
        .limit(limit)
    )
    items = list(result.scalars().all())
    return PagedResponse(items=items, total=total, page=page, limit=limit, has_more=(offset + len(items)) < total)


@router.post("/{chat_id}/messages")
async def send_message(
    chat_id: int,
    body: SendMessageRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Проверяем что чат принадлежит пользователю
    result = await db.execute(
        select(Chat).where(Chat.id == chat_id, Chat.user_id == current_user.id)
    )
    chat = result.scalar_one_or_none()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    # AI-авторутинг
    route_result = await route(
        message=body.content,
        file_mime_type=body.file_mime_type,
        manual_model=body.manual_model,
    )

    # --- ASR: транскрибируем аудио и используем текст как сообщение ---
    display_content = body.content  # то что будет сохранено в БД
    if route_result.task_type == TaskType.ASR and body.file_id:
        doc = await _get_document(body.file_id, current_user.id, db)
        if doc:
            try:
                transcription = await llm_client.transcribe(route_result, doc.path)
                display_content = f"[Голосовое сообщение]\n\n{transcription}"
                body = body.model_copy(update={"content": transcription})
                logger.info(f"ASR transcription done for doc {doc.id}")
            except Exception as e:
                logger.error(f"ASR failed: {e}")

    # Загружаем факты о пользователе (долгосрочная память)
    facts_result = await db.execute(
        select(UserFact).where(UserFact.user_id == current_user.id)
    )
    facts = facts_result.scalars().all()
    facts_context = build_facts_context(facts)

    # Сохраняем сообщение пользователя
    user_msg = Message(
        chat_id=chat_id,
        role="user",
        content=display_content,
        file_id=body.file_id,
    )
    db.add(user_msg)
    await db.commit()

    # Обновляем название чата если это первое сообщение
    msg_count_result = await db.execute(
        select(Message).where(Message.chat_id == chat_id)
    )
    if len(msg_count_result.scalars().all()) == 1:
        chat.title = body.content[:60] + ("…" if len(body.content) > 60 else "")
        await db.commit()

    # История сообщений для контекста
    history = await build_messages_history(chat_id, db)

    # --- RAG: достаём релевантные куски документа ---
    rag_context = ""
    if route_result.task_type == TaskType.RAG:
        from app.services.rag import retrieve, build_rag_context
        chunks = await retrieve(
            user_id=current_user.id,
            query=body.content,
            document_id=body.file_id,
        )
        rag_context = build_rag_context(chunks, body.content)

    # System prompt с фактами о пользователе (+ RAG-контекст если есть)
    system_prompt = SYSTEM_PROMPT + facts_context
    if rag_context:
        system_prompt = system_prompt + "\n\n" + rag_context

    llm_messages = [{"role": "system", "content": system_prompt}] + history

    # --- VISION: добавляем изображение в мультимодальный формат ---
    if route_result.task_type == TaskType.VISION and body.file_id and body.file_mime_type:
        doc = await _get_document(body.file_id, current_user.id, db)
        if doc:
            try:
                llm_messages = _build_vision_messages(
                    llm_messages, doc.path, body.file_mime_type
                )
            except Exception as e:
                logger.error(f"Vision message build failed: {e}")

    # Стриминг ответа
    async def generate():
        full_response = []

        # Мета-информация (тип задачи и модель)
        meta = {
            "type": "meta",
            "task_type": route_result.task_type.value,
            "model": route_result.model,
        }
        yield f"data: {json.dumps(meta, ensure_ascii=False)}\n\n"

        # Стримим токены
        llm_error = None
        try:
            async for token in llm_client.stream_chat(
                route=route_result,
                messages=llm_messages,
            ):
                full_response.append(token)
                chunk = {"type": "token", "content": token}
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
        except Exception as e:
            llm_error = str(e)
            logger.error(f"LLM streaming error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'detail': llm_error}, ensure_ascii=False)}\n\n"

        # Сохраняем полный ответ ассистента в БД
        full_content = "".join(full_response)
        if llm_error and not full_content:
            full_content = f"[Ошибка LLM: {llm_error}]"
        assistant_msg = Message(
            chat_id=chat_id,
            role="assistant",
            content=full_content,
            model_used=route_result.model,
        )
        db.add(assistant_msg)
        await db.commit()

        # Фоновое извлечение фактов о пользователе
        background_tasks.add_task(
            _extract_facts_background,
            user_id=current_user.id,
            user_message=body.content,
            assistant_message=full_content,
            db_url=settings.DATABASE_URL,
        )

        # Сигнал завершения
        yield f"data: {json.dumps({'type': 'done', 'message_id': assistant_msg.id}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def _extract_facts_background(
    user_id: int,
    user_message: str,
    assistant_message: str,
    db_url: str,
) -> None:
    """Фоновая задача: извлекает и сохраняет факты о пользователе."""
    from app.services.memory_extractor import extract_and_save
    await extract_and_save(user_id, user_message, assistant_message, db_url)
