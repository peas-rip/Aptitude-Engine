# Deployment Architecture: Question Metadata Engine

## 1. Deployment Target (V1)

**Platform:** Single VPS (Hetzner CX42 / DigitalOcean 8GB RAM / 4 vCPU)
**Orchestration:** Docker Compose
**Networking:** Single host, no Kubernetes

## 2. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        VPS (Single Host)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │   Nginx      │  │   FastAPI    │  │   Batch Worker       │  │
│  │   (Reverse   │──│   (API)      │  │   (CLI / Background) │  │
│  │   Proxy)     │  │   Port 8000  │  │   Same Image         │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
│         │                │                     │                │
│         └────────────────┼─────────────────────┘                │
│                          ▼                                     │
│                 ┌──────────────────┐                           │
│                 │   Shared Volume  │                           │
│                 │   /data          │                           │
│                 │   - input/       │                           │
│                 │   - output/      │                           │
│                 │   - checkpoints/ │                           │
│                 └──────────────────┘                           │
└─────────────────────────────────────────────────────────────────┘
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
      ┌───────────────┐       ┌───────────────┐
      │  OpenAI API   │       │  PostgreSQL   │
      │  (External)   │       │  (V2+: Local  │
      │               │       │   or Managed) │
      └───────────────┘       └───────────────┘
```

## 3. Docker Compose Services

### 3.1 docker-compose.yml (Production)
```yaml
version: "3.8"

services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./certs:/etc/nginx/certs:ro
    depends_on:
      - api
    restart: unless-stopped

  api:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    command: ["uvicorn", "qme.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
    environment:
      - ENVIRONMENT=production
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - LOG_LEVEL=INFO
    volumes:
      - data:/data
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: "2"
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  worker:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    command: ["python", "-m", "qme.cli", "process", "--input", "/data/input/batch.jsonl", "--output", "/data/output", "--checkpoint-dir", "/data/checkpoints"]
    environment:
      - ENVIRONMENT=production
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - LOG_LEVEL=INFO
    volumes:
      - data:/data
    deploy:
      resources:
        limits:
          memory: 3G
          cpus: "2"
    restart: "no"  # Run once per batch
    profiles:
      - batch

volumes:
  data:
    driver: local
```

### 3.2 docker-compose.dev.yml (Development)
```yaml
version: "3.8"

services:
  api:
    build:
      context: ..
      dockerfile: docker/Dockerfile.dev
    command: ["uvicorn", "qme.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
    environment:
      - ENVIRONMENT=development
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - LOG_LEVEL=DEBUG
    volumes:
      - ..:/app
      - data:/data
    ports:
      - "8000:8000"
    stdin_open: true
    tty: true

volumes:
  data:
```

### 3.3 Dockerfile (Multi-stage)
```dockerfile
# Builder stage
FROM python:3.11-slim AS builder
WORKDIR /app
COPY pyproject.toml uv.lock* ./
RUN pip install --no-cache-dir uv && uv sync --frozen

# Runtime stage
FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
COPY src/ ./src/
COPY data/taxonomy/ ./data/taxonomy/
COPY config/prompts/ ./config/prompts/
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
CMD ["uvicorn", "qme.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 4. Networking

| Component | Port | Access |
|-----------|------|--------|
| Nginx HTTP | 80 | Public (redirect to HTTPS) |
| Nginx HTTPS | 443 | Public |
| FastAPI | 8000 | Internal (Nginx only) |
| PostgreSQL | 5432 | Internal (V2+) |
| SSH | 22 | Admin only (key-based) |

**Firewall:** UFW - allow 22, 80, 443 only

## 5. Scaling Strategy

### V1: Vertical Scaling
- Increase VPS size (CPU/RAM)
- Add API workers (`--workers 4`)
- Single batch worker (sequential)

### V2: Horizontal Scaling (When Needed)
- Multiple API replicas behind load balancer
- Multiple batch workers with queue (Redis + Celery)
- Read replicas for PostgreSQL
- Separate ingestion/processing hosts

### Trigger Points for Scaling
| Metric | Threshold | Action |
|--------|-----------|--------|
| API p95 latency | >2s | Add API workers/replicas |
| Batch queue time | >1hr | Add batch workers |
| DB CPU | >70% | Read replica / upgrade |
| OpenAI rate limits | Frequent 429 | Batch API, request spacing |

## 6. Monitoring Strategy

### 6.1 Metrics (Prometheus)
- **API:** Request rate, latency (p50/p95/p99), error rate
- **Batch:** Questions processed, success/failed/review rates, throughput
- **LLM:** Tokens per question, cost per question, model distribution
- **System:** CPU, memory, disk, network

### 6.2 Logging
- Structured JSON (structlog)
- Correlation IDs across request/batch
- Log levels: DEBUG (dev), INFO (prod), ERROR (always)
- Retention: 30 days (local), 90 days (shipped to Loki/Grafana Cloud V2)

### 6.3 Alerting (V2: Grafana/Prometheus Alertmanager)
| Alert | Condition | Severity |
|-------|-----------|----------|
| API down | Health check fails 3x | Critical |
| Batch failure rate | >10% in 1hr | Warning |
| Cost spike | >2x baseline daily | Warning |
| Disk space | >80% | Warning |
| Review queue backlog | >100 items | Warning |

## 7. Backup Strategy

| Data | Frequency | Retention | Method |
|------|-----------|-----------|--------|
| Input files | On upload | 90 days | Object storage (S3/compat) |
| Output JSONL | Per batch | 1 year | Object storage |
| Checkpoints | Every 10 questions | 7 days | Local volume |
| PostgreSQL | Daily | 30 days | pg_dump to object storage |
| Taxonomy/Prompts | On change | Forever | Git |

## 8. Disaster Recovery

| Scenario | RTO | RPO | Procedure |
|----------|-----|-----|-----------|
| VPS failure | 30 min | 1 hr | Restore from VPS snapshot + data volume |
| Data corruption | 1 hr | 1 batch | Re-import from JSONL outputs |
| OpenAI outage | N/A | N/A | Queue batches, process when restored |
| Bad deployment | 10 min | 0 | Docker Compose rollback to previous image |

## 9. Cost Considerations (Monthly Estimate)

| Component | V1 (Small) | V2 (Medium) |
|-----------|------------|-------------|
| VPS (Hetzner CX42) | ~€35/mo | ~€70/mo (2x) |
| Managed PostgreSQL | N/A | ~$50/mo |
| Object Storage | ~$5/mo | ~$20/mo |
| OpenAI API | ~$300/mo (10K q) | ~$3000/mo (100K q) |
| Monitoring | Free (self-hosted) | ~$50/mo (Grafana Cloud) |
| **Total** | **~$340/mo** | **~$3170/mo** |

## 10. Operational Considerations

### 10.1 Deployment Process
```bash
# Build and deploy
docker compose -f docker-compose.yml build
docker compose -f docker-compose.yml up -d

# Run batch
docker compose -f docker-compose.yml --profile batch run --rm worker

# View logs
docker compose logs -f api
docker compose logs worker
```

### 10.2 Rollback
```bash
docker compose pull  # Get previous image tag
docker compose up -d --force-recreate
```

### 10.3 Secrets Management
- V1: `.env` file on VPS (chmod 600)
- V2: HashiCorp Vault / AWS Secrets Manager / Doppler

### 10.4 Maintenance Windows
- Weekly: OS updates, Docker image rebuild
- Monthly: Dependency updates, security scan
- Quarterly: Model evaluation, prompt optimization

## 11. Future Migration Path

| From | To | Trigger |
|------|-----|---------|
| Docker Compose | Kubernetes (EKS/GKE) | >5 replicas, multi-AZ |
| Single VPS | Managed K8s | Team growth, compliance |
| Local PostgreSQL | RDS/Cloud SQL | HA requirements |
| File checkpoints | Redis + Celery | Distributed workers |
| Nginx | Cloud Load Balancer | TLS termination, WAF |
