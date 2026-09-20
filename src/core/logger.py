"""Ustrukturyzowane logowanie JSON przy użyciu biblioteki structlog.

Zapewnia spójny format logów we wszystkich modułach backendu, ETL (Airflow)
oraz silnika analitycznego AI/LLM, wspierając Cloud Logging (GCP / Datadog).
"""

import logging
import os
import sys
from typing import Any, cast

import structlog
from structlog.types import EventDict, Processor


def add_app_context(_logger: Any, _method_name: str, event_dict: EventDict) -> EventDict:
    """Dodaje globalne metadane aplikacji do każdego wpisu w logu."""
    event_dict.setdefault("service", "weryfikator-obietnic-api")
    event_dict.setdefault("environment", os.getenv("ENVIRONMENT", "development"))
    return event_dict


def configure_logging(log_level: str | None = None) -> None:
    """Konfiguruje globalny potok procesorów structlog oraz standardowy moduł logging."""
    raw_level = log_level or os.getenv("LOG_LEVEL") or "INFO"
    level_name = raw_level.upper()
    level = getattr(logging, level_name, logging.INFO)

    # Standardowe procesory formatujące kontekst i metadane
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        add_app_context,
    ]

    # Wybór renderera w zależności od formatu LOG_FORMAT
    json_logging = os.getenv("LOG_FORMAT", "json").lower() == "json"
    renderer: Processor = (
        structlog.processors.JSONRenderer()
        if json_logging
        else structlog.dev.ConsoleRenderer(colors=True)
    )

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Konfiguracja handlerów standardowego modułu logging
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)

    # Wyciszenie zbyt gadatliwych loggerów zewnętrznych
    for noisy_logger in ("uvicorn.access", "sqlalchemy.engine", "httpcore", "httpx"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Zwraca powiązaną instancję loggera structlog dla danego modułu."""
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))


# Domyślna inicjalizacja przy imporcie modułu
configure_logging()
logger = get_logger("weryfikator-obietnic")
