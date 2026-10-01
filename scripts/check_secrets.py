#!/usr/bin/env python3
"""Pre-commit guard: fail if any file contains a secret value from the local .env.

Exact-match scanning complements gitleaks' pattern rules: it catches our real key even if its
format matches no known pattern. Values are never printed. Standard library only.
"""

import re
import sys
from pathlib import Path

SENSITIVE_KEY = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD)", re.IGNORECASE)
MIN_SECRET_LENGTH = 8
ENV_LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$")


def load_secrets(env_path):
    if not env_path.is_file():
        return {}
    secrets = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        match = ENV_LINE.match(line)
        if not match or line.lstrip().startswith("#"):
            continue
        name, value = match.group(1), match.group(2).strip("'\"")
        if SENSITIVE_KEY.search(name) and len(value) >= MIN_SECRET_LENGTH:
            secrets[name] = value
    return secrets


def main(paths):
    secrets = load_secrets(Path(__file__).resolve().parent.parent / ".env")
    leaks = []
    for raw in paths:
        path = Path(raw)
        if not path.is_file() or path.name == ".env":
            continue
        content = path.read_bytes().decode("utf-8", errors="ignore")
        leaks.extend(f"{raw}: contains the value of {name}" for name, value in secrets.items() if value in content)
    for leak in leaks:
        print(leak, file=sys.stderr)
    return 1 if leaks else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
