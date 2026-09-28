# Technology Decisions

## Database Evaluation

### Recommended: PostgreSQL + pgvector

**Pros:**
- Native JSON/JSONB support for flexible metadata storage
- pgvector extension for future embedding-based deduplication
- ACID compliance for data integrity
- Mature ecosystem, excellent Python support (asyncpg, SQLAlchemy)
- Single database for metadata + vector search (no polyglot persistence)
- Cost-effective on managed services (RDS, Cloud SQL, Neon, Supabase)

**Cons:**
- Vector search less optimized than dedicated vector DBs (Pinecone, Weaviate)
- Horizontal scaling requires more effort (Citus, read replicas)
- pgvector HNSW index build can be slow for large datasets

**Cost Considerations:**
- Managed PostgreSQL: ~$15-50/month for small instances
- pgvector included at no extra cost
- Storage: ~$0.10-0.20/GB/month

**Scaling Considerations:**
- Vertical scaling to 64+ vCPU, 512GB RAM
- Read replicas for query distribution
- Citus extension for horizontal sharding if needed
- Partitioning by topic/category for query performance

**Operational Complexity:** Low-Medium. Well-understood, excellent tooling.

---

### Alternative: MongoDB + Atlas Vector Search

**Pros:**
- Flexible schema for evolving metadata
- Native vector search integration
- Horizontal scaling via sharding built-in

**Cons:**
- No ACID transactions across documents (until recently)
- Less mature Python async ecosystem
- Additional cost for Atlas Vector Search
- Eventual consistency by default

**Verdict:** PostgreSQL preferred for this use case.

---

## Cache Evaluation

### Recommended: Redis (Optional - Defer to V2)

**When Needed:**
- LLM response caching (exact prompt matching)
- Rate limiting / token bucket for API quotas
- Session/cache for batch job coordination
- Distributed locking for worker coordination

**V1 Decision:** **Do not include Redis in V1.**
- Add complexity without clear V1 need
- File-based checkpointing sufficient for thousands of questions
- Can add Redis when:
  - Multi-worker parallel processing needed
  - LLM caching shows measurable cost savings
  - Rate limiting becomes bottleneck

**Cost if Added Later:** ~$15-30/month (managed Redis)

---

## Queue Evaluation

### Recommended: None for V1 (File-based + In-Process)

**V1 Approach:**
- Single-process batch worker reading JSONL files
- Checkpointing via file position / processed IDs log
- Retry logic in-process with exponential backoff

**When to Add Queue (V2+):**
- Multiple parallel workers needed
- Webhook/callback on completion
- Priority queues (retry failed vs new batch)
- Horizontal scaling across machines

**Options When Needed:**
- **Redis + BullMQ / Celery**: Simple, mature, good for Python
- **RabbitMQ**: More features, higher ops complexity
- **Kafka**: Overkill for this scale, but durable

**V1 Decision:** **No queue infrastructure.** Simplicity wins.

---

## Search Engine Evaluation

### Recommended: PostgreSQL Full-Text Search + pgvector (Future)

**V1:** No search engine needed. Output is JSONL for downstream consumption.

**Future (Deduplication Engine):**
- pgvector for semantic similarity (embeddings)
- PostgreSQL FTS for keyword/tag filtering
- Hybrid search: vector + keyword + metadata filters

**Dedicated Search (If Needed Later):**
- **Meilisearch**: Simple, fast, good for metadata filtering
- **Typesense**: Similar to Meilisearch
- **Elasticsearch/OpenSearch**: Powerful but high ops cost

**V1 Decision:** **Defer entirely.** Not in scope for Metadata Engine.

---

## Cloud / Deployment Evaluation

### Recommended: Container-Ready, Cloud-Agnostic

**V1 Target:** Single VM / VPS / Docker Compose

**Options:**
| Platform | Pros | Cons | Est. Cost (Small) |
|----------|------|------|-------------------|
| **VPS (DigitalOcean, Hetzner, Linode)** | Simple, predictable cost, full control | Manual ops, no auto-scale | $6-24/mo |
| **AWS ECS/Fargate** | Managed, auto-scale, IAM integration | Complex, vendor lock-in | $30-100+/mo |
| **GCP Cloud Run** | Serverless containers, scale-to-zero | Cold starts, vendor lock-in | $10-50/mo |
| **Azure Container Apps** | Similar to Cloud Run | Vendor lock-in | $10-50/mo |
| **Railway / Render / Fly.io** | Developer-friendly, git-deploy | Less control, pricing changes | $10-50/mo |

**Recommendation:** **Start with VPS + Docker Compose** (Hetzner/DigitalOcean).
- Lowest cost, full control, easy to migrate later
- Docker Compose file works locally and on any VM
- Can move to managed containers when scale demands

**Infrastructure as Code:** Defer Terraform to V2. Document deployment manually for V1.

---

## LLM Provider Evaluation

### Selected: Google Gemini free tier (default) + Groq (free alternative) + OpenAI (optional paid) - User Confirmed (M3, Sept 2026)

> Amended twice: first from "OpenAI only" to Groq, then to Gemini after the
> Groq key expired and re-provisioning failed. The gateway is
> provider-pluggable (`QME_LLM_PROVIDER=gemini|groq|openai|custom`), so swapping
> is a config change, not code. **Structured-output-only is the hard
> constraint:** the default must support `response_format` JSON Schema. Gemini's
> OpenAI-compatible endpoint accepts `json_schema` + `strict: true` and returns
> schema-conformant JSON (validated live in the M3 gate, including nested
> `$defs`/`$ref` schemas needed by later milestones).

**Why Gemini free tier as default (probed live, Sept 2026):**
- Free, no credit card: key from aistudio.google.com
- OpenAI-compatible endpoint (`/v1beta/openai/`) → same `openai` SDK, `base_url` swap
- Strict `json_schema` accepted; nested `$defs`/`$ref`/nullable `anyOf` all validated
- Highest free volume of the free options tested: `gemini-3.5-flash-lite` answered
  10/10 burst calls with zero errors; `gemini-3.8-flash` is capped at 5 req/min
- Quota 429s carry **no `retry-after` header** — the delay rides the error body
  (`RetryInfo.retryDelay`, "Please retry in 33s"); the gateway parses both
- Caveats: `gemini-2.5-flash` is retired for new users (use 3.x); occasional
  503 "high demand" (gateway retries 5xx with backoff); free-tier prompts may
  be used by Google to improve products outside UK/CH/EEA

**Model Strategy:**
| Task | Model | Rationale |
|------|-------|-----------|
| Topic/Subtopic Classification | gemini-3.5-flash-lite | Strict structured output, highest free RPM; M3 eval = 100% category/topic |
| Difficulty Scoring | gemini-3.5-flash-lite | Structured reasoning sufficient |
| Solution Generation | gemini-3.5-flash-lite (→ gemini-3.8-flash if quality gaps) | Multi-step math; revisit at Step 5 eval |
| Formula Extraction | gemini-3.5-flash-lite | Pattern recognition, structured output |
| Validation (LLM-assisted) | gemini-3.5-flash-lite (→ gemini-3.8-flash if needed) | Paid fallback (OpenAI) available |

**Cost:** $0 during development/evaluation on the free tier. Paid fallback
(OpenAI GPT-4o / 4o-mini) remains configured for when free-tier volume is not
enough (est. ~$260-300 per 10K questions) or when evals show quality gaps.

**Volume planning:** flash-lite measured ≥10 req/min free (per-model quota);
Gemini rate limits are per-model per-minute, so large batches pace via the
gateway's parsed 429 delay (cap 60s). Adding another OpenAI-compatible
provider (Groq, Cerebras, ...) stays config-only.

**Optimization:**
- Space batch requests to stay under the per-model per-minute quota (gateway handles 429 waits automatically)
- Use strict structured outputs to avoid validation retries
- `gemini-3.8-flash` for hard stages, `flash-lite` for volume stages — set per
  stage via `MODEL_*` env vars / `BatchConfig.model_overrides`

---

## Embedding Model Evaluation

### Recommended: OpenAI text-embedding-3-small (Future)

**When Needed:** Deduplication Engine (separate system)

**Current V1:** Not needed. Metadata Engine outputs structured data only.

**Future Cost:** ~$0.02/1K tokens -> ~$0.20 for 10K questions

---

## Summary: V1 Technology Stack

| Component | Choice | Status |
|-----------|--------|--------|
| Language | Python 3.11+ | Confirmed |
| Framework | FastAPI | Confirmed |
| Validation | Pydantic v2 | Confirmed |
| Database | PostgreSQL + pgvector | **Pending Approval** |
| Cache | None (Defer) | Deferred |
| Queue | None (Defer) | Deferred |
| Search | None (Defer) | Deferred |
| Deployment | Docker Compose on VPS | **Pending Approval** |
| LLM Provider | Google Gemini free tier (default) + Groq (free alt) + OpenAI (optional paid) | Confirmed (M3) |
| Embeddings | OpenAI text-embedding-3-small | Future |

---

## Pending Approvals Required

1. **PostgreSQL + pgvector** as primary database (for future deduplication integration)
2. **Docker Compose on VPS** as deployment target (Hetzner/DigitalOcean recommended)
3. **Defer Redis, Queue, Search** to V2+

Please confirm or request changes before I proceed to architecture design.
