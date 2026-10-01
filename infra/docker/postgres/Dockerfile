# PostgreSQL 17 + PostGIS 3 + pgvector, multi-arch (official postgres images ship the PGDG apt repo,
# which builds both extensions for amd64 and arm64).
FROM postgres:17-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-17-postgis-3 \
        postgresql-17-pgvector \
    && rm -rf /var/lib/apt/lists/*
