# Backend image (API, migrations, CLI jobs). Build context: repository root.
FROM ghcr.io/astral-sh/uv:0.11 AS uv

FROM python:3.12-slim-bookworm
COPY --from=uv /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1

WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock backend/.python-version ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project

COPY backend/src ./src
COPY backend/alembic.ini ./
COPY backend/migrations ./migrations
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-editable

COPY config /app/config

RUN useradd --create-home --uid 10001 app && mkdir -p /data/blobs && chown app /data/blobs
USER app

ENV CONFIG_DIR=/app/config \
    BLOB__ROOT=/data/blobs

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=12 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=2)"]
CMD ["uvicorn", "villasanj.entrypoints.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
