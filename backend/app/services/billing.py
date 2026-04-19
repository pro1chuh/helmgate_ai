"""
Биллинг — расчёт стоимости LLM-запросов и списание с баланса организации.

Цены за 1M токенов (в рублях) — актуальные тарифы routerai.ru:
  gemma-3-4b-it:           вход 3₽,   выход 7₽
  llama-3.3-70b-instruct:  вход 11₽,  выход 37₽
  kat-coder-pro-v2:        вход 29₽,  выход 118₽
  gemini-2.5-pro:          вход 123₽, выход 988₽
  grok-4.20:               вход 197₽, выход 593₽
  gemini-2.5-flash-image:  вход 29₽,  выход 247₽
"""
import logging
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger(__name__)

# Цены за 1 токен в рублях (= цена за 1M / 1_000_000)
_PRICING: dict[str, tuple[Decimal, Decimal]] = {
    # model_id: (input_per_token, output_per_token)
    "google/gemma-3-4b-it":                    (Decimal("3") / 1_000_000,   Decimal("7") / 1_000_000),
    "meta-llama/llama-3.3-70b-instruct":       (Decimal("11") / 1_000_000,  Decimal("37") / 1_000_000),
    "kwaipilot/kat-coder-pro-v2":              (Decimal("29") / 1_000_000,  Decimal("118") / 1_000_000),
    "google/gemini-2.5-pro":                   (Decimal("123") / 1_000_000, Decimal("988") / 1_000_000),
    "x-ai/grok-4.20":                          (Decimal("197") / 1_000_000, Decimal("593") / 1_000_000),
    "google/gemini-2.5-flash-image":           (Decimal("29") / 1_000_000,  Decimal("247") / 1_000_000),
}

# Дефолтная цена для неизвестных моделей — берём среднюю (llama)
_DEFAULT_PRICING = (Decimal("11") / 1_000_000, Decimal("37") / 1_000_000)

# Gemma overhead на каждый запрос:
# классификатор: ~300 вход + ~20 выход
# память:        ~600 вход + ~50 выход
_GEMMA_INPUT  = Decimal("920")   # токенов
_GEMMA_OUTPUT = Decimal("70")    # токенов
_GEMMA_IN_PRICE, _GEMMA_OUT_PRICE = _PRICING["google/gemma-3-4b-it"]
GEMMA_OVERHEAD_PER_REQUEST = (_GEMMA_INPUT * _GEMMA_IN_PRICE + _GEMMA_OUTPUT * _GEMMA_OUT_PRICE)


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    """Считает стоимость одного запроса в рублях."""
    in_price, out_price = _PRICING.get(model, _DEFAULT_PRICING)
    main_cost = Decimal(input_tokens) * in_price + Decimal(output_tokens) * out_price
    return (main_cost + GEMMA_OVERHEAD_PER_REQUEST).quantize(Decimal("0.000001"))


async def log_and_deduct(
    organization_id: int,
    user_id: int,
    model: str,
    task_type: str,
    input_tokens: int,
    output_tokens: int,
    db: AsyncSession,
) -> Decimal:
    """
    1. Считает стоимость запроса
    2. Записывает в usage_logs
    3. Списывает с баланса организации
    Возвращает списанную сумму.
    """
    from app.models.organization import Organization, UsageLog

    cost = calculate_cost(model, input_tokens, output_tokens)

    # Записываем лог
    log = UsageLog(
        organization_id=organization_id,
        user_id=user_id,
        model=model,
        task_type=task_type,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_rub=cost,
    )
    db.add(log)

    # Списываем с баланса (не уходим в минус — минимум 0)
    result = await db.execute(select(Organization).where(Organization.id == organization_id))
    org = result.scalar_one_or_none()
    if org:
        org.balance = max(Decimal("0"), org.balance - cost)
        # Приостанавливаем если баланс кончился
        if org.balance == Decimal("0"):
            from app.models.organization import OrgStatus
            org.status = OrgStatus.suspended
            logger.warning(f"Organization {org.company_name} balance exhausted — suspended")

    await db.commit()
    return cost


async def check_balance(organization_id: int | None, db: AsyncSession) -> bool:
    """
    Проверяет что у организации есть активный статус и ненулевой баланс.
    Superadmin-пользователи (organization_id=None) всегда проходят.
    """
    if organization_id is None:
        return True

    from app.models.organization import Organization, OrgStatus
    result = await db.execute(select(Organization).where(Organization.id == organization_id))
    org = result.scalar_one_or_none()
    if not org:
        return False
    return org.status == OrgStatus.active and org.balance > Decimal("0")
