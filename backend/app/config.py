from pydantic_settings import BaseSettings
from pydantic import field_validator
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Helm"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://helm:helm@db:5432/helm"

    # JWT
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # -------------------------------------------------------
    # Провайдеры (только cloud — через router.ai / OpenRouter)
    # -------------------------------------------------------

    # Groq — ASR (Whisper); OpenRouter не поддерживает audio endpoints
    GROQ_API_KEY: str = ""
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"

    # OpenRouter (routerai.ru) — все LLM, Vision, Image Gen
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

    # -------------------------------------------------------
    # Модели (все через OpenRouter, кроме ASR)
    # -------------------------------------------------------

    # Текст — общение, документы, RAG
    MODEL_TEXT: str = "meta-llama/llama-3.3-70b-instruct"

    # Код
    MODEL_CODE: str = "kwaipilot/kat-coder-pro-v2"

    # Reasoning — глубокий анализ
    MODEL_REASONING: str = "google/gemini-2.5-pro"

    # Vision — анализ изображений
    MODEL_VISION: str = "x-ai/grok-4.20"

    # Image generation
    MODEL_IMAGE_GEN: str = "google/gemini-3.1-flash-image-preview"

    # ASR — через Groq
    MODEL_ASR: str = "whisper-large-v3-turbo"

    # Классификатор запросов (маленькая быстрая модель)
    MODEL_ROUTER: str = "google/gemma-3-4b-it"

    # Извлечение фактов о пользователе (фоновая)
    MODEL_MEMORY: str = "google/gemma-3-4b-it"

    # Files
    UPLOAD_DIR: str = "/app/uploads"
    MAX_FILE_SIZE_MB: int = 50

    # Chroma (RAG)
    CHROMA_PATH: str = "/app/chroma"

    # -------------------------------------------------------
    # Redis
    # -------------------------------------------------------
    REDIS_URL: str = "redis://redis:6379/0"

    # -------------------------------------------------------
    # Billing alerts
    # -------------------------------------------------------
    # Порог низкого баланса (рубли) — алерт отправляется один раз при пересечении
    LOW_BALANCE_THRESHOLD_RUB: float = 100.0
    # Telegram-бот для системных алертов (баланс, ошибки)
    # Оставь пустым чтобы отключить алерты
    TELEGRAM_ALERT_TOKEN: str = ""
    TELEGRAM_ALERT_CHAT_ID: str = ""

    # -------------------------------------------------------
    # Per-user daily token limit (0 = без ограничений)
    # Можно переопределить на уровне конкретного пользователя в БД
    # -------------------------------------------------------
    DEFAULT_DAILY_TOKEN_LIMIT: int = 0

    # -------------------------------------------------------
    # Circuit breaker — LLM failover
    # -------------------------------------------------------
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = 3   # сбоев подряд для открытия
    CIRCUIT_BREAKER_COOLDOWN_SECONDS: int = 60   # секунд до retry

    @field_validator("GROQ_API_KEY", "OPENROUTER_API_KEY", mode="before")
    @classmethod
    def empty_string_allowed(cls, v):
        return v or ""

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
