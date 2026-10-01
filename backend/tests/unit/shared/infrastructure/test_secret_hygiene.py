"""The API key must never appear in repr, logs or error output."""

import logging

import pytest
import structlog
from pydantic import SecretStr

from villasanj.shared.infrastructure.logging import REDACTED, SecretRedactor, configure_logging
from villasanj.shared.infrastructure.settings import Settings

SECRET = "aa-secret-value-0123456789abcdef"


def test_settings_never_render_the_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AVALAI_API_KEY", SECRET)
    settings = Settings(_env_file=None)
    assert settings.avalai_api_key == SecretStr(SECRET)
    for rendering in (repr(settings), str(settings), settings.model_dump_json()):
        assert SECRET not in rendering
    assert settings.secret_values() == [SECRET]


def test_logs_from_structlog_and_stdlib_are_redacted(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO", "json", [SECRET])
    structlog.get_logger("test").info(
        "calling gateway", detail=f"key={SECRET}", nested={"x": SECRET}
    )
    structlog.get_logger("test").info("headers", authorization="Bearer whatever")
    logging.getLogger("httpx").info("library message with %s inside", SECRET)
    output = capsys.readouterr().err
    assert SECRET not in output
    assert output.count(REDACTED) >= 4


def test_redactor_ignores_short_values() -> None:
    redactor = SecretRedactor(["abc"])
    assert redactor.scrub_text("abc def") == "abc def"
