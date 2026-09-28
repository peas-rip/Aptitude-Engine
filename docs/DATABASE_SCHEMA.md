# Database Schema: Question Metadata Engine

## 1. Schema Design Principles

- PostgreSQL + pgvector for metadata + future embeddings
- JSONB for flexible, evolving metadata fields
- Versioned tables for taxonomy, prompts, processing runs
- Immutable event log for audit trail
- Indexes optimized for deduplication engine queries

## 2. Core Tables

### 2.1 questions (Main Entity)
```sql
CREATE TABLE questions (
    question_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_hash         CHAR(64) NOT NULL,
    question_text        TEXT NOT NULL,
    options              JSONB NOT NULL,
    correct_answer       VARCHAR(10) NOT NULL,
    category_id          UUID REFERENCES taxonomy_nodes(id),
    topic_id             UUID REFERENCES taxonomy_nodes(id),
    subtopic_id          UUID REFERENCES taxonomy_nodes(id),
    concepts             TEXT[] DEFAULT ARRAY[]::TEXT[],
    question_type        VARCHAR(50) NOT NULL,
    difficulty_score     DECIMAL(3,2),
    difficulty_rating    VARCHAR(10),
    difficulty_factors   JSONB DEFAULT '{}',
    estimated_time_sec   INTEGER,
    solution             JSONB,
    solution_source      VARCHAR(20),
    solution_confidence  DECIMAL(3,2),
    formulas_used        JSONB DEFAULT '[]',
    source_name          VARCHAR(255),
    source_type          VARCHAR(50),
    source_identifier    VARCHAR(255),
    source_page          INTEGER,
    source_question_id   VARCHAR(255),
    processing_version   VARCHAR(20),
    model_used           VARCHAR(100),
    prompt_version       VARCHAR(64),
    processing_timestamp TIMESTAMPTZ DEFAULT NOW(),
    processing_duration_ms INTEGER,
    token_usage          JSONB,
    estimated_cost_usd   DECIMAL(10,6),
    validation_status    VARCHAR(20),
    validation_errors    JSONB DEFAULT '[]',
    validation_warnings  JSONB DEFAULT '[]',
    status               VARCHAR(20) DEFAULT 'processed',
    embedding            VECTOR(1536),
    created_at           TIMESTAMPTZ DEFAULT NOW(),
    updated_at           TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_questions_content_hash ON questions(content_hash);
CREATE INDEX idx_questions_category ON questions(category_id);
CREATE INDEX idx_questions_topic ON questions(topic_id);
CREATE INDEX idx_questions_subtopic ON questions(subtopic_id);
CREATE INDEX idx_questions_difficulty ON questions(difficulty_score);
CREATE INDEX idx_questions_status ON questions(status);
CREATE INDEX idx_questions_source ON questions(source_name, source_type);
CREATE INDEX idx_questions_embedding ON questions USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_questions_created ON questions(created_at);
```

### 2.2 taxonomy_nodes (Hierarchical Taxonomy)
```sql
CREATE TABLE taxonomy_nodes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_id       UUID REFERENCES taxonomy_nodes(id),
    level           INTEGER NOT NULL,
    name            VARCHAR(255) NOT NULL,
    slug            VARCHAR(255) NOT NULL,
    description     TEXT,
    display_order   INTEGER DEFAULT 0,
    is_active       BOOLEAN DEFAULT TRUE,
    metadata        JSONB DEFAULT '{}',
    version         INTEGER DEFAULT 1,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(parent_id, slug)
);

CREATE INDEX idx_taxonomy_parent ON taxonomy_nodes(parent_id);
CREATE INDEX idx_taxonomy_level ON taxonomy_nodes(level);
CREATE INDEX idx_taxonomy_slug ON taxonomy_nodes(slug);
CREATE INDEX idx_taxonomy_active ON taxonomy_nodes(is_active) WHERE is_active;
```

### 2.3 taxonomy_versions (Version Control)
```sql
CREATE TABLE taxonomy_versions (
    version         INTEGER PRIMARY KEY,
    snapshot        JSONB NOT NULL,
    description     TEXT,
    created_by      VARCHAR(255),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

### 2.4 processing_runs (Batch Tracking)
```sql
CREATE TABLE processing_runs (
    run_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_name      VARCHAR(255),
    source_path     TEXT,
    total_questions INTEGER DEFAULT 0,
    successful      INTEGER DEFAULT 0,
    failed          INTEGER DEFAULT 0,
    needs_review    INTEGER DEFAULT 0,
    config_snapshot JSONB,
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    status          VARCHAR(20),
    total_tokens    BIGINT DEFAULT 0,
    estimated_cost  DECIMAL(10,4)
);

CREATE INDEX idx_runs_status ON processing_runs(status);
CREATE INDEX idx_runs_started ON processing_runs(started_at);
```

### 2.5 question_processing_log (Immutable Event Log)
```sql
CREATE TABLE question_processing_log (
    log_id          BIGSERIAL PRIMARY KEY,
    run_id          UUID REFERENCES processing_runs(run_id),
    question_id     UUID REFERENCES questions(question_id),
    stage           VARCHAR(50),
    status          VARCHAR(20),
    input_snapshot  JSONB,
    output_snapshot JSONB,
    error_message   TEXT,
    duration_ms     INTEGER,
    tokens_used     INTEGER,
    model_used      VARCHAR(100),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_log_run ON question_processing_log(run_id);
CREATE INDEX idx_log_question ON question_processing_log(question_id);
CREATE INDEX idx_log_stage ON question_processing_log(stage);
CREATE INDEX idx_log_created ON question_processing_log(created_at);
```

### 2.6 prompts (Prompt Versioning)
```sql
CREATE TABLE prompts (
    prompt_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(100) NOT NULL,
    version         INTEGER NOT NULL,
    template        TEXT NOT NULL,
    model           VARCHAR(100) NOT NULL,
    parameters      JSONB DEFAULT '{}',
    schema          JSONB,
    description     TEXT,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(name, version)
);

CREATE INDEX idx_prompts_name ON prompts(name, is_active);
```

### 2.7 review_queue (Human Review)
```sql
CREATE TABLE review_queue (
    review_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question_id     UUID REFERENCES questions(question_id),
    reason_codes    TEXT[] NOT NULL,
    priority        INTEGER DEFAULT 0,
    assigned_to     VARCHAR(255),
    status          VARCHAR(20) DEFAULT 'pending',
    resolution      JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    resolved_at     TIMESTAMPTZ
);

CREATE INDEX idx_review_status ON review_queue(status);
CREATE INDEX idx_review_priority ON review_queue(priority DESC);
CREATE INDEX idx_review_question ON review_queue(question_id);
```

### 2.8 evaluation_results (Gold Standard Evaluation)
```sql
CREATE TABLE evaluation_results (
    eval_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_name    VARCHAR(100),
    model_config    JSONB,
    metrics         JSONB NOT NULL,
    details         JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

## 3. V1 Output Format (JSONL) - Before DB Integration

For V1, the engine outputs JSONL files. Schema matches the questions table above.

### Example Output Record
```json
{
  "question_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "content_hash": "sha256...",
  "question_text": "A train travels at 54 km/hr. How long to cross a 300m platform?",
  "options": {"A": "20s", "B": "24s", "C": "28s", "D": "32s"},
  "correct_answer": "B",
  "category_id": "cat-uuid-quantitative",
  "topic_id": "topic-uuid-tsd",
  "subtopic_id": "subtopic-uuid-trains",
  "concepts": ["speed", "distance", "time", "unit_conversion"],
  "question_type": "mcq",
  "difficulty_score": 4.50,
  "difficulty_rating": "medium",
  "difficulty_factors": {"concept_count": 3, "reasoning_complexity": 5, "calculation_complexity": 4, "steps": 3, "ambiguity": 2, "formula_complexity": 3},
  "estimated_time_sec": 90,
  "solution": {
    "steps": [
      "Convert 54 km/hr to m/s: 54 * 5/18 = 15 m/s",
      "Total distance = train length + platform length (train length not given, use platform only)",
      "Time = Distance / Speed = 300 / 15 = 20 seconds"
    ],
    "formulas_used": ["speed_conversion", "time_distance_speed"],
    "calculations": [{"expr": "54 * 5/18", "result": 15}, {"expr": "300 / 15", "result": 20}],
    "final_answer": "20s (Option A)",
    "source": "generated",
    "confidence": 0.92
  },
  "solution_source": "generated",
  "formulas_used": [
    {"name": "km/hr to m/s conversion", "expression": "v * 5/18", "category": "unit_conversion", "reference_id": "FORM-001"},
    {"name": "Time = Distance / Speed", "expression": "t = d/v", "category": "motion", "reference_id": "FORM-002"}
  ],
  "source_name": "Quantitative Aptitude by R.S. Aggarwal",
  "source_type": "pdf",
  "source_identifier": "ISBN-9789352534029",
  "source_page": 142,
  "source_question_id": "Ex-12-Q15",
  "processing_version": "1.0.0",
  "model_used": "gpt-4o",
  "prompt_version": "a1b2c3d4",
  "processing_timestamp": "2026-09-28T10:30:00Z",
  "processing_duration_ms": 12500,
  "token_usage": {"prompt": 1200, "completion": 800, "total": 2000},
  "estimated_cost_usd": 0.005,
  "validation_status": "validated",
  "validation_errors": [],
  "validation_warnings": [],
  "status": "validated",
  "created_at": "2026-09-28T10:30:00Z",
  "updated_at": "2026-09-28T10:30:00Z"
}
```

## 4. Migration Strategy

1. V1: JSONL file output only. No database required.
2. V2: Add PostgreSQL, import JSONL via COPY or batch INSERT.
3. V3: Add pgvector embeddings, build HNSW index.
4. V4: Connect to Deduplication Engine for semantic search.

## 5. Extensibility Notes

- All JSONB fields can evolve without schema migrations
- taxonomy_nodes.metadata stores aliases, keywords for matching
- prompts table enables full prompt versioning and A/B testing
- question_processing_log provides complete replay capability
