# Deployment Guide: metadata-engine

## 1. Environment Requirements

| Requirement | Version | Purpose |
|-------------|---------|---------|
| Python | 3.11+ | Runtime |
| Docker | 24+ | Container runtime |
| Docker Compose | v2 | Multi-service orchestration |
| Nginx | 1.24+ | Reverse proxy / TLS (production) |
| PostgreSQL | 15+ (V2 only) | Persistent storage (V2+) |
| Git | 2.40+ | Source control |

## 2. Configuration

### 2.1 Environment Variables

All configuration is provided via environment variables (see `.env.example`):

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `OPENAI_API_KEY` | Yes | - | LLM provider authentication |
| `ENVIRONMENT` | Yes | `production` | `development` / `staging` / `production` |
| `LOG_LEVEL` | No | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `API_HOST` | No | `0.0.0.0` | Bind address |
| `API_PORT` | No | `8000` | API port |
| `API_WORKERS` | No | `2` | Uvicorn worker processes |
| `MODEL_CLASSIFIER` | No | `gpt-4o-mini` | Classification model |
| `MODEL_SOLUTION` | No | `gpt-4o` | Solution generation model |
| `CHECKPOINT_INTERVAL` | No | `10` | Questions between checkpoints |
| `MAX_RETRIES` | No | `3` | Per-question retry count |
| `INPUT_DIR` | No | `/data/input` | Input file location |
| `OUTPUT_DIR` | No | `/data/output` | Output file location |
| `CHECKPOINT_DIR` | No | `/data/checkpoints` | Checkpoint location |

### 2.2 Secret Management

- **V1:** `.env` file on the host (permissions 600, never committed)
- **V2:** HashiCorp Vault / AWS Secrets Manager / Doppler
- Never log, export, or embed API keys in images or code

## 3. Deployment Procedures

### 3.1 Local Development

```bash
cp .env.example .env          # Add OPENAI_API_KEY
make dev                      # Starts docker-compose.dev.yml
# API: http://localhost:8000
# Docs: http://localhost:8000/docs
```

### 3.2 Staging / Production (VPS)

```bash
# One-time server setup
git clone <repo> /opt/qme
cd /opt/qme
cp .env.example .env          # Configure secrets, chmod 600 .env

# Deploy
make build                    # docker compose -f docker/docker-compose.yml build
make deploy                   # docker compose -f docker/docker-compose.yml up -d

# Verify
curl -f http://localhost:8000/api/v1/health
docker compose -f docker/docker-compose.yml ps
docker compose -f docker/docker-compose.yml logs -f api
```

### 3.3 Running a Batch (Production)

```bash
# Place input file
cp batch.jsonl /opt/qme/data/input/

# Run worker (one-shot)
docker compose -f docker/docker-compose.yml --profile batch run --rm worker

# Or via API
curl -X POST http://localhost:8000/api/v1/batches -F file=@batch.jsonl
curl http://localhost:8000/api/v1/batches/{batch_id}
curl http://localhost:8000/api/v1/batches/{batch_id}/results > output.jsonl
```

## 4. Service Roles

| Service | Role | Restart Policy | Scaling |
|---------|------|----------------|---------|
| `nginx` | TLS termination, reverse proxy, static | unless-stopped | Vertical only |
| `api` | FastAPI request handling | unless-stopped | Add `--workers` or replicas |
| `worker` | Batch processing (one-shot) | `no` (per batch) | Run parallel instances with separate checkpoint dirs |

## 5. Scaling Strategy

### 5.1 Vertical (V1)
1. Increase VPS size (CPU/RAM)
2. Increase `API_WORKERS` (rule of thumb: 2 × CPU cores)
3. Keep single batch worker (sequential, checkpoint-safe)

### 5.2 Horizontal (V2+, trigger-based)

| Trigger | Action |
|---------|--------|
| API p95 latency > 2s | Add API replicas behind load balancer |
| Batch queue time > 1 hour | Add batch workers + Redis queue |
| PostgreSQL CPU > 70% | Read replica or instance upgrade |
| OpenAI 429 rate limits frequent | Enable Batch API, add request spacing |

## 6. Health Checks & Monitoring

### 6.1 Health Endpoints
- `GET /api/v1/health` - liveness + dependency status
- `GET /api/v1/metrics` - Prometheus metrics

### 6.2 Docker Healthcheck
- Interval: 30s, Timeout: 10s, Retries: 3
- Failure: container marked unhealthy, orchestrator restarts

### 6.3 Key Metrics to Watch
- `qme_questions_processed_total` (success/failure/review)
- `qme_request_latency_p95_seconds`
- `qme_llm_cost_usd_daily`
- `qme_review_queue_size`
- Disk usage on `/data` volume

## 7. Backup & Retention

| Data | Frequency | Retention | Method |
|------|-----------|-----------|--------|
| Input files | On upload | 90 days | Object storage (V2) or `/data/input` archive |
| Output JSONL | Per batch | 1 year | Object storage (V2) or tar archive |
| Checkpoints | Every 10 questions | 7 days | `/data/checkpoints` (local volume) |
| Logs | Continuous | 30 days | Log rotation (logrotate) |
| `.env` secrets | On change | Forever | Encrypted offsite backup |

### Backup Command Pattern
```bash
tar -czf backup-$(date +%F).tar.gz /opt/qme/data
```

## 8. Rollback Procedure

```bash
# 1. Identify last good image tag
git log --oneline -10

# 2. Checkout previous version
git checkout <last-good-sha>

# 3. Rebuild and restart
docker compose -f docker/docker-compose.yml build
docker compose -f docker/docker-compose.yml up -d

# 4. Verify health
curl -f http://localhost:8000/api/v1/health

# 5. Resume any interrupted batch (checkpoints preserved)
docker compose -f docker/docker-compose.yml --profile batch run --rm worker
```

**RTO target:** < 10 minutes. **RPO target:** last checkpoint (≤ 10 questions).

## 9. Operational Runbook

### Incident: OpenAI API outage
- **Symptom:** Timeouts, 5xx errors in logs
- **Action:** Batches auto-retry; queue new batches; no data loss expected
- **Escalation:** None required; monitor status.openai.com

### Incident: Rate limits (429)
- **Symptom:** `Rate limit exceeded` errors
- **Action:** Worker backs off automatically (exponential); if persistent, reduce `API_WORKERS` or enable Batch API
- **Verify:** Error rate returns to normal in metrics

### Incident: Checkpoint corruption
- **Symptom:** Resume fails with parse error on checkpoint file
- **Action:** Move corrupt file to `.bak`, rerun worker; it restarts from last valid checkpoint (worst case: reprocess ≤ 10 questions)

### Incident: Disk full
- **Symptom:** Write errors, health check fails
- **Action:** Archive old outputs, rotate logs, expand volume
- **Prevention:** Alert at 80% usage

### Incident: High memory (OOM)
- **Symptom:** Container killed by OOM reaper
- **Action:** Increase memory limit; check for unbounded result accumulation; confirm streaming JSONL writer is used

### Incident: Cost spike
- **Symptom:** `qme_llm_cost_usd_daily` > 2× baseline
- **Action:** Pause batches, inspect batch metrics for runaway retries or model misrouting, review prompt sizes

## 10. Post-Deployment Checklist

- [ ] Health endpoint returns 200
- [ ] Metrics endpoint returns valid Prometheus format
- [ ] `.env` permissions = 600, not in git
- [ ] Log rotation configured
- [ ] Disk usage alert at 80% configured
- [ ] Backup job scheduled
- [ ] Rollback procedure documented and tested
- [ ] Smoke test: process 1-question batch end-to-end
