# ADR-0003 — Local infrastructure on a 16 GB Apple M4

Status: Accepted (M0 approval, 2026-10-01) · Date: 2026-10-01

## Context (measured 2026-10-01)

| Item | Value |
|---|---|
| Machine | Apple M4 (4 performance + 6 efficiency cores), 10-core GPU (Metal 4), **16 GB RAM** |
| OS | macOS 26.5.2, arm64 |
| Disk | 168 GB free of 460 GB |
| Docker | Docker Desktop 29.6.2, Compose v5.3.1, **7.75 GB RAM / 10 CPUs allocated** to the VM |
| Tooling | uv 0.11.32, Node 26.5, npm 11.17, GNU Make **3.81**, git 2.55; system Python 3.9.6 (uv manages 3.11 today) |
| Network | Docker Hub pulls work (images present); AvalAI edge served by ArvanCloud |

Facts that shape the design:

1. **Containers on macOS cannot use the Apple GPU.** Docker Desktop has no Metal passthrough, so
   anything in `docker compose` runs on CPU (linux/arm64).
2. **All images must be linux/arm64.** Official `postgis/postgis` images have historically been
   amd64-only; OSRM images may be too (to verify in M8).
3. **Memory is the scarce resource**, not CPU or disk.

## Decision

1. **Compose profiles**: `core` (db, api, web), `pipeline` (worker, browser), `routing` (osrm,
   osrm-prep one-shot). `make up` starts `core`; jobs start `pipeline` services on demand.
2. **Memory budget** (limits set in compose, so a runaway job cannot starve the DB):

   | Service | Limit | Note |
   |---|---|---|
   | db (Postgres 17 + PostGIS + pgvector) | 1.5 GB | `shared_buffers` 384 MB |
   | api | 0.5 GB | |
   | web (Next.js prod server) | 0.5 GB | UI development runs `npm run dev` on the host |
   | worker | 2.5 GB | torch CPU + DINOv2-S/B batch inference; Splink/DuckDB |
   | browser (Chromium) | 1.0 GB | only while a JS-rendered adapter is crawling |
   | osrm-routed | 0.7 GB | clipped north-Iran graph |
   | **Peak total** | **≈ 6.7 GB** | fits 7.75 GB; the core profile alone ≈ 2.5 GB |

3. **Custom Postgres image**: `FROM postgres:17-bookworm` + PGDG packages `postgresql-17-postgis-3` and
   `postgresql-17-pgvector`. Multi-arch by construction; versions pinned in the Dockerfile.
4. **Image inference runs on CPU in the `worker` container** by default (reproducible, part of
   `docker compose`). DINOv2 ViT-S/14 or ViT-B/14 on ~30k photos is a one-off batch job; throughput is
   measured in M5. **Optional accelerator:** the same job can run on the host with `uv run` and
   `device=mps`. It is the same code and the same port, with a different device setting. This is the
   documented exception to "everything in compose", used only if CPU time proves painful.
5. **OSRM on a clipped extract**: download Geofabrik's Iran extract once, `osmium extract` a bounding
   box that covers Tehran → Chalus/Haraz/Qazvin–Rasht corridors → Ramsar–Tonekabon, and build the
   graph with MLD. The clipped graph keeps preprocessing and serving memory small. Drive times are
   free-flow and labelled as such (no traffic data exists here).
6. **Map basemap**: prefer a local PMTiles extract for the region (offline, no tile-server policy
   issues). Fallback: OSM raster tiles with attribution at demo-level volume. Decided in M7.
7. **Makefile compatible with GNU Make 3.81** (macOS default): no `.ONESHELL`, no `file` function,
   no grouped targets.
8. **Text embeddings via AvalAI**, not a resident local model (see ADR-0006): a local bge-m3 would pin
   ~2 GB in the API process.

## Alternatives considered

- **Raise Docker's memory to 10–12 GB.** Possible, but it leaves macOS and the browser tight. It is not
  needed with the profile plan. The owner can raise it later without design changes.
- **Colima/OrbStack instead of Docker Desktop.** No GPU benefit either; switching tools for no gain.
- **Full Iran OSRM graph.** Larger preprocessing memory and time for routes we never ask for.

## Consequences

- (+) The core stack is light enough to leave running while developing.
- (+) No GPU dependency; results are reproducible on any machine with Docker.
- (−) CPU image embedding is slower; mitigated by batching, ≤ 800 px downloads and the optional MPS runner.
- (−) The custom Postgres image must be built once (`make setup`).

## Amendment (2026-10-02): basemap for the listing map (decision 6)

The listing page shows the published pin and its blur circle on a MapLibre map (static: no drag or
zoom, so it never takes the page's scroll or keyboard focus). For now the basemap is OSM's raster
tiles with attribution, the decision-6 fallback, at demo-level volume. The offline demo (M11
criterion 1) cannot use them, and bulk-downloading OSM tiles is against OSM's tile policy, so M11
builds a local style from the clipped extract `data/osm/north.osm.pbf` and sets
`NEXT_PUBLIC_MAP_STYLE_URL`. MapLibre 6 needs its worker files served next to each other; they are
copied from `node_modules` into `public/maplibre/` before `next dev` and `next build`.
