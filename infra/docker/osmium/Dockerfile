# osmium-tool for clipping the Geofabrik Iran extract (ADR-0003 decision 5, ADR-0013).
# Debian's package is multi-arch (amd64 and arm64), so nothing is installed on the host.
FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends osmium-tool=1.15.0-1 \
    && rm -rf /var/lib/apt/lists/*

ENTRYPOINT ["osmium"]
