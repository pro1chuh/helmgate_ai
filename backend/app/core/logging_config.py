"""
Structured JSON logging — каждая строка лога является валидным JSON-объектом.
Grafana Loki / любой log-агрегатор подхватывает без парсинга.

Использование:
    from app.core.logging_config import setup_logging
    setup_logging(debug=settings.DEBUG)
"""
import json
import logging
import sys
from datetime import datetime, timezone

# Поля stdlib LogRecord которые не нужны в итоговом JSON
_SKIP_FIELDS = frozenset({
    "args", "asctime", "created", "exc_info", "exc_text", "filename",
    "funcName", "id", "levelname", "levelno", "lineno", "module",
    "msecs", "message", "msg", "name", "pathname", "process",
    "processName", "relativeCreated", "stack_info", "thread", "threadName",
})


class JSONFormatter(logging.Formatter):
    """Форматирует лог-запись как однострочный JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj: dict = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }

        # Местоположение (только для WARNING+)
        if record.levelno >= logging.WARNING:
            log_obj["loc"] = f"{record.pathname}:{record.lineno}"

        # Traceback
        if record.exc_info:
            log_obj["exc"] = self.formatException(record.exc_info)

        # Любые extra-поля, добавленные через logger.info(..., extra={...})
        for key, value in record.__dict__.items():
            if key not in _SKIP_FIELDS and not key.startswith("_"):
                try:
                    json.dumps(value)  # проверяем сериализуемость
                    log_obj[key] = value
                except (TypeError, ValueError):
                    log_obj[key] = str(value)

        return json.dumps(log_obj, ensure_ascii=False)


def setup_logging(debug: bool = False) -> None:
    """
    Настраивает корневой логгер на JSON-вывод в stdout.
    Вызывать один раз при старте приложения (до первого import logging).
    """
    level = logging.DEBUG if debug else logging.INFO

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    root.addHandler(handler)

    # Приглушаем шумные библиотеки
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if debug else logging.WARNING
    )
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    logging.getLogger("onnxruntime").setLevel(logging.WARNING)
