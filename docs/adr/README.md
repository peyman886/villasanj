# Architecture Decision Records

Format: *Context → Decision → Alternatives considered → Consequences*. Status is one of
`Proposed`, `Accepted`, `Superseded by ADR-XXXX`. An ADR is never edited to reverse a decision; a new
ADR supersedes it. Measured evidence (dates, numbers, sources) goes inline.

| ADR | Title | Status |
|---|---|---|
| [0001](0001-modular-monolith-hexagonal.md) | Hexagonal modular monolith with six bounded contexts | Accepted |
| [0002](0002-technology-stack.md) | Technology stack (and what we deliberately leave out) | Accepted |
| [0003](0003-local-infrastructure-and-hardware-budget.md) | Local infrastructure on a 16 GB Apple M4 | Accepted |
| [0004](0004-llm-gateway-avalai.md) | LLM gateway: AvalAI adapter behind `LLMClient` with a decorator chain | Accepted |
| [0005](0005-llm-model-selection-and-cost.md) | Model per LLM task and total cost estimate | Accepted |
| [0006](0006-embeddings-text-and-image.md) | Embeddings: image local, text via AvalAI behind an eval gate | Accepted (image part superseded by 0012) |
| [0007](0007-provenance-and-no-fabricated-numbers.md) | Provenance everywhere; LLMs never write numbers | Accepted |
| [0008](0008-ethical-crawling.md) | Ethical, reproducible crawling | Accepted |
| [0009](0009-entity-resolution-strategy.md) | Staged, precision-first entity resolution | Accepted |
| [0010](0010-persistence-postgres.md) | One Postgres: schema per context, queue, cache and vectors | Accepted |
| [0011](0011-platform-scope-after-tos-audit.md) | Platform scope after the robots.txt/ToS audit (jabama + shab) | Accepted |

All ADRs were accepted with the Milestone 0 approval (2026-10-01). Later refinements are
appended as dated *Amendment* sections inside the ADR.
| [0012](0012-image-matching-evidence.md) | Image matching evidence: local DINOv2 + pHash, chosen by measurement | Accepted |
| [0013](0013-geo-evidence-osm-coastline-and-osrm.md) | Geo evidence: OSM coastline in PostGIS and free-flow OSRM drive times | Accepted |
