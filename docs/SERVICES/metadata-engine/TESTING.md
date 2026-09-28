# Testing Guide: metadata-engine

## Test Organization

```
tests/
|-- conftest.py              # Shared fixtures
|-- unit/                    # Pure logic, no LLM
|   |-- test_models.py       # Pydantic model validation
|   |-- test_normalizer.py   # Text normalization
|   |-- test_difficulty_calculation.py  # Factor weighting
|   |-- test_formula_parsing.py         # Formula ref parsing
|   |-- test_validators.py   # Validation logic
|   |-- test_checkpoint.py   # Checkpoint serialization
|-- integration/             # Full pipeline, mocked LLM
|   |-- test_pipeline.py     # End-to-end flow
|   |-- test_batch_processing.py       # Coordinator
|   |-- test_api.py          # FastAPI endpoints
|   |-- test_cli.py          # Typer commands
|-- ai_evaluation/           # Real LLM calls (costs money!)
|   |-- gold_standard/
|   |   |-- questions.jsonl  # 200 manually labeled
|   |   |-- expected_outputs.jsonl
|   |-- test_classification_accuracy.py
|   |-- test_difficulty_correlation.py
|   |-- test_solution_correctness.py
|   |-- test_formula_extraction.py
|-- failure/                 # Error handling
|   |-- test_malformed_questions.py
|   |-- test_missing_answers.py
|   |-- test_api_timeouts.py
|   |-- test_invalid_json.py
|   |-- test_unsupported_formats.py
|-- regression/              # Prompt/model change detection
    |-- test_prompt_v1_v2.py
    |-- test_model_swap.py
```

## Test Principles

1. **Unit tests:** Fast, deterministic, no external dependencies
2. **Integration tests:** Mock LLM gateway, test orchestration
3. **AI Evaluation:** Real LLM against gold standard, run selectively (costs money)
4. **Failure tests:** Chaos engineering for the pipeline
5. **Regression tests:** Detect behavior changes when prompts/models change

## Running Tests

```bash
# All tests (CI default)
make test

# Specific categories
pytest tests/unit/ -v
pytest tests/integration/ -v
pytest tests/ai_evaluation/ -v   # Requires OPENAI_API_KEY, costs money
pytest tests/failure/ -v
pytest tests/regression/ -v

# With coverage
pytest --cov=src/qme --cov-report=html

# Parallel
pytest -n auto
```

## Writing Tests

### Unit Test Example

```python
# tests/unit/test_difficulty_calculation.py
import pytest
from qme.core.models import DifficultyFactor
from qme.pipeline.stages.difficulty import calculate_difficulty_score

def test_difficulty_weighting():
    factors = [
        DifficultyFactor(name="concept_count", weight=0.2, score=5.0, reasoning=""),
        DifficultyFactor(name="reasoning_complexity", weight=0.3, score=7.0, reasoning=""),
        # ... other factors
    ]
    result = calculate_difficulty_score(factors)
    assert 0 <= result.score <= 10
    assert result.rating in ("easy", "medium", "hard")
```

### Integration Test Example

```python
# tests/integration/test_pipeline.py
import pytest
from unittest.mock import AsyncMock
from qme.pipeline.coordinator import BatchCoordinator

@pytest.mark.asyncio
async def test_full_pipeline(mock_llm_gateway):
    coordinator = BatchCoordinator(llm_gateway=mock_llm_gateway)
    questions = [sample_question()]
    results = await coordinator.process_batch(questions)
    assert len(results.successful) == 1
    assert results.failed == 0
```

### AI Evaluation Test Example

```python
# tests/ai_evaluation/test_classification_accuracy.py
import pytest
from qme.evaluation.metrics import classification_accuracy
from qme.evaluation.gold_standard import load_gold_standard

@pytest.mark.ai_eval
@pytest.mark.asyncio
async def test_classification_accuracy(real_llm_gateway):
    gold = load_gold_standard("classification")
    accuracy = await classification_accuracy(real_llm_gateway, gold)
    assert accuracy > 0.90  # 90% threshold
```

## Gold Standard Dataset

Location: `tests/ai_evaluation/gold_standard/`

- `questions.jsonl`: 200 diverse aptitude questions
- `expected_outputs.jsonl`: Ground truth EnrichedQuestion objects

**Maintenance:**
- Curated by content team
- Version controlled
- Expanded quarterly
- Each entry includes: question, expected classification, difficulty, solution, formulas

## Mocking Strategy

### LLM Gateway Mock

```python
# conftest.py
@pytest.fixture
def mock_llm_gateway():
    gateway = AsyncMock()
    gateway.classify.return_value = ClassificationResult(...)
    gateway.score_difficulty.return_value = DifficultyResult(...)
    gateway.solve.return_value = SolutionResult(...)
    gateway.extract_formulas.return_value = FormulaResult(...)
    gateway.validate.return_value = ValidationResult(...)
    return gateway
```

### Batch Checkpoint Mock

```python
@pytest.fixture
def temp_checkpoint_dir(tmp_path):
    return tmp_path / "checkpoints"
```

## CI/CD Integration

### GitHub Actions (.github/workflows/test.yml)

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: make test

  ai-eval:
    runs-on: ubuntu-latest
    if: github.event_name == 'schedule' || github.ref == 'refs/heads/main'
    env:
      OPENAI_API_KEY: PLACEHOLDER_OPENAI_KEY
    steps:
      - uses: actions/checkout@v4
      - run: pytest tests/ai_evaluation/ -v
```

> Note: `PLACEHOLDER_OPENAI_KEY` refers to the repository secret that stores the OpenAI API key.

## Test Data

### Sample Questions
`data/samples/sample_questions.jsonl` - 100 clean questions for dev testing

### Fixtures
`tests/conftest.py` provides:
- `sample_question()` - Single NormalizedQuestion
- `sample_batch()` - List of 10 questions
- `malformed_question()` - Invalid input
- `mock_llm_gateway()` - Configured mock

## Regression Testing

When prompts or models change:
1. Run `tests/regression/test_prompt_v1_v2.py`
2. Compare outputs on gold standard
3. If metrics degrade: investigate, do not auto-approve
4. Update gold standard only with human review

**Regression gate:** classification accuracy must not drop more than 2 percentage points against the previous baseline.

## Performance Benchmarks

```bash
# Latency benchmark
pytest tests/benchmarks/ -v --benchmark-only

# Target: p95 < 30s per question
# Throughput: > 100 questions/hour sequential
```

## Failure Test Matrix

| Scenario | Expected Behavior |
|----------|-------------------|
| Malformed JSONL line | Skip line, log error, continue batch |
| Missing answer | Mark failed, write to failed.jsonl |
| Missing options (numeric question) | Allowed, validated as numeric |
| Incorrect AI output | Validation layer flags needs_review |
| API timeout | Retry 3x with exponential backoff, then fail question |
| Invalid JSON from LLM | Retry with same prompt, then fail question |
| Unsupported document format | Reject at ingestion with clear error |
| Checkpoint corruption | Detect, back up, restart from last good checkpoint |
| Rate limit (429) | Wait, retry, continue; never drop questions |
