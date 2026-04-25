"""
RAG-пайплайн для Helm.

Поток:
  1. Загрузка файла → извлечение текста → нарезка на куски
  2. Векторизация через локальную ONNX-модель (без API)
  3. Хранение в ChromaDB (коллекция per user)
  4. При запросе: векторный поиск → топ-5 кусков → в prompt LLM
"""
import os
import re
import asyncio
import logging
from pathlib import Path
import chromadb
from chromadb.config import Settings as ChromaSettings
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2EmbeddingFunction
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Размер куска текста и перекрытие (в символах)
CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
# Сколько кусков отдавать в контекст LLM
TOP_K = 5


# -------------------------------------------------------
# ChromaDB клиент (синглтон)
# -------------------------------------------------------

_chroma: chromadb.ClientAPI | None = None


def get_chroma() -> chromadb.ClientAPI:
    global _chroma
    if _chroma is None:
        _chroma = chromadb.PersistentClient(
            path=settings.CHROMA_PATH,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
    return _chroma


_embedding_fn = ONNXMiniLM_L6_V2EmbeddingFunction()


def _user_collection(user_id: int) -> chromadb.Collection:
    """Отдельная Chroma-коллекция для каждого пользователя."""
    return get_chroma().get_or_create_collection(
        name=f"user_{user_id}",
        metadata={"hnsw:space": "cosine"},
        embedding_function=_embedding_fn,
    )


# -------------------------------------------------------
# Извлечение текста из файла
# -------------------------------------------------------

def _extract_text(path: str, mime_type: str) -> str:
    """Извлекает текст из PDF, DOCX или текстового файла."""

    if mime_type == "application/pdf":
        from pypdf import PdfReader
        reader = PdfReader(path)
        return "\n\n".join(
            page.extract_text() or "" for page in reader.pages
        )

    if mime_type in (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    ):
        from docx import Document
        doc = Document(path)
        return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())

    # TXT, CSV, MD — читаем напрямую
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


# -------------------------------------------------------
# Нарезка текста на куски
# -------------------------------------------------------

def _chunk_text(text: str) -> list[str]:
    """
    Нарезает текст на куски с перекрытием.
    Старается не разрывать на середине предложения.
    """
    # Нормализуем пробелы
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        return []

    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE

        # Ищем конец предложения чтобы не рвать посередине
        if end < len(text):
            for sep in (". ", ".\n", "\n\n", "\n", " "):
                pos = text.rfind(sep, start, end)
                if pos != -1:
                    end = pos + len(sep)
                    break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - CHUNK_OVERLAP

    return chunks


# -------------------------------------------------------
# Индексация документа
# -------------------------------------------------------

async def index_document(
    user_id: int,
    document_id: int,
    file_path: str,
    mime_type: str,
    filename: str,
) -> int:
    """
    Извлекает текст, нарезает, векторизует и сохраняет в Chroma.
    Возвращает количество проиндексированных кусков.
    """
    # Извлекаем текст в thread pool (синхронные библиотеки)
    loop = asyncio.get_event_loop()
    text = await loop.run_in_executor(None, _extract_text, file_path, mime_type)

    if not text.strip():
        logger.warning(f"Document {document_id} has no extractable text")
        return 0

    chunks = _chunk_text(text)
    if not chunks:
        return 0

    # Сохраняем в Chroma — эмбеддинги считаются локально через ONNX
    collection = _user_collection(user_id)

    ids = [f"doc_{document_id}_chunk_{i}" for i in range(len(chunks))]
    metadatas = [
        {"document_id": document_id, "filename": filename, "chunk_index": i}
        for i in range(len(chunks))
    ]

    # Удаляем старые куски этого документа если документ переиндексируется
    try:
        collection.delete(where={"document_id": document_id})
    except Exception:
        pass

    collection.add(
        ids=ids,
        documents=chunks,
        metadatas=metadatas,
    )

    logger.info(f"Indexed document {document_id}: {len(chunks)} chunks")
    return len(chunks)


# -------------------------------------------------------
# Поиск по базе знаний
# -------------------------------------------------------

async def retrieve(
    user_id: int,
    query: str,
    document_id: int | None = None,
    top_k: int = TOP_K,
) -> list[str]:
    """
    Ищет релевантные куски текста по запросу пользователя.

    Args:
        user_id:     ID пользователя (ищем в его коллекции)
        query:       Вопрос пользователя
        document_id: Искать только в конкретном документе (опционально)
        top_k:       Количество кусков для возврата

    Returns:
        Список текстовых кусков, отсортированных по релевантности
    """
    try:
        collection = _user_collection(user_id)

        # Фильтр по конкретному документу если указан
        where = {"document_id": document_id} if document_id else None

        # Эмбеддинг запроса считается локально через ONNX
        results = collection.query(
            query_texts=[query],
            n_results=min(top_k, collection.count()),
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        chunks = results["documents"][0] if results["documents"] else []
        return chunks

    except Exception as e:
        logger.error(f"RAG retrieval failed: {e}")
        return []


async def retrieve_with_sources(
    user_id: int,
    query: str,
    document_id: int | None = None,
    top_k: int = TOP_K,
) -> list[dict]:
    """Returns relevant chunks with metadata for UI citations."""
    try:
        collection = _user_collection(user_id)
        count = collection.count()
        if count <= 0:
            return []

        where = {"document_id": document_id} if document_id else None
        results = collection.query(
            query_texts=[query],
            n_results=min(top_k, count),
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        documents = results.get("documents", [[]])[0] if results.get("documents") else []
        metadatas = results.get("metadatas", [[]])[0] if results.get("metadatas") else []
        distances = results.get("distances", [[]])[0] if results.get("distances") else []

        sources = []
        for index, chunk in enumerate(documents):
            metadata = metadatas[index] if index < len(metadatas) and metadatas[index] else {}
            distance = distances[index] if index < len(distances) else None
            snippet = re.sub(r"\s+", " ", chunk or "").strip()
            sources.append({
                "source_id": index + 1,
                "document_id": metadata.get("document_id"),
                "filename": metadata.get("filename") or "Document",
                "chunk_index": metadata.get("chunk_index"),
                "snippet": snippet[:360],
                "score": None if distance is None else max(0, min(1, 1 - float(distance))),
                "text": chunk or "",
            })
        return sources

    except Exception as e:
        logger.error(f"RAG retrieval with sources failed: {e}")
        return []


# -------------------------------------------------------
# Формирование контекста для LLM
# -------------------------------------------------------

def build_rag_context(chunks: list[str], query: str) -> str:
    """
    Собирает system-prompt с найденными кусками документа.
    """
    if not chunks:
        return ""

    context_text = "\n\n---\n\n".join(chunks)
    return (
        f"Используй следующие фрагменты документов для ответа на вопрос.\n"
        f"Если ответ не содержится в документах — так и скажи.\n\n"
        f"=== ФРАГМЕНТЫ ДОКУМЕНТОВ ===\n{context_text}\n"
        f"=== КОНЕЦ ФРАГМЕНТОВ ===\n\n"
        f"Вопрос пользователя: {query}"
    )


def build_rag_context_from_sources(sources: list[dict], query: str) -> str:
    if not sources:
        return ""

    chunks = []
    for source in sources:
        chunks.append(
            f"[source {source.get('source_id')}] "
            f"{source.get('filename')} / chunk {source.get('chunk_index')}\n"
            f"{source.get('text') or source.get('snippet') or ''}"
        )

    context_text = "\n\n---\n\n".join(chunks)
    return (
        "Use the following document fragments to answer the user's question. "
        "When the answer relies on them, mention the relevant source numbers naturally.\n"
        "If the answer is not contained in the documents, say that clearly.\n\n"
        f"=== DOCUMENT FRAGMENTS ===\n{context_text}\n"
        f"=== END DOCUMENT FRAGMENTS ===\n\n"
        f"User question: {query}"
    )
