"""AST-based architecture rules that import-linter cannot express precisely."""

from __future__ import annotations

import ast
import re
import sys
import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

ROOT_PACKAGE = "villasanj"
CONTEXTS = (
    "shared",
    "ingestion",
    "catalog",
    "entity_resolution",
    "pricing",
    "enrichment",
    "discovery",
)
# Known Iranian rental platforms. Only source adapters, config and tests may name them.
PLATFORM_SLUGS = ("jajiga", "jabama", "otaghak", "shab", "homsa", "mihmansho", "mizboon")
SOURCES_PACKAGE = f"{ROOT_PACKAGE}.ingestion.infrastructure.sources"
_SLUG_PATTERN = re.compile(rf"\b({'|'.join(PLATFORM_SLUGS)})\b", re.IGNORECASE)
_FORMAT_CATEGORY = "Cf"
_LAYER_INDEX = 2  # villasanj.<context>.<layer>


@dataclass(frozen=True)
class Module:
    name: str
    source: str
    path: str = "<memory>"

    @property
    def tree(self) -> ast.Module:
        return ast.parse(self.source)

    @property
    def context(self) -> str | None:
        parts = self.name.split(".")
        return parts[1] if len(parts) > 1 and parts[1] in CONTEXTS else None

    @property
    def layer(self) -> str | None:
        parts = self.name.split(".")
        return parts[_LAYER_INDEX] if len(parts) > _LAYER_INDEX and self.context else None


def iter_modules(src_root: Path) -> Iterator[Module]:
    for path in sorted(src_root.rglob("*.py")):
        relative = path.relative_to(src_root).with_suffix("")
        parts = [p for p in relative.parts if p != "__init__"]
        yield Module(".".join(parts), path.read_text(encoding="utf-8"), str(path))


def _imports(module: Module) -> Iterator[tuple[int, str]]:
    for node in ast.walk(module.tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.lineno, node.module


_DOMAIN_MODULE = re.compile(rf"^{ROOT_PACKAGE}\.\w+\.domain(\.|$)")


def domain_purity_violations(module: Module) -> list[str]:
    """Domain code may import only the stdlib and domain layers.

    Which contexts' domains are reachable is governed by the import-linter context DAG.
    """
    if module.layer != "domain":
        return []
    violations = []
    for line, imported in _imports(module):
        top = imported.split(".")[0]
        if top == "__future__" or top in sys.stdlib_module_names:
            continue
        if _DOMAIN_MODULE.match(imported):
            continue
        violations.append(f"{module.path}:{line} domain imports {imported}")
    return violations


def foreign_infrastructure_violations(module: Module) -> list[str]:
    """A context may not import another context's infrastructure (only entrypoints may)."""
    if module.context is None:
        return []
    violations = []
    for line, imported in _imports(module):
        parts = imported.split(".")
        is_infrastructure = len(parts) > _LAYER_INDEX and parts[_LAYER_INDEX] == "infrastructure"
        if is_infrastructure and parts[0] == ROOT_PACKAGE and parts[1] != module.context:
            violations.append(f"{module.path}:{line} imports {imported}")
    return violations


def _docstring_nodes(tree: ast.Module) -> set[int]:
    owners = [
        tree,
        *(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
        ),
    ]
    ids = set()
    for owner in owners:
        body = owner.body
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
            ids.add(id(body[0].value))
    return ids


def platform_slug_violations(module: Module) -> list[str]:
    """Platform specifics reach the core as data, never as names in code (OCP)."""
    if module.name.startswith(SOURCES_PACKAGE):
        return []
    tree = module.tree
    docstrings = _docstring_nodes(tree)
    violations = []
    for node in ast.walk(tree):
        text: str | None = None
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docstrings
        ):
            text = node.value
        elif isinstance(node, ast.Name):
            text = node.id.replace("_", " ")
        elif isinstance(node, ast.Attribute):
            text = node.attr.replace("_", " ")
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            text = node.name.replace("_", " ")
        if text and _SLUG_PATTERN.search(text):
            violations.append(f"{module.path}:{getattr(node, 'lineno', '?')} names a platform")
    return violations


def invisible_character_violations(path: str, source: str) -> list[str]:
    """Zero-width and other format characters must be written as escapes (e.g. \\N{...})."""
    violations = []
    for line_number, line in enumerate(source.splitlines(), start=1):
        for char in line:
            if unicodedata.category(char) == _FORMAT_CATEGORY:
                name = unicodedata.name(char, f"U+{ord(char):04X}")
                violations.append(f"{path}:{line_number} contains {name}")
    return violations
