"""
Генерация изображений.

POST /api/images/generate — принимает промпт, возвращает URL изображения.
Модель по умолчанию: MODEL_IMAGE_GEN из настроек (gemini-3.1-flash-image-preview).
Можно переопределить через поле model в теле запроса.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.core.auth import get_current_user
from app.models.user import User
from app.config import get_settings
from app.core.router import RouteResult, TaskType, Provider, _openrouter

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/images", tags=["images"])


class GenerateImageRequest(BaseModel):
    prompt: str
    model: str | None = None          # переопределить модель (любая из routerai.ru)
    size: str = "1024x1024"           # "512x512" | "1024x1024" | "1792x1024"


class GenerateImageResponse(BaseModel):
    url: str                          # URL или data:image/png;base64,...
    model: str
    prompt: str


@router.post("/generate", response_model=GenerateImageResponse)
async def generate_image(
    body: GenerateImageRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Генерирует изображение по текстовому промпту.

    Примеры промптов:
    - "логотип технологического стартапа, минимализм, синий градиент"
    - "офисное пространство будущего, фотореализм, 4K"

    Модель по умолчанию задаётся в .env (MODEL_IMAGE_GEN).
    Можно явно передать model — любую из 353 моделей на routerai.ru.
    """
    if not body.prompt.strip():
        raise HTTPException(status_code=422, detail="Prompt cannot be empty")

    model = body.model or settings.MODEL_IMAGE_GEN
    route = _openrouter(model, TaskType.IMAGE_GEN, "direct image generation request")

    from app.services.llm import llm_client

    try:
        url = await llm_client.generate_image(route, body.prompt)
    except Exception as e:
        logger.error(
            "Image generation failed",
            extra={"model": model, "error": str(e)},
        )
        raise HTTPException(
            status_code=502,
            detail=f"Image generation failed: {str(e)[:200]}",
        )

    logger.info(
        "Image generated",
        extra={"user_id": current_user.id, "model": model},
    )
    return GenerateImageResponse(url=url, model=model, prompt=body.prompt)
