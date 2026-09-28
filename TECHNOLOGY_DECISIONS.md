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

### Selected: OpenAI (GPT-4o, GPT-4o-mini) - User Confirmed

**Model Strategy:**
| Task | Model | Rationale |
|------|-------|-----------|
| Topic/Subtopic Classification | GPT-4o-mini | Fast, cheap, structured output reliable |
| Difficulty Scoring | GPT-4o-mini | Structured reasoning sufficient |
| Solution Generation | GPT-4o | Complex reasoning, multi-step math |
| Formula Extraction | GPT-4o-mini | Pattern recognition, structured output |
| Validation (LLM-assisted) | GPT-4o | Need strong reasoning for verification |

**Cost Estimate (10K questions):**
- Classification (4o-mini): ~$0.15/1K tokens x ~500 tokens x 10K = ~$7.50
- Solution Gen (4o): ~$2.50/1K tokens x ~1K tokens x 10K = ~$250
- Formula Extraction (4o-mini): ~$0.15/1K tokens x ~300 tokens x 10K = ~$4.50
- **Total: ~$260-300 for 10K questions**

**Optimization:**
- Batch API (50% discount) for non-urgent processing
- Cache identical prompts
- Use structured outputs to avoid retries

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
| LLM Provider | OpenAI (4o, 4o-mini) | Confirmed |
| Embeddings | OpenAI text-embedding-3-small | Future |

---

## Pending Approvals Required

1. **PostgreSQL + pgvector** as primary database (for future deduplication integration)
2. **Docker Compose on VPS** as deployment target (Hetzner/DigitalOcean recommended)
3. **Defer Redis, Queue, Search** to V2+

Please confirm or request changes before I proceed to architecture design.
