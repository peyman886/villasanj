# Architecture Decision Records

Format: *Context → Decision → Alternatives considered → Consequences*. Status is one of
`Proposed`, `Accepted`, `Superseded by ADR-XXXX`. An ADR is never edited to reverse a decision; a new
ADR supersedes it. Measured evidence (dates, numbers, sources) goes inline.

| ADR | Title | Status |
|---|---|---|
| [0001](0001-modular-monolith-hexagonal.md) | Hexagonal modular monolith with six bounded contexts | Proposed |
| [0002](0002-technology-stack.md) | Technology stack (and what we deliberately leave out) | Proposed |
| [0003](0003-local-infrastructure-and-hardware-budget.md) | Local infrastructure on a 16 GB Apple M4 | Proposed |
| [0004](0004-llm-gateway-avalai.md) | LLM gateway: AvalAI adapter behind `LLMClient` with a decorator chain | Proposed |
| [0005](0005-llm-model-selection-and-cost.md) | Model per LLM task and total cost estimate | Proposed |
| [0006](0006-embeddings-text-and-image.md) | Embeddings: image local, text via AvalAI behind an eval gate | Proposed |
| [0007](0007-provenance-and-no-fabricated-numbers.md) | Provenance everywhere; LLMs never write numbers | Proposed |
| [0008](0008-ethical-crawling.md) | Ethical, reproducible crawling | Proposed |
| [0009](0009-entity-resolution-strategy.md) | Staged, precision-first entity resolution | Proposed |
| [0010](0010-persistence-postgres.md) | One Postgres: schema per context, queue, cache and vectors | Proposed |

All ADRs become `Accepted` when the owner approves Milestone 0.
