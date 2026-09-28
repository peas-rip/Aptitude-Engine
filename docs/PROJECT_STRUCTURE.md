# Project Structure: Question Metadata Engine

## 1. Repository Layout

```
aptitude-engine/
├── .github/
│   └── workflows/           # CI/CD pipelines
├── docs/
│   ├── PRD.md
│   ├── SYSTEM_ARCHITECTURE.md
│   ├── DATABASE_SCHEMA.md
│   ├── API_CONTRACTS.md
│   ├── PROJECT_STRUCTURE.md
│   ├── FEATURE_SERVICE_MAPPING.md
│   ├── ROADMAP.md
│   ├── IMPLEMENTATION_ORDER.md
│   ├── DEPLOYMENT_ARCHITECTURE.md
│   ├── AI_IMPLEMENTATION_GUIDE.md
│   ├── TECHNOLOGY_DECISIONS.md
│   ├── FEATURES/
│   │   ├── FE-001_QUESTION_EXTRACTION.md
│   │   ├── FE-002_TOPIC_CLASSIFICATION.md
│   │   ├── FE-003_DIFFICULTY_SCORING.md
│   │   ├── FE-004_SOLUTION_ENGINE.md
│   │   ├── FE-005_FORMULA_EXTRACTION.md
│   │   ├── FE-006_VALIDATION_PIPELINE.md
│   │   ├── FE-007_BATCH_PROCESSING.md
│   │   ├── FE-008_SOURCE_TRACKING.md
│   │   ├── FE-009_HUMAN_REVIEW.md
│   │   └── FE-010_OBSERVABILITY.md
│   └── SERVICES/
│       └── metadata-engine/
│           ├── SERVICE_SPEC.md
│           ├── DEVELOPMENT.md
│           ├── TESTING.md
│           └── DEPLOYMENT.md
├── src/
│   └── qme/
│       ├── __init__.py
│       ├── main.py                 # FastAPI app entry point
│       ├── cli.py                  # Typer CLI entry point
│       ├── config/
│       │   ├── __init__.py
│       │   ├── settings.py         # Pydantic settings
│       │   ├── taxonomy.yaml       # Seed taxonomy
│       │   └── prompts/            # Prompt templates by version
│       │       ├── classifier_v1.txt
│       │       ├── difficulty_v1.txt
│       │       ├── solution_v1.txt
│       │       ├── formula_v1.txt
│       │       └── validator_v1.txt
│       ├── core/
│       │   ├── __init__.py
│       │   ├── models.py           # Pydantic models (EnrichedQuestion, etc.)
│       │   ├── protocols.py        # Protocol interfaces
│       │   ├── exceptions.py       # Custom exceptions
│       │   └── constants.py        # Enums, constants
│       ├── ingestion/
│       │   ├── __init__.py
│       │   ├── ingestor.py         # FileIngestor base + format-specific
│       │   ├── parsers/
│       │   │   ├── __init__.py
│       │   │   ├── jsonl_parser.py
│       │   │   ├── csv_parser.py
│       │   │   ├── txt_parser.py
│       │   │   ├── pdf_parser.py
│       │   │   └── docx_parser.py
│       │   ├── normalizer.py
│       │   └── source_tracker.py
│       ├── pipeline/
│       │   ├── __init__.py
│       │   ├── coordinator.py      # BatchCoordinator
│       │   ├── stages/
│       │   │   ├── __init__.py
│       │   │   ├── classifier.py
│       │   │   ├── difficulty.py
│       │   │   ├── solution.py
│       │   │   ├── formula.py
│       │   │   └── validator.py
│       │   └── checkpoint.py
│       ├── llm/
│       │   ├── __init__.py
│       │   ├── gateway.py          # LLMGateway with model routing
│       │   ├── structured_output.py # Schema enforcement
│       │   ├── prompt_manager.py   # Versioned prompt loading
│       │   └── cost_tracker.py
│       ├── validation/
│       │   ├── __init__.py
│       │   ├── schema_validator.py
│       │   ├── answer_validator.py
│       │   ├── calculation_validator.py  # V2: SymPy integration
│       │   ├── consistency_validator.py
│       │   └── confidence_checker.py
│       ├── output/
│       │   ├── __init__.py
│       │   ├── jsonl_writer.py
│       │   ├── metrics_collector.py
│       │   └── review_queue.py
│       ├── api/
│       │   ├── __init__.py
│       │   ├── routes/
│       │   │   ├── __init__.py
│       │   │   ├── questions.py
│       │   │   ├── batches.py
│       │   │   ├── health.py
│       │   │   └── metrics.py
│       │   ├── dependencies.py
│       │   └── middleware.py
│       ├── evaluation/
│       │   ├── __init__.py
│       │   ├── gold_standard.py
│       │   ├── metrics.py
│       │   └── runner.py
│       └── utils/
│           ├── __init__.py
│           ├── hashing.py
│           ├── timing.py
│           └── retry.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── unit/
│   │   ├── test_models.py
│   │   ├── test_normalizer.py
│   │   ├── test_difficulty_calculation.py
│   │   ├── test_formula_parsing.py
│   │   ├── test_validators.py
│   │   └── test_checkpoint.py
│   ├── integration/
│   │   ├── test_pipeline.py
│   │   ├── test_batch_processing.py
│   │   ├── test_api.py
│   │   └── test_cli.py
│   ├── ai_evaluation/
│   │   ├── gold_standard/
│   │   │   ├── questions.jsonl
│   │   │   └── expected_outputs.jsonl
│   │   ├── test_classification_accuracy.py
│   │   ├── test_difficulty_correlation.py
│   │   ├── test_solution_correctness.py
│   │   └── test_formula_extraction.py
│   ├── failure/
│   │   ├── test_malformed_questions.py
│   │   ├── test_missing_answers.py
│   │   ├── test_api_timeouts.py
│   │   ├── test_invalid_json.py
│   │   └── test_unsupported_formats.py
│   └── regression/
│       ├── test_prompt_v1_v2.py
│       └── test_model_swap.py
├── data/
│   ├── taxonomy/
│   │   ├── seed_taxonomy.yaml
│   │   └── versions/
│   ├── samples/
│   │   ├── sample_questions.jsonl
│   │   └── sample_batch.jsonl
│   └── gold_standard/
│       └── evaluation_set.jsonl
├── scripts/
│   ├── download_nltk_data.py
│   ├── seed_taxonomy.py
│   ├── run_evaluation.py
│   └── reprocess_failed.py
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── docker-compose.dev.yml
│   └── docker-compose.prod.yml
├── .env.example
├── .gitignore
├── pyproject.toml
├── README.md
├── LICENSE
└── Makefile
```

## 2. Module Responsibility Matrix

| Module | Responsibility | Owner |
|--------|---------------|-------|
| `config/` | Settings, taxonomy, prompts | Platform |
| `core/models.py` | Canonical data models | Platform |
| `core/protocols.py` | Module interfaces | Platform |
| `ingestion/` | File parsing, normalization | Data Engineering |
| `pipeline/stages/` | AI processing modules | ML Engineering |
| `llm/` | LLM gateway, prompts, costs | ML Engineering |
| `validation/` | Multi-layer validation | ML + Platform |
| `output/` | JSONL, metrics, review queue | Platform |
| `api/` | FastAPI routes | Platform |
| `evaluation/` | Gold standard testing | ML Engineering |

## 3. Shared Modules

- `core/models.py` - Single source of truth for all data structures
- `core/protocols.py` - Contracts between pipeline stages
- `core/constants.py` - Enums: QuestionType, DifficultyRating, ValidationStatus, etc.
- `utils/` - Pure functions, no external dependencies

## 4. Configuration Structure

```
config/
├── settings.py          # All env-configurable settings
├── taxonomy.yaml        # Hierarchical taxonomy (versioned)
└── prompts/
    ├── classifier_v1.txt
    ├── difficulty_v1.txt
    ├── solution_v1.txt
    ├── formula_v1.txt
    └── validator_v1.txt
```

## 5. Prompt Versioning Convention

- File naming: `{module}_v{version}.txt`
- Version stored in `prompts` table and `prompt_version` field
- Hash of template stored with each processed question
- Enables exact reproduction of any historical run

## 6. Test Organization

| Test Type | Location | Purpose |
|-----------|----------|---------|
| Unit | `tests/unit/` | Pure logic, no LLM calls |
| Integration | `tests/integration/` | Full pipeline, mocked LLM |
| AI Evaluation | `tests/ai_evaluation/` | Accuracy against gold standard |
| Failure | `tests/failure/` | Error handling, edge cases |
| Regression | `tests/regression/` | Prompt/model change detection |

## 7. Data Directories

| Directory | Purpose | Git Tracked |
|-----------|---------|-------------|
| `data/taxonomy/` | Seed taxonomy + versions | Yes |
| `data/samples/` | Example inputs for testing | Yes |
| `data/gold_standard/` | Manually labeled evaluation set | Yes (small) |
| `data/output/` | Runtime outputs | No (.gitignore) |
| `data/checkpoints/` | Batch checkpoints | No (.gitignore) |

## 8. Docker Structure

```
docker/
├── Dockerfile              # Multi-stage: builder -> runtime
├── docker-compose.yml      # Local development (API + worker)
├── docker-compose.dev.yml  # Dev overrides (volumes, debug)
└── docker-compose.prod.yml # Production (replicas, resources)
```

## 9. Key Files Description

| File | Purpose |
|------|---------|
| `pyproject.toml` | Dependencies, build config, tool config (ruff, mypy, pytest) |
| `Makefile` | Common commands: test, lint, build, run, eval |
| `.env.example` | Template for environment variables |
| `src/qme/main.py` | FastAPI app factory, lifespan events |
| `src/qme/cli.py` | Typer CLI with all commands |
| `src/qme/pipeline/coordinator.py` | Batch orchestration, checkpointing |
| `src/qme/llm/gateway.py` | Model routing, structured output, retries |
