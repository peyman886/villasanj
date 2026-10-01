# ADR-0010 — One Postgres: schema per context, queue, cache and vectors

Status: Proposed · Date: 2026-10-01

## Context

The system needs relational data (listings, decisions, quotes), geo (points, coastline, distance), full
text (normalized Persian), vectors (image/text embeddings), a durable crawl queue, and an LLM
cache/ledger. Scale: ~3k listings, ~40k photos, ~100k calendar observations, a few thousand LLM calls.
There is one machine with a tight memory budget (ADR-0003).

## Decision

1. **PostgreSQL 17 + PostGIS + pgvector + pg_trgm** in one instance (custom multi-arch image).
2. **One schema per bounded context** (`ingestion`, `catalog`, `er`, `pricing`, `enrichment`, `discovery`)
   plus `ops` (jobs, LLM cache, LLM ledger). A context's repositories touch only its own schema.
   Cross-context reads go through the upstream context's application ports, implemented by reading its
   tables through a read-only adapter. There are no cross-schema foreign keys except to stable
   identifiers (listing id, villa id).
3. **Queue:** `ingestion.frontier` consumed with `SELECT … FOR UPDATE SKIP LOCKED`; per-host
   scheduling uses `next_attempt_at`. The queue is resumable after crashes.
4. **Vectors:** `photo_embedding(photo_id, model_id, embedding vector)` with **partial HNSW indexes per
   model** on a cast to its fixed dimension (e.g. `(embedding::vector(384)) WHERE model_id = 'dinov2-s14'`).
   Text vectors are ≤ 2,000 dims (ADR-0006). At this scale exact kNN in the worker (NumPy) is also
   fine; the index exists for query-time use.
5. **Full text:** a `tsvector` built with the `simple` configuration over **already-normalized** text
   (Postgres has no Persian stemmer), plus `pg_trgm` for fuzzy place names.
6. **Migrations:** Alembic, one linear history. Integration tests run migrations on a Testcontainers
   Postgres built from the same image.
7. **Blobs are not in Postgres**: snapshots and photos go to the `BlobStore` (filesystem volume); the DB
   stores keys and hashes.

## Alternatives considered

- **Separate vector DB (Qdrant is already on this machine).** Another service and RAM for ~40k
  vectors that pgvector handles easily. It stays available behind the embedding/index ports if needed.
- **SQLite/DuckDB only.** No PostGIS-grade geo, weak concurrency for API + worker. DuckDB is still used
  *inside* Splink as a compute engine.
- **Redis for queue/cache.** See ADR-0002.

## Consequences

- (+) One backup, one connection pool, and transactional consistency across a pipeline stage.
- (+) Schemas make context ownership visible in the database too.
- (−) Postgres is a shared failure point; acceptable for a local demo.
- Limits to watch: frontier contention (irrelevant at 1 req/3 s/host) and HNSW build memory
  (small at 40k × 384).
