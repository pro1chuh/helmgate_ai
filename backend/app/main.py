from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.database import init_db
from app.api import auth, chats, files, memory, profile, admin, workspaces
from app.config import get_settings
import os

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Создаём таблицы при старте
    await init_db()
    # Создаём папку для загрузок
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    yield
    # Graceful shutdown — закрываем пул соединений
    from app.services.llm import llm_client
    await llm_client.aclose()


app = FastAPI(
    title="Helm API",
    version="0.1.0",
    description="Корпоративный AI-ассистент с автороутингом моделей",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:80", "http://localhost:8080", "null"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(chats.router, prefix="/api")
app.include_router(files.router, prefix="/api")
app.include_router(memory.router, prefix="/api")
app.include_router(profile.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(workspaces.router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME}


@app.get("/api/health/detailed")
async def health_detailed():
    """
    Расширенный healthcheck — проверяет доступность LLM-провайдера.
    Используется для мониторинга и дашборда администратора.
    """
    import asyncio
    from app.services.llm import llm_client

    provider_status = "ok"
    provider_latency_ms = None
    provider_error = None

    try:
        import time
        start = time.monotonic()
        response = await asyncio.wait_for(
            llm_client._client.get(
                f"{settings.OPENROUTER_BASE_URL}/models",
                timeout=5.0,
            ),
            timeout=6.0,
        )
        provider_latency_ms = round((time.monotonic() - start) * 1000)
        if response.status_code >= 400:
            provider_status = "degraded"
            provider_error = f"HTTP {response.status_code}"
    except Exception as e:
        provider_status = "unavailable"
        provider_error = str(e)

    overall = "ok" if provider_status == "ok" else "degraded"

    return {
        "status": overall,
        "app": settings.APP_NAME,
        "provider": {
            "name": "routerai",
            "url": settings.OPENROUTER_BASE_URL,
            "status": provider_status,
            "latency_ms": provider_latency_ms,
            "error": provider_error,
        },
    }
