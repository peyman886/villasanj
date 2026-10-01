"""Structured JSON logging with secret redaction for both structlog and stdlib loggers."""

from __future__ import annotations

import logging
import re
import sys
from collections.abc import Iterable, MutableMapping
from typing import Any

import structlog
from structlog.typing import EventDict, Processor, WrappedLogger

REDACTED = "***"
_SENSITIVE_KEY = re.compile(r"authorization|api[_-]?key|secret|token|password", re.IGNORECASE)
_MIN_SECRET_LENGTH = 8  # shorter values would cause false redactions everywhere


class SecretRedactor:
    """Masks known secret values anywhere in an event and values of sensitive-looking keys."""

    def __init__(self, secrets: Iterable[str]) -> None:
        self._secrets = [s for s in secrets if len(s) >= _MIN_SECRET_LENGTH]

    def __call__(self, _: WrappedLogger, __: str, event_dict: EventDict) -> EventDict:
        return self._scrub_mapping(event_dict)

    def scrub_text(self, text: str) -> str:
        for secret in self._secrets:
            text = text.replace(secret, REDACTED)
        return text

    def _scrub_mapping(self, mapping: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
        for key, value in mapping.items():
            mapping[key] = REDACTED if _SENSITIVE_KEY.search(str(key)) else self._scrub(value)
        return mapping

    def _scrub(self, value: Any) -> Any:
        if isinstance(value, str):
            return self.scrub_text(value)
        if isinstance(value, dict):
            return self._scrub_mapping(dict(value))
        if isinstance(value, list | tuple):
            return type(value)(self._scrub(item) for item in value)
        return value


def configure_logging(level: str, fmt: str, secrets: Iterable[str]) -> None:
    redactor = SecretRedactor(secrets)
    shared: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.format_exc_info,
        redactor,
    ]
    renderer: Processor = (
        structlog.processors.JSONRenderer(ensure_ascii=False)
        if fmt == "json"
        else structlog.dev.ConsoleRenderer()
    )
    structlog.configure(
        processors=[*shared, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,
    )
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared,
            processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, renderer],
        )
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
