"""
Чаты и сообщения — основной функционал продукта.
Стриминг через Server-Sent Events.
"""
import asyncio
import base64
import io
import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from fastapi.responses import StreamingResponse, Response
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
from app.core.rate_limit import check_rate_limit
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
    system_prompt: str | None
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


class CreateChatRequest(BaseModel):
    title: str | None = None
    system_prompt: str | None = None


class UpdateChatRequest(BaseModel):
    title: str | None = None
    system_prompt: str | None = None


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
    body: CreateChatRequest = CreateChatRequest(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    chat = Chat(
        user_id=current_user.id,
        title=body.title or "Новый чат",
        system_prompt=body.system_prompt,
    )
    db.add(chat)
    await db.commit()
    await db.refresh(chat)
    return chat


@router.patch("/{chat_id}", response_model=ChatOut)
async def update_chat(
    chat_id: int,
    body: UpdateChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Chat).where(Chat.id == chat_id, Chat.user_id == current_user.id)
    )
    chat = result.scalar_one_or_none()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    if body.title is not None:
        chat.title = body.title
    if body.system_prompt is not None:
        chat.system_prompt = body.system_prompt
    await db.commit()
    await db.refresh(chat)
    return chat


@router.get("/search", response_model=PagedResponse[ChatOut])
async def search_chats(
    q: str,
    page: int = 1,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Полнотекстовый поиск по названиям чатов и содержимому сообщений.
    Использует PostgreSQL ILIKE для простого и надёжного поиска.
    """
    from sqlalchemy import func as sqlfunc, or_
    limit = min(max(limit, 1), 100)
    offset = (page - 1) * limit
    q_pattern = f"%{q}%"

    # Находим chat_id где есть совпадение в сообщениях
    msg_subq = (
        select(Message.chat_id)
        .where(Message.content.ilike(q_pattern))
        .scalar_subquery()
    )

    base_filter = (
        Chat.user_id == current_user.id,
        or_(
            Chat.title.ilike(q_pattern),
            Chat.id.in_(msg_subq),
        ),
    )

    count_result = await db.execute(
        select(sqlfunc.count()).select_from(Chat).where(*base_filter)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(Chat)
        .where(*base_filter)
        .order_by(Chat.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    items = list(result.scalars().all())
    return PagedResponse(items=items, total=total, page=page, limit=limit, has_more=(offset + len(items)) < total)


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


@router.get("/{chat_id}/export")
async def export_chat(
    chat_id: int,
    format: str = Query(default="md", pattern="^(md|pdf)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Экспорт чата.
    format=md  — Markdown (text/markdown)
    format=pdf — PDF (application/pdf)
    """
    result = await db.execute(
        select(Chat).where(Chat.id == chat_id, Chat.user_id == current_user.id)
    )
    chat = result.scalar_one_or_none()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    result = await db.execute(
        select(Message).where(Message.chat_id == chat_id).order_by(Message.created_at)
    )
    messages = result.scalars().all()

    if format == "md":
        lines = [f"# {chat.title}\n"]
        for m in messages:
            role_label = "**Пользователь**" if m.role == "user" else f"**Helm** _{m.model_used or ''}_"
            lines.append(f"### {role_label}\n{m.content}\n")
        content = "\n".join(lines)
        filename = f"chat_{chat_id}.md"
        return Response(
            content=content.encode("utf-8"),
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # PDF
    try:
        from fpdf import FPDF
    except ImportError:
        raise HTTPException(status_code=501, detail="PDF export not available: fpdf2 not installed")

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    title_safe = chat.title.encode("latin-1", "replace").decode("latin-1")
    pdf.cell(0, 10, title_safe, ln=True)
    pdf.ln(4)

    for m in messages:
        pdf.set_font("Helvetica", "B", 10)
        role_label = "Пользователь:" if m.role == "user" else f"Helm ({m.model_used or 'AI'}):"
        label_safe = role_label.encode("latin-1", "replace").decode("latin-1")
        pdf.cell(0, 6, label_safe, ln=True)
        pdf.set_font("Helvetica", "", 10)
        text_safe = m.content.encode("latin-1", "replace").decode("latin-1")
        pdf.multi_cell(0, 5, text_safe)
        pdf.ln(3)

    buf = io.BytesIO(pdf.output())
    filename = f"chat_{chat_id}.pdf"
    return Response(
        content=buf.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{chat_id}/messages")
async def send_message(
    chat_id: int,
    body: SendMessageRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Rate limiting — 20 запросов/минуту на пользователя
    check_rate_limit(current_user.id)

    # Проверяем баланс организации
    from app.services.billing import check_balance
    if not await check_balance(current_user.organization_id, db):
        raise HTTPException(
            status_code=402,
            detail="Баланс организации исчерпан. Обратитесь к администратору для пополнения.",
        )

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

    # System prompt: кастомный для чата или дефолтный
    base_prompt = chat.system_prompt if chat.system_prompt else SYSTEM_PROMPT
    system_prompt = base_prompt + facts_context
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

        llm_error = None

        # --- IMAGE GEN: одиночный запрос вместо стрима ---
        if route_result.task_type == TaskType.IMAGE_GEN:
            try:
                async with asyncio.timeout(120):
                    image_url = await llm_client.generate_image(route_result, body.content)
                full_response.append(image_url)
                yield f"data: {json.dumps({'type': 'image', 'url': image_url}, ensure_ascii=False)}\n\n"
            except TimeoutError:
                llm_error = "Превышено время генерации изображения (120 сек)"
                logger.error(f"Image gen timeout for chat {chat_id}")
                yield f"data: {json.dumps({'type': 'error', 'detail': llm_error}, ensure_ascii=False)}\n\n"
            except Exception as e:
                llm_error = str(e)
                logger.error(f"Image gen error: {e}")
                yield f"data: {json.dumps({'type': 'error', 'detail': llm_error}, ensure_ascii=False)}\n\n"

        else:
            # Стримим токены с таймаутом 90 секунд на всю генерацию
            try:
                async def _stream():
                    async for token in llm_client.stream_chat(
                        route=route_result,
                        messages=llm_messages,
                    ):
                        full_response.append(token)
                        chunk = {"type": "token", "content": token}
                        yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

                async with asyncio.timeout(90):
                    async for sse_chunk in _stream():
                        yield sse_chunk

            except TimeoutError:
                llm_error = "Превышено время ожидания ответа (90 сек)"
                logger.error(f"LLM generation timeout for chat {chat_id}")
                yield f"data: {json.dumps({'type': 'error', 'detail': llm_error}, ensure_ascii=False)}\n\n"
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

        # Биллинг — логируем и списываем с баланса организации
        if current_user.organization_id:
            input_tokens = max(1, sum(len(m.get("content", "") or "") // 4 for m in llm_messages))
            output_tokens = max(1, len(full_content) // 4)
            background_tasks.add_task(
                _billing_background,
                organization_id=current_user.organization_id,
                user_id=current_user.id,
                model=route_result.model,
                task_type=route_result.task_type.value,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                db_url=settings.DATABASE_URL,
            )

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


async def _billing_background(
    organization_id: int,
    user_id: int,
    model: str,
    task_type: str,
    input_tokens: int,
    output_tokens: int,
    db_url: str,
) -> None:
    """Фоновая задача: списывает стоимость запроса с баланса организации."""
    from app.services.billing import log_and_deduct
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

    engine = create_async_engine(db_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        await log_and_deduct(organization_id, user_id, model, task_type, input_tokens, output_tokens, session)
    await engine.dispose()


async def _extract_facts_background(
    user_id: int,
    user_message: str,
    assistant_message: str,
    db_url: str,
) -> None:
    """Фоновая задача: извлекает и сохраняет факты о пользователе."""
    from app.services.memory_extractor import extract_and_save
    await extract_and_save(user_id, user_message, assistant_message, db_url)
