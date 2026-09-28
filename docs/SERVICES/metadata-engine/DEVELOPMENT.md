# Development Guide: metadata-engine

## Local Development Setup

### Prerequisites
- Python 3.11+
- Docker & Docker Compose
- OpenAI API key
- Git

### Quick Start
\\\ash
# Clone and setup
git clone <repo>
cd aptitude-engine

# Configure environment
cp .env.example .env
# Edit .env with your OPENAI_API_KEY

# Start development stack
make dev
# Or manually:
docker compose -f docker/docker-compose.dev.yml up -d

# API available at http://localhost:8000
# Docs at http://localhost:8000/docs
\\\

### Running Without Docker
\\\ash
# Create venv
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Run API
make run-api
# Or: uvicorn qme.main:app --reload --port 8000

# Run CLI
qme --help
\\\

## Project Structure (Key Directories)
\\\
src/qme/
├── config/          # Settings, taxonomy, prompts
├── core/            # Models, protocols, constants
├── ingestion/       # File parsing, normalization
├── pipeline/        # AI stages, coordinator, checkpoint
├── llm/             # Gateway, prompts, cost tracking
├── validation/      # 7-layer validation
├── output/          # JSONL, metrics, review queue
├── api/             # FastAPI routes
├── evaluation/      # Gold standard testing
└── utils/           # Pure utilities
\\\

## Adding a New Pipeline Stage

1. Define Protocol in `core/protocols.py`
2. Create Pydantic models in `core/models.py`
3. Add prompt template in `config/prompts/{stage}_v1.txt`
4. Implement stage in `pipeline/stages/{stage}.py`
5. Register in `pipeline/coordinator.py`
6. Add unit tests in \	ests/unit/\
7. Add integration test in \	ests/integration/\
8. Add gold standard eval in \	ests/ai_evaluation/\

## Configuration
All settings in `config/settings.py` (Pydantic Settings).
Environment variables override defaults.
Key settings:
- `OPENAI_API_KEY` - Required
- `MODEL_CLASSIFIER` - Default: gpt-4o-mini
- `MODEL_SOLUTION` - Default: gpt-4o
- `CHECKPOINT_INTERVAL` - Default: 10
- `CONFIDENCE_THRESHOLDS` - Per-stage thresholds

## Prompt Management
- Templates in `config/prompts/{name}_v{version}.txt`
- Loaded via `PromptManager` (caches, versions)
- Hash stored with every processed question
- To update: create new version file, update default in settings

## Taxonomy Management
- Seed taxonomy: `data/taxonomy/seed_taxonomy.yaml`
- Loaded at startup, versioned in DB
- Hot-reload: POST /api/v1/admin/taxonomy/reload (admin only)
- Structure: category -> topic -> subtopic with slugs

## Running Tests
\\\ash
# All tests
make test

# Unit only
pytest tests/unit/ -v

# Integration (requires API running)
pytest tests/integration/ -v

# AI Evaluation (costs money!)
pytest tests/ai_evaluation/ -v

# Failure tests
pytest tests/failure/ -v

# Regression tests
pytest tests/regression/ -v
\\\

## Code Quality
\\\ash
make lint      # Ruff + MyPy
make format    # Ruff format
make typecheck # MyPy only
\\\

## Debugging Tips
- Set `LOG_LEVEL=DEBUG` for verbose logs
- Check \/data/checkpoints/\ for batch progress
- Use `qme process --input file --output dir --checkpoint-dir .checkpoints`
- Inspect failed.jsonl for error details
- Correlation IDs link logs across stages

## Common Tasks

### Process a Batch File
\\\ash
# Via CLI
qme process --input data/samples/batch.jsonl --output data/output --checkpoint-dir data/checkpoints

# Via API
curl -X POST http://localhost:8000/api/v1/batches -F file=@batch.jsonl
curl http://localhost:8000/api/v1/batches/{id}/results > output.jsonl
\\\

### Run Evaluation
\\\ash
python scripts/run_evaluation.py --gold tests/ai_evaluation/gold_standard/questions.jsonl --pred data/output/output.jsonl
\\\

### Add Taxonomy Entry
1. Edit `data/taxonomy/seed_taxonomy.yaml`
2. Increment version in \	axonomy_versions\ table
3. Reload via API or restart service

### Update Prompt
1. Copy `config/prompts/classifier_v1.txt` to `classifier_v2.txt`
2. Modify template
3. Update `DEFAULT_PROMPT_VERSIONS` in settings
4. Deploy - old questions retain v1 hash
