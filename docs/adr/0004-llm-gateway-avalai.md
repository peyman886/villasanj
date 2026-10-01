# ADR-0004 — LLM gateway: AvalAI adapter behind `LLMClient` with a decorator chain

Status: Accepted (M0 approval, 2026-10-01) · Date: 2026-10-01

## Context

- All LLM calls (text and vision) go through **AvalAI**, an OpenAI-compatible gateway.
  `/v1/models` lists 365 models from several vendors (OpenAI, Google, Anthropic, Alibaba, DeepSeek, …).
- Credit is limited, so the brief requires a persistent cache, a per-call token/cost ledger, per-job
  budget caps, `--dry-run`, cheap models for bulk work and strong models only for the ER gray zone.
- Tests must never call the real API.
- Probe findings (2026-10-01, 10 tiny calls, ≈ $0.006 total):
  - Rate-limit headers show **tier 3** (e.g. gemini-3.1-flash-lite 1000 RPM / 3M TPM; claude-sonnet-5-5
    50 RPM / 120k TPM).
  - `response_format: json_schema` (strict) works for Gemini and OpenAI models, including
    `["number","null"]` union types.
  - `gemini-embedding-001` returns `usage.prompt_tokens = 0`. Reported usage cannot be trusted for
    every model, so the ledger needs an estimate path.
  - Gemini models bill ~1,090 prompt tokens **per image regardless of size or `detail`**.
    gpt-5.4-mini bills by patches (34 tokens for a 32×32 image at `detail: low`).
  - A reasoning model with `max_tokens: 5` spent all 5 tokens on reasoning and returned empty text.
    `finish_reason = length` must be treated as an error.
- The owner's `.env` has `AVALAI_API_KEY = …` (spaces around `=`). python-dotenv tolerates this, but
  shell sourcing and Compose's `env_file` do not. It will be normalised to `KEY=value` in M1.

## Decision

### Configuration
- Secrets come **only** from the environment: `AVALAI_API_KEY` (`SecretStr`) and `AVALAI_BASE_URL`
  (default `https://api.avalai.ir/v1`; mirror `https://api.avalapis.ir/v1`). Pydantic Settings with
  `env_nested_delimiter="__"` (matching the existing `LLM__PROVIDER`).
- Non-secret routing lives in a versioned `config/llm.toml`, overridable by env. **No model name
  appears in code.** Sketch:

  ```toml
  [budget]
  project_usd = 30.0          # hard stop across all jobs (ledger)
  default_job_usd = 2.0

  [tasks.claim_extraction]
  model = "gemini-3.1-flash-lite"
  fallbacks = ["gpt-5.4-mini"]
  max_output_tokens = 1200
  temperature = 0.0
  concurrency = 8

  [tasks.er_judge]
  model = "gemini-3.8-flash"            # provisional until the M5 bake-off
  fallbacks = ["gpt-5.4-mini"]
  max_output_tokens = 1500

  [models."gemini-3.1-flash-lite"]     # calibration for the dry-run estimator
  image_tokens = 1090                  # measured 2026-10-01
  chars_per_token_fa = 4.3             # measured on one sample; recalibrated from the ledger
  ```
- Prices are read from a `/v1/models` snapshot (`docs/reference/avalai-models-<date>.csv`), refreshed
  by `make llm-models`. The cost of each call is computed from the snapshot that was current at the
  time and stored in the ledger row.

### Port (shared.application)
- `LLMClient.generate(request: LLMRequest[T], ctx: JobContext) -> LLMResponse[T]`.
  - `LLMRequest`: `task: LLMTask` (enum: `QUERY_UNDERSTANDING`, `ER_JUDGE`, `CLAIM_EXTRACTION`,
    `TEXT_NORMALIZATION`, `VISION_TAGGING`, `REVIEW_SUMMARY`, `EXPLANATION`), `prompt_id`,
    `prompt_version`, multimodal `messages` (text parts + image parts referenced by sha256),
    `output_schema: type[T]` (Pydantic model), `max_output_tokens`.
  - `LLMResponse`: `value: T`, `model`, `usage`, `usage_source` (`reported | estimated`), `cost_usd`,
    `cache_hit`, `attempts`, `latency_ms`.
- One port handles text and vision. A separate `VisionLLMClient` would duplicate the chain for no gain.
  Vision capability is validated at startup against the model snapshot (`supports_vision`).

### Decorator chain (outer → inner)
1. **Caching**: key = `sha256(canonical_json(provider, model, prompt_id, prompt_version, messages with
   image hashes, output JSON-schema hash, generation params))`. Stored in `ops.llm_cache`. A cache hit
   costs $0 and is logged.
2. **Fallback**: primary → `fallbacks` in order, **only** on transport/availability failures
   (timeouts, 5xx, 429 after retries, model-not-found). A fallback is never used to shop for a
   "better" answer.
3. **Retrying**: exponential backoff with jitter (config: attempts, base, cap, timeout). Honours
   `Retry-After`. On schema-validation failure it retries with the validation error appended
   (max 2). It then raises `LLMOutputInvalid`, a domain-specific error that carries the task and
   prompt id but no response body.
4. **Cost governing**: before every attempt, the worst-case cost (estimated input + `max_output_tokens`)
   is checked against the remaining job and project budgets and raises `BudgetExceeded` before the
   call. After every attempt (including failed validations, which still cost tokens) it writes an
   `ops.llm_call` row. Concurrency is capped per task through a semaphore (tier 3 limits are far above
   our needs; 429s are still handled by retry).
5. **Provider**: `AvalAIProvider` uses the OpenAI SDK with `base_url` and `json_schema` response_format
   (strict). If a model rejects strict schemas, a per-model `structured_mode = "json_object"` setting
   switches to JSON mode + Pydantic validation.

### Dry-run
Use cases that call LLMs expose `plan() -> Sequence[LLMRequest]`. `--dry-run` resolves cache hits,
estimates the rest (tiktoken `o200k_base` for OpenAI models; calibrated chars-per-token and per-image
tokens for others), prints calls / cache hits / estimated USD per task, and exits without calling the
provider. The estimator is re-calibrated from ledger actuals (acceptance: ±25% in M9).

### Testing
- `FakeLLMProvider` sits at the provider level, so the real decorators are exercised in unit tests.
  It is deterministic, scripted per `(task, prompt_id, input hash)`, and can inject invalid JSON,
  5xx, timeouts and usage figures.
- Live tests carry the pytest marker `live_llm`, are excluded by default, run with `make test-live`,
  and have a $0.05 cap.

### Secrets hygiene
`SecretStr` everywhere. A structlog processor masks the key value and `Authorization` headers. SDK
exceptions are wrapped, so no raw request/response is logged. gitleaks runs in pre-commit. `.env` is
git-ignored, and `.env.example` has no values.

## Alternatives considered

- **LiteLLM as the client.** Adds a large dependency for something AvalAI already does (multi-vendor
  behind the OpenAI API). Our cost/budget/cache logic is domain-specific anyway.
- **Separate text and vision ports.** Duplicates the chain; rejected (see above).
- **Redis cache.** Postgres is already there and persistent (ADR-0010).
- **Fake at the use-case level only.** It would leave cache/retry/budget untested; the fake lives at
  the provider level.

## Consequences

- (+) Changing provider = new provider adapter + `LLM__PROVIDER`; everything above it is unchanged.
- (+) Re-running any pipeline stage with unchanged prompts and inputs costs $0.
- (+) Spend is attributable per task, per job and per milestone.
- (−) The cache key includes `prompt_version`: editing a prompt without bumping the version is caught
  by a test that hashes prompt templates.

## Amendment (M1 implementation, 2026-10-01)

Refinements found while building; the decision itself stands.

1. **Chain order.** Implemented as `RoutedLLMClient` (routing, fallback, per-task concurrency) →
   `CachingInvoker` → `RetryingInvoker` → `CostGoverningInvoker` → `StructuredOutputInvoker` →
   provider. Cache keys include the model, so routing must sit above the cache. Validation lives
   below the cost governor so that failed attempts are still charged to the ledger with an accurate
   status (`invalid_output`, `truncated`).
2. **Token estimation without tiktoken.** tiktoken downloads its BPE files at first use, which is a
   hidden network call and breaks offline dry-runs. The estimator is a calibrated heuristic
   (chars per token and per-image tokens per model, in `config/llm.toml`), re-calibrated from ledger
   actuals.
3. **Routing overrides** are done by pointing `LLM__ROUTING_FILE` at another TOML file (e.g. a lean
   profile) instead of per-field environment overrides.
4. **OpenAI SDK 3.x uses httpx2.** Adapter tests mock it with `httpx2.MockTransport`.
5. **Concurrency and budgets.** The governor reserves each call's worst-case cost before calling, so
   parallel calls cannot jointly overspend a budget (unit-tested).
6. **Measured (live smoke, 2026-10-01).** On a trivial JSON reply, `gemini-3.8-flash` spent
   164–255 reasoning tokens (thinking is on by default), while `gemini-3.1-flash-lite` spent none.
   Gemini also does not appear to bill the JSON schema as input tokens (37 prompt tokens reported), so
   the estimator over-estimates schema-heavy calls. Both feed the M5/M10 calibration (see ADR-0005).
