"""
Загрузка файлов и запуск индексации для RAG.
"""
import os
import uuid
import aiofiles
from sqlalchemy import func as sqlfunc
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime
from app.database import get_db
from app.models.chat import Document
from app.models.user import User
from app.core.auth import get_current_user
from app.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/files", tags=["files"])

MAX_FILES_PER_USER = 50
MAX_TOTAL_SIZE_MB = 500

ALLOWED_MIME_TYPES = {
    # Документы
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "text/plain",
    "text/csv",
    "text/markdown",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    # Изображения
    "image/jpeg", "image/png", "image/gif", "image/webp",
    # Аудио
    "audio/mpeg", "audio/wav", "audio/ogg", "audio/flac",
    "audio/m4a", "audio/webm",
}

DOCUMENT_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "text/plain", "text/csv", "text/markdown",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


class FileOut(BaseModel):
    id: int
    filename: str
    mime_type: str
    size_bytes: int
    indexed: bool
    created_at: datetime

    class Config:
        from_attributes = True


async def _index_in_background(
    user_id: int,
    document_id: int,
    file_path: str,
    mime_type: str,
    filename: str,
    db_url: str,
):
    """Запускает индексацию документа в фоне."""
    from app.services.rag import index_document
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from app.models.chat import Document as Doc

    try:
        chunks = await index_document(user_id, document_id, file_path, mime_type, filename)

        # Обновляем флаг indexed в БД
        engine = create_async_engine(db_url)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            result = await session.execute(select(Doc).where(Doc.id == document_id))
            doc = result.scalar_one_or_none()
            if doc:
                doc.indexed = True
                await session.commit()
        await engine.dispose()

    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Background indexing failed: {e}")


@router.post("", response_model=FileOut, status_code=201)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Читаем содержимое
    contents = await file.read()
    size = len(contents)

    # 1. Валидация MIME по реальному содержимому (magic bytes), не по заголовку
    try:
        import filetype as ft
        detected = ft.guess(contents)
        real_mime = detected.mime if detected else None
    except Exception:
        real_mime = None

    # Берём реальный MIME если определился, иначе доверяем заголовку (для text/*)
    mime_type = real_mime or file.content_type or "application/octet-stream"

    if mime_type not in ALLOWED_MIME_TYPES:
        # Для текстовых файлов filetype не определяет — доверяем заголовку
        header_mime = file.content_type or ""
        if header_mime.startswith("text/") and header_mime in ALLOWED_MIME_TYPES:
            mime_type = header_mime
        else:
            raise HTTPException(
                status_code=415,
                detail=f"File type not supported: {mime_type}",
            )

    # 2. Проверяем размер файла
    if size > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File too large (max {settings.MAX_FILE_SIZE_MB}MB)")

    # 3. Лимит количества файлов на пользователя
    count_result = await db.execute(
        select(sqlfunc.count()).select_from(Document).where(Document.user_id == current_user.id)
    )
    if (count_result.scalar() or 0) >= MAX_FILES_PER_USER:
        raise HTTPException(status_code=400, detail=f"File limit reached ({MAX_FILES_PER_USER} files per user)")

    # 4. Лимит суммарного размера на пользователя
    size_result = await db.execute(
        select(sqlfunc.sum(Document.size_bytes)).where(Document.user_id == current_user.id)
    )
    total_used = size_result.scalar() or 0
    if total_used + size > MAX_TOTAL_SIZE_MB * 1024 * 1024:
        used_mb = round(total_used / 1024 / 1024, 1)
        raise HTTPException(
            status_code=400,
            detail=f"Storage limit reached ({used_mb}/{MAX_TOTAL_SIZE_MB} MB used)",
        )

    # Сохраняем на диск
    ext = os.path.splitext(file.filename or "")[1]
    unique_name = f"{uuid.uuid4()}{ext}"
    user_dir = os.path.join(settings.UPLOAD_DIR, str(current_user.id))
    os.makedirs(user_dir, exist_ok=True)
    file_path = os.path.join(user_dir, unique_name)

    async with aiofiles.open(file_path, "wb") as f:
        await f.write(contents)

    # Сохраняем в БД
    doc = Document(
        user_id=current_user.id,
        filename=file.filename or unique_name,
        path=file_path,
        mime_type=mime_type,
        size_bytes=size,
        indexed=False,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    # Индексируем документы в фоне (не блокируем ответ)
    if mime_type in DOCUMENT_MIME_TYPES:
        from app.config import get_settings
        background_tasks.add_task(
            _index_in_background,
            current_user.id,
            doc.id,
            file_path,
            mime_type,
            file.filename or unique_name,
            settings.DATABASE_URL,
        )

    return doc


@router.get("", response_model=list[FileOut])
async def list_files(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Document)
        .where(Document.user_id == current_user.id)
        .order_by(Document.created_at.desc())
    )
    return result.scalars().all()


@router.delete("/{file_id}", status_code=204)
async def delete_file(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Document).where(Document.id == file_id, Document.user_id == current_user.id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="File not found")

    # Удаляем из Chroma
    try:
        from app.services.rag import get_chroma
        collection = get_chroma().get_collection(f"user_{current_user.id}")
        collection.delete(where={"document_id": file_id})
    except Exception:
        pass

    # Удаляем с диска
    if os.path.exists(doc.path):
        os.remove(doc.path)

    await db.delete(doc)
    await db.commit()
