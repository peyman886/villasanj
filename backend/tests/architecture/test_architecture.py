"""Architecture rules over the real code base, each with a deliberately failing fixture."""

from pathlib import Path

import pytest

from tests.architecture.rules import (
    Module,
    domain_purity_violations,
    foreign_infrastructure_violations,
    invisible_character_violations,
    iter_modules,
    platform_slug_violations,
)

BACKEND = Path(__file__).resolve().parents[2]
SRC = BACKEND / "src"
MODULES = list(iter_modules(SRC))


def test_the_scan_sees_the_code_base() -> None:
    names = {module.name for module in MODULES}
    assert "villasanj.shared.domain.money" in names
    assert any(module.layer == "domain" for module in MODULES)


def test_domain_layers_import_only_stdlib_and_kernel() -> None:
    assert [v for m in MODULES for v in domain_purity_violations(m)] == []


def test_contexts_do_not_import_foreign_infrastructure() -> None:
    assert [v for m in MODULES for v in foreign_infrastructure_violations(m)] == []


def test_core_never_names_a_platform() -> None:
    assert [v for m in MODULES for v in platform_slug_violations(m)] == []


@pytest.mark.parametrize("root", [SRC, BACKEND / "tests"])
def test_no_invisible_characters_in_python_sources(root: Path) -> None:
    violations = [
        violation
        for path in root.rglob("*.py")
        for violation in invisible_character_violations(str(path), path.read_text("utf-8"))
    ]
    assert violations == []


# ---------------------------------------------------------------- the rules catch violations

BAD_DOMAIN = Module(
    "villasanj.pricing.domain.bad",
    "import pydantic\nfrom sqlalchemy import select\nfrom villasanj.pricing.application import x\n"
    "import datetime\nfrom villasanj.shared.domain.money import Money\n",
)


def test_fixture_domain_purity_rule_fires() -> None:
    violations = domain_purity_violations(BAD_DOMAIN)
    assert len(violations) == 3
    assert any("pydantic" in v for v in violations)
    assert any("villasanj.pricing.application" in v for v in violations)


def test_fixture_foreign_infrastructure_rule_fires() -> None:
    module = Module(
        "villasanj.pricing.application.quotes",
        "from villasanj.catalog.infrastructure.repos import PgListingRepo\n"
        "from villasanj.pricing.infrastructure.repos import PgQuoteRepo\n",
    )
    assert len(foreign_infrastructure_violations(module)) == 1


def test_fixture_platform_slug_rule_fires() -> None:
    core = Module(
        "villasanj.pricing.domain.fees",
        '"""Docstrings may mention jabama."""\n'
        "def fee(platform: str) -> int:\n"
        "    if platform == 'Jabama':\n"
        "        return 1\n"
        "    return jajiga_fee\n",
    )
    adapter = Module("villasanj.ingestion.infrastructure.sources.jabama.adapter", "X = 'jabama'\n")
    assert len(platform_slug_violations(core)) == 2
    assert platform_slug_violations(adapter) == []


def test_fixture_invisible_character_rule_fires() -> None:
    source = 'ZWNJ = "\N{ZERO WIDTH NON-JOINER}"\n'
    assert len(invisible_character_violations("fixture.py", source)) == 1
