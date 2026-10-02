# Test & Practice Agent

## Purpose

Deterministically assembles practice sets and full-length tests from the
external question agent's output bank. No LLM calls: every question, answer
and solution step comes verbatim from the bank; the agent only selects,
orders, validates and renders.

## Responsibilities

- Load and cross-validate the three upstream files (blueprint, question
  bank, knowledge bank); hard-stop with a field-level report on any
  contract mismatch.
- Select questions by blueprint filters (chapter, topic, difficulty,
  question_type, skills, page range) with seeded, reproducible sampling.
- Assemble blueprint-conformant tests: `test_id`, `questions`,
  `answer_key`, `coverage`, `timing`, plus shortages and overlap notes.
- Assemble practice sets (progressive easy→hard or mixed) with topic
  formulas and short tricks.
- Render Markdown for humans; JSON for machines.
- Expose everything through `qme testgen` and `qme practice`.

### Responsibilities this agent DOES NOT have

- It does not generate, rewrite, translate or "improve" questions,
  options, answers or solutions.
- It does not call any LLM, and it does not implement the QME metadata
  pipeline (classification, difficulty, solution engine — those live in
  `src/qme/pipeline/`).
- It does not deduplicate questions beyond per-request unique selection.
- It does not persist to a database; outputs are files only.
- It does not invent quota rules: counts and filters always come from the
  caller, bounded by the blueprint contract.

## Inputs

Required:

- `--blueprint` path to `aptitude_test_blueprint.json` (declares the bank
  filenames, contract rules and bucket counts).
- Sibling files resolvable from the blueprint's directory:
  `book_questions_agent_ready.jsonl`, `aptitude_agent_knowledge.json`.
- `--output` directory.

Optional (test): `--count`, `--chapter`, `--topic`, `--difficulty`
(easy | medium | hard), `--seed`, `--test-id`, `--title`, `--format`
(json | md | both, default both).

Optional (practice): same filters plus `--mode` (progressive | mixed,
default progressive) and `--practice-id`.

Example:

```bash
qme testgen --blueprint data/input/aptitude_test_blueprint.json \
  --output data/output/tests --count 20 --difficulty hard --seed 42
qme practice --blueprint data/input/aptitude_test_blueprint.json \
  --output data/output/practice --topic Percentage --count 10 --seed 7
```

## Outputs

Test JSON (`data/output/<test_id>.json`), all blueprint `output_fields`
present:

```json
{
  "test_id": "T-20261002-140544-5",
  "title": "Smoke Test",
  "generated_at": "2026-10-02T14:05:44+00:00",
  "contract_source": {"blueprint": "aptitude_test_blueprint.json", "...": "..."},
  "selections_applied": [{"count": 5, "difficulty": "hard"}],
  "selection_rules_applied": ["..."],
  "questions": [{"question_id": "p410-14", "...": "verbatim bank record"}],
  "answer_key": [{"question_id": "p410-14", "correct_answer": "D",
                   "answer_text": "20", "solution_steps": ["..."]}],
  "coverage": {"total": 5, "by_chapter": {"...": 3}, "by_topic": {"...": 3},
               "by_difficulty": {"hard": 5}},
  "timing": {"estimated_total_sec": 450, "avg_per_question_sec": 90.0,
             "min_sec": 90, "max_sec": 90},
  "shortages": [],
  "notes": {}
}
```

Practice JSON adds `mode`, `filters_applied`, `topic_knowledge`
(per-topic formulas and short tricks) and `chapter_formula_summary`.

Markdown (`.md`) is a human rendering of the same document: header
coverage/timing, numbered questions grouped by chapter, answer key with
solution steps (tests), collapsible answers (practice), shortage notes.

## Internal Workflow

Receive request (CLI flags)
→ Load blueprint and validate contract (required filters, output fields,
selection rules)
→ Load question bank line-by-line; every record must match the schema
→ Cross-validate: bucket counts vs bank, knowledge coverage vs bank,
unique question_id
→ For each selection: apply filters, raise `SelectionError` on unknown
values or zero matches, seeded-sample up to `count`, record shortages and
overlap exclusions
→ Build coverage (chapter/topic/difficulty counts) and timing
(sum/avg/min/max of `estimated_time_seconds`)
→ Build answer key (correct answer + answer_text + solution steps)
→ Emit JSON + Markdown
→ Return summary (id, totals, shortages)

## Upstream Dependencies

None in the agent sense — the upstream is a *data* producer (the external
question agent, see `docs/AGENT_SUMMARY.md` consumers below). Expected
files and required fields:

- `book_questions_agent_ready.jsonl`: `question_id`, `question_text`,
  `options`, `correct_answer`, `classification{chapter,topic,difficulty}`,
  `agent_metadata{question_type,skills,estimated_time_seconds}`,
  `solution{method,steps,final_answer}`, `source{name,type}`.
- `aptitude_test_blueprint.json`: `question_bank`, `knowledge_bank`,
  `test_generation_contract{required_filters,optional_filters,
  selection_rules,output_fields}`, `buckets`.
- `aptitude_agent_knowledge.json`: `chapters{chapter → topics{topic →
  formulas, short_tricks, ...}}`, `chapter_formula_summary`.

Any mismatch (missing field, bucket drift, missing knowledge topic,
duplicate id, bad required_filters/output_fields) is a hard stop:
`ContractError` listing every violation. Contracts are never repaired
silently.

## Downstream Consumers

- Humans: the Markdown test/practice papers.
- Other agents/tools: the JSON documents (stable field names per the
  blueprint contract: `test_id`, `questions`, `answer_key`, `coverage`,
  `timing`).
- The QME API (future Step 8+ could expose this under `/api/v1/...`);
  not wired yet — CLI only.

## Integration Contract

Input: CLI flags as above (programmatic: `TestRequest` / `PracticeRequest`
Pydantic models).

Output: `GeneratedTest` / `PracticeSet` Pydantic models — round-trip
validated (`Model.validate_json(model_dump_json())`), so consumers may
rely on the field names shown in Outputs.

Agent-to-agent: none today; the bank files are the only contract, and
they are validated on every load.

## APIs

HTTP (FastAPI, API_CONTRACTS §1.7) — stateless JSON, `X-API-Key` required
except on health:

```
GET  /api/v1/health        (open; PaaS health check)
GET  /api/v1/bank/meta     chapters/topics/difficulties/buckets/contract
POST /api/v1/tests         body TestRequest    -> GeneratedTest
POST /api/v1/practice      body PracticeRequest -> PracticeSet
```

Errors follow the §4 envelope (`{error:{code,message,details,request_id}}`):
401 `UNAUTHORIZED`, 422 `VALIDATION_ERROR`/`INVALID_INPUT`, 503
`SERVICE_UNAVAILABLE` (broken bank, full contract report in `details.issues`).
The blueprint path is server config only (`QME_BLUEPRINT_PATH`); the bank is
mtime-cached so regenerated files are picked up without restart; the app
refuses to boot with `ENVIRONMENT=production` and no `QME_API_KEY`.

CLI (Typer, part of the existing `qme` app):

- `qme testgen --blueprint <path> --output <dir> [--count --chapter
  --topic --difficulty --seed --test-id --title --format]`
- `qme practice --blueprint <path> --output <dir> [--count --chapter
  --topic --difficulty --mode --seed --practice-id --title --format]`

Programmatic: `qme.testgen.load_bank`, `generate_test`,
`generate_practice`.

## Storage

Filesystem only. Inputs are read from `data/input/` (gitignored); outputs
written to the directory passed via `--output` (convention:
`data/output/tests/`, `data/output/practice/`, gitignored). No database.

## Error Handling

- `ContractError(TestGenError)` — upstream file violates the contract;
  message lists every issue (capped at 15). Exit code 1, no partial
  output written.
- `SelectionError(TestGenError)` — unknown filter value (message lists
  available chapters/topics/difficulties) or zero matches. Exit code 1.
- Pydantic `ValidationError` on CLI flags (e.g. `--difficulty brutal`) —
  caught and reported as `Error: ...`, exit code 1.
- Shortages are *not* errors: a request larger than the pool returns what
  exists plus a `shortages` record (`requested`, `provided`,
  `shortfall`, `filters`).
- No retries anywhere (no network calls). No silent fallbacks.

## Security Considerations

- No secrets, no network access, no LLM keys involved.
- Input paths are caller-supplied local files; JSON is parsed with the
  standard library and validated by Pydantic (size bounded only by the
  filesystem).
- Output files contain bank content only — no credentials can leak into
  them.

## Usage Instructions

```bash
# 20-question hard test, reproducible
qme testgen --blueprint data/input/aptitude_test_blueprint.json \
  --output data/output/tests --count 20 --difficulty hard --seed 42

# progressive practice set on one topic
qme practice --blueprint data/input/aptitude_test_blueprint.json \
  --output data/output/practice --topic Percentage --count 10 --mode progressive

# in code
from pathlib import Path
from qme.testgen import load_bank, generate_test
from qme.testgen.schemas import Selection, TestRequest

bank = load_bank(Path("data/input/aptitude_test_blueprint.json"))
test = generate_test(bank, TestRequest(seed=1, selections=[Selection(count=10, difficulty="medium")]))
```

If the upstream agent changes the file shape, expect a `ContractError`
with a field report — regenerate the bank or update this agent's read
models deliberately; do not loosen validation.

## Development Notes

- Language: Python 3.11
- Framework: Pydantic v2 (schemas), Typer (CLI) — no new dependencies
- Database: none
- LLM provider: none (deterministic by design)
- Dependencies added: none (reuses `qme.core.exceptions.QMEError`)
- Code: `src/qme/testgen/` (`bank.py`, `selector.py`, `assembler.py`,
  `practice.py`, `render.py`, `schemas.py`, `errors.py`), CLI commands in
  `src/qme/cli.py`
- Tests: `tests/testgen_fixtures.py` (builders), `tests/unit/
  test_testgen_{bank,selector,assembler,practice,render}.py`,
  `tests/integration/test_testgen_{e2e,cli}.py` (e2e skips when
  `data/input/` is absent)
- Created: 2026-10-02
