# ADR-0001 — Hexagonal modular monolith with six bounded contexts

Status: Proposed · Date: 2026-10-01

## Context

The system is a batch pipeline (crawl → parse → normalize → resolve → price → enrich → project) plus
an online API. The brief requires Clean/Hexagonal architecture, SOLID, and **real** Open/Closed:
adding a platform, LLM provider, embedding model or search engine must not touch the core. One
developer builds it, on one laptop, for a demo.

## Decision

1. **Modular monolith**: one Python package `villasanj`, one deployable image, several entrypoints
   (CLI jobs, API, workers). No microservices.
2. **Six bounded contexts** (ARCHITECTURE §2): Ingestion, Catalog, EntityResolution, Pricing,
   Enrichment, Discovery, plus a `shared` kernel and `entrypoints`. API/Web is a delivery layer, not
   a context. Normalization is split between adapters (source-specific) and the shared kernel
   (Persian text). ReviewQueue is ER's adjudication. Explanation is part of Discovery.
3. **Three layers per context** (`domain` → `application` → `infrastructure`), with dependencies
   pointing inward. Domain uses the stdlib only. Pydantic is allowed from `application` outward.
4. **Enforcement, not convention**: `import-linter` contracts (domain purity, layer order, context
   DAG, sibling independence), plus an architecture test that forbids platform slugs in core packages.
5. **Composition root** per entrypoint, hand-written (no DI framework). Adapters are chosen from
   config; source adapters are discovered through the `villasanj.sources` entry-point group.
6. **Abstractions only where they pay**: a port exists when (a) it isolates I/O or a vendor, which
   makes tests deterministic, or (b) there are ≥ 2 real implementations. Examples that do *not* get
   a port: the Persian normalizer (pure functions), the pricing engine (pure domain service),
   the Splink training loop (only one implementation, wrapped by the `PairScorer` port at its boundary).

## Alternatives considered

- **Microservices per context.** Rejected: operational cost with no scaling need; a network hop
  between every stage of a batch pipeline.
- **Flat "services/" + "models/" layout.** Rejected: no enforceable boundaries; OCP would stay nominal.
- **DI framework (dependency-injector, lagom).** Rejected for now: a hand-written root is ~200 lines,
  explicit and type-checked. Revisit if wiring exceeds that.
- **One package per context (uv workspace).** Rejected: import-linter gives the same boundary
  guarantees with less packaging overhead.

## Consequences

- (+) Boundaries are machine-checked; the OCP claim can be shown in the demo (the diff of the jabama PR).
- (+) Unit tests run on pure domain objects plus fakes and need no Docker.
- (−) Some mapping code between DTOs, domain objects and ORM rows. Accepted as the price of a pure domain.
- (−) Pydantic in application couples use cases to it. Mitigated: it never reaches `domain`.

**Tension noted (purity vs deliverability):** Splink and DuckDB own their data frames, and forcing them
through domain objects row by row would be slow and pointless. The ER *scoring* adapter therefore
operates on bulk tabular features in infrastructure and returns `MatchScore` value objects at the port
boundary. The domain stays pure; the adapter is pragmatic.
