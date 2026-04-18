"""
Чаты и сообщения — основной функционал продукта.
Стриминг через Server-Sent Events.
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime
from app.database import get_db
from app.models.chat import Chat, Message
from app.models.user import User, UserFact
from app.core.auth import get_current_user
from app.core.router import route
from app.services.llm import llm_client
import json

router = APIRouter(prefix="/chats", tags=["chats"])

SYSTEM_PROMPT = """Ты — Helm, корпоративный AI-ассистент.
Отвечай на русском языке, если не попросили иначе.
Будь конкретным, профессиональным и полезным.
{facts}"""


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

    class Config:
        from_attributes = True


class SendMessageRequest(BaseModel):
    content: str
    file_id: int | None = None
    file_mime_type: str | None = None
    manual_model: str | None = None


# --- Helpers ---

def build_facts_context(facts: list[UserFact]) -> str:
    if not facts:
        return ""
    lines = [f"- {f.key}: {f.value}" for f in facts]
    return "Что известно о пользователе:\n" + "\n".join(lines)


async def build_messages_history(chat_id: int, db: AsyncSession) -> list[dict]:
    result = await db.execute(
        select(Message)
        .where(Message.chat_id == chat_id)
        .order_by(Message.created_at)
        .limit(50)  # последние 50 сообщений для контекста
    )
    messages = result.scalars().all()
    return [{"role": m.role, "content": m.content} for m in messages]


# --- Endpoints ---

@router.get("", response_model=list[ChatOut])
async def list_chats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Chat)
        .where(Chat.user_id == current_user.id)
        .order_by(Chat.updated_at.desc())
    )
    return result.scalars().all()


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


@router.get("/{chat_id}/messages", response_model=list[MessageOut])
async def get_messages(
    chat_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Chat).where(Chat.id == chat_id, Chat.user_id == current_user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Chat not found")

    result = await db.execute(
        select(Message).where(Message.chat_id == chat_id).order_by(Message.created_at)
    )
    return result.scalars().all()


@router.post("/{chat_id}/messages")
async def send_message(
    chat_id: int,
    body: SendMessageRequest,
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

    # Авторутинг
    route_result = route(
        message=body.content,
        file_mime_type=body.file_mime_type,
        manual_model=body.manual_model,
    )

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
        content=body.content,
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

    # System prompt с фактами о пользователе
    system_prompt = SYSTEM_PROMPT.format(facts=facts_context)
    llm_messages = [{"role": "system", "content": system_prompt}] + history

    # Стриминг ответа
    async def generate():
        full_response = []

        # Сначала отправляем мета-информацию (тип задачи и модель)
        meta = {
            "type": "meta",
            "task_type": route_result.task_type.value,
            "model": route_result.model,
        }
        yield f"data: {json.dumps(meta, ensure_ascii=False)}\n\n"

        # Стримим токены
        async for token in llm_client.stream_chat(
            model=route_result.model,
            messages=llm_messages,
        ):
            full_response.append(token)
            chunk = {"type": "token", "content": token}
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

        # Сохраняем полный ответ ассистента в БД
        full_content = "".join(full_response)
        assistant_msg = Message(
            chat_id=chat_id,
            role="assistant",
            content=full_content,
            model_used=route_result.model,
        )
        db.add(assistant_msg)
        await db.commit()

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
