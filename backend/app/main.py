from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.database import init_db
from app.api import auth, chats, files, memory, profile, admin
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
    allow_origins=["http://localhost:3000", "http://localhost:80"],
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


@app.get("/api/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME}
