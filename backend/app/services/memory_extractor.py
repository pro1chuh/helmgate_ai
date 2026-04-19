"""
Авто-извлечение фактов о пользователе из диалога.

После каждого ответа ассистента запускается в фоне:
  - отправляет последний обмен в gemma-3-4b-it (через OpenRouter)
  - парсит факты (имя, должность, компания, предпочтения…)
  - сохраняет / обновляет UserFact в БД
"""
import json
import logging
import httpx
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

EXTRACT_PROMPT = """\
Проанализируй диалог и извлеки факты о пользователе.
Верни ТОЛЬКО валидный JSON без пояснений:
{{"facts": [{{"key": "...", "value": "..."}}]}}

Если фактов нет — верни {{"facts": []}}.

Допустимые ключи: name, role, company, department, language, preferences, timezone, other_<anything>.

Пользователь: {user_message}
Ассистент: {assistant_message}"""


async def extract_and_save(
    user_id: int,
    user_message: str,
    assistant_message: str,
    db_url: str,
) -> None:
    """Фоновая задача — извлекает и сохраняет факты о пользователе."""
    payload = {
        "model": settings.MODEL_MEMORY,
        "messages": [
            {
                "role": "user",
                "content": EXTRACT_PROMPT.format(
                    user_message=user_message[:600],
                    assistant_message=assistant_message[:600],
                ),
            }
        ],
        "temperature": 0.0,
        "max_tokens": 200,
        "stream": False,
    }

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(
                f"{settings.OPENROUTER_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {settings.OPENROUTER_API_KEY}"},
                json=payload,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"].strip()
            content = content.replace("```json", "").replace("```", "").strip()
            data = json.loads(content)
            facts = data.get("facts", [])

        if not facts:
            return

        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        from sqlalchemy import select
        from app.models.user import UserFact

        engine = create_async_engine(db_url)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        async with session_factory() as session:
            for item in facts:
                key = str(item.get("key", "")).strip()[:100]
                value = str(item.get("value", "")).strip()[:1000]
                if not key or not value:
                    continue

                result = await session.execute(
                    select(UserFact).where(
                        UserFact.user_id == user_id,
                        UserFact.key == key,
                    )
                )
                fact = result.scalar_one_or_none()
                if fact:
                    fact.value = value
                else:
                    session.add(UserFact(user_id=user_id, key=key, value=value))

            await session.commit()

        await engine.dispose()
        logger.info(f"Extracted {len(facts)} facts for user {user_id}")

    except Exception as e:
        logger.debug(f"Memory extraction skipped: {type(e).__name__}: {e}")
