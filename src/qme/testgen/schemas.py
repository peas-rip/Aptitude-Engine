"""Pydantic schemas for the Test & Practice Agent.

Two families:

- *Read models* mirror the upstream bank files (agent-ready questions,
  knowledge bank, blueprint). They are deliberately separate from
  ``core/models.py``, which stays frozen to API_CONTRACTS.
- *Request/output models* define what callers ask for and what the agent
  returns; :class:`GeneratedTest` carries every field the blueprint's
  ``output_fields`` requires (test_id, questions, answer_key, coverage,
  timing).
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Difficulty = Literal["easy", "medium", "hard"]
DIFFICULTY_RANK = {"easy": 0, "medium": 1, "hard": 2}
CHAPTER_SEP = " › "


def qualify_chapter(source: str, chapter: str) -> str:
    """Canonical chapter key: ``"<source.name> › <chapter>"`` (API_CONTRACTS 1.7)."""
    return f"{source}{CHAPTER_SEP}{chapter}"


# ---------------------------------------------------------------------------
# Read models: book_questions_agent_ready.jsonl
# ---------------------------------------------------------------------------


class BankClassification(BaseModel):
    model_config = ConfigDict(extra="ignore")

    chapter: str
    topic: str
    difficulty: Difficulty
    difficulty_basis: str | None = None
    source_label_basis: str | None = None


class BankAgentMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    question_type: str
    skills: list[str] = []
    generation_tags: list[str] = []
    recommended_use: list[str] = []
    estimated_time_seconds: int = Field(ge=0)


class BankFinalAnswer(BaseModel):
    model_config = ConfigDict(extra="ignore")

    option_key: str
    option_text: str | None = None


class BankSolution(BaseModel):
    model_config = ConfigDict(extra="ignore")

    method: str
    steps: list[str]
    final_answer: BankFinalAnswer
    solution_basis: str | None = None


class BankSource(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    type: str
    identifier: str | None = None
    page: int | None = None
    question_id: str | None = None


class BankQuestion(BaseModel):
    """One question exactly as the upstream agent produced it (never altered)."""

    model_config = ConfigDict(extra="ignore")

    question_id: str
    question_text: str = Field(min_length=1)
    options: dict[str, str] = Field(default_factory=dict)
    correct_answer: str = Field(min_length=1)
    answer_text: str | None = None
    classification: BankClassification
    agent_metadata: BankAgentMetadata
    solution: BankSolution
    formula_refs: list[str] = []
    source: BankSource


# ---------------------------------------------------------------------------
# Read models: aptitude_agent_knowledge.json
# ---------------------------------------------------------------------------


class KnowledgeTopic(BaseModel):
    model_config = ConfigDict(extra="ignore")

    question_count: int = Field(ge=0)
    difficulty_counts: dict[str, int] = Field(default_factory=dict)
    formulas: list[str] = []
    short_tricks: list[str] = []
    web_research: list[dict] = []


class KnowledgeChapter(BaseModel):
    model_config = ConfigDict(extra="ignore")

    question_count: int = Field(ge=0)
    topics: dict[str, KnowledgeTopic] = Field(default_factory=dict)
    chapter_formula_summary: list[str] = []


class KnowledgeBank(BaseModel):
    model_config = ConfigDict(extra="ignore")

    schema_version: float | str
    purpose: str | None = None
    provenance: dict = Field(default_factory=dict)
    chapters: dict[str, KnowledgeChapter] = Field(default_factory=dict)
    web_sources: list[str] | list[dict] = []


# ---------------------------------------------------------------------------
# Read models: aptitude_test_blueprint.json
# ---------------------------------------------------------------------------


class TestGenerationContract(BaseModel):
    model_config = ConfigDict(extra="ignore")

    required_filters: list[str]
    optional_filters: list[str]
    selection_rules: list[str]
    output_fields: list[str]


class Blueprint(BaseModel):
    model_config = ConfigDict(extra="ignore")

    schema_version: float | str
    question_bank: str
    knowledge_bank: str
    test_generation_contract: TestGenerationContract
    buckets: dict[str, dict[str, dict[str, int]]] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------


class Selection(BaseModel):
    """One bucket query: keep every provided filter, take ``count`` questions.

    ``chapter``/``source`` are the legacy single-value filters; ``chapters``
    is the friendly-shape scope (qualified chapter keys, union pool).
    """

    count: int = Field(ge=1)
    source: str | None = None
    chapter: str | None = None
    chapters: list[str] = []
    topic: str | None = None
    difficulty: Difficulty | None = None
    question_type: str | None = None
    skills: list[str] = []
    page_min: int | None = Field(default=None, ge=1)
    page_max: int | None = Field(default=None, ge=1)

    def filter_summary(self) -> dict:
        return {
            k: v
            for k, v in {
                "source": self.source,
                "chapter": self.chapter,
                "chapters": self.chapters or None,
                "topic": self.topic,
                "difficulty": self.difficulty,
                "question_type": self.question_type,
                "skills": self.skills or None,
                "page_min": self.page_min,
                "page_max": self.page_max,
            }.items()
            if v is not None
        }


class TestRequest(BaseModel):
    """Legacy shape: explicit bucket selections (v1 semantics, kept)."""

    __test__ = False  # not a pytest test class

    test_id: str | None = None
    title: str | None = None
    seed: int | None = None
    selections: list[Selection] = Field(min_length=1)
    include_solutions: bool = True


class DifficultySpec(BaseModel):
    """Friendly-shape difficulty choice: one level or a mixed composition."""

    mode: Literal["single", "mixed"]
    value: Difficulty | None = None
    counts: dict[str, int] | None = None


class TestSpec(BaseModel):
    """Friendly shape: sources x chapters x difficulty x count (API_CONTRACTS 1.7).

    Rule-table validation (multiple of 5, minimums, mixed sums, feasibility)
    happens in ``qme.testgen.spec`` so violations surface as ``INVALID_INPUT``
    with machine-readable ``details`` rather than schema errors.
    """

    __test__ = False  # not a pytest test class

    test_id: str | None = None
    title: str | None = None
    seed: int | None = None
    sources: list[str] | None = None
    chapters: list[str] | None = None
    difficulty: DifficultySpec
    count: int


class SubmitRequest(BaseModel):
    """End-test submission: exact test body + answers (API_CONTRACTS 1.7).

    ``test_id`` is the id echoed by ``POST /tests`` — carried through to the
    result so reports stay traceable even when the body itself has no
    ``test_id`` (the server generates one per creation).
    """

    test_id: str | None = None
    request: dict[str, Any]
    answers: dict[str, str] = Field(default_factory=dict)
    elapsed_seconds: int | None = Field(default=None, ge=0)


class PracticeRequest(BaseModel):
    practice_id: str | None = None
    title: str | None = None
    seed: int | None = None
    count: int = Field(default=10, ge=1)
    page: int = Field(default=1, ge=1)
    source: str | None = None
    chapter: str | None = None
    topic: str | None = None
    difficulty: Difficulty | None = None
    mode: Literal["progressive", "mixed"] = "progressive"
    include_knowledge: bool = True


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------


class Shortage(BaseModel):
    selection_index: int
    requested: int
    provided: int
    shortfall: int
    filters: dict


class Coverage(BaseModel):
    total: int
    by_chapter: dict[str, int] = Field(default_factory=dict)
    by_topic: dict[str, int] = Field(default_factory=dict)
    by_difficulty: dict[str, int] = Field(default_factory=dict)
    by_source: dict[str, int] = Field(default_factory=dict)


class Timing(BaseModel):
    estimated_total_sec: int = Field(ge=0)
    avg_per_question_sec: float = Field(ge=0)
    min_sec: int = Field(ge=0)
    max_sec: int = Field(ge=0)


class AnswerKeyEntry(BaseModel):
    question_id: str
    correct_answer: str
    answer_text: str | None = None
    solution_steps: list[str] = []


class GeneratedTest(BaseModel):
    """Blueprint-conformant test document (output_fields all present)."""

    test_id: str
    title: str | None = None
    seed: int | None = None
    generated_at: str
    contract_source: dict
    selections_applied: list[Selection]
    selection_rules_applied: list[str]
    questions: list[BankQuestion]
    answer_key: list[AnswerKeyEntry]
    coverage: Coverage
    timing: Timing
    shortages: list[Shortage] = []
    notes: dict = Field(default_factory=dict)


class Pagination(BaseModel):
    page: int = Field(ge=1)
    count: int = Field(ge=1)
    total: int = Field(ge=0)
    total_pages: int = Field(ge=0)
    has_more: bool


class PracticeSet(BaseModel):
    practice_id: str
    title: str | None = None
    seed: int | None = None
    generated_at: str
    mode: Literal["progressive", "mixed"]
    filters_applied: dict
    questions: list[BankQuestion]
    coverage: Coverage
    timing: Timing
    pagination: Pagination | None = None
    shortages: list[Shortage] = []
    topic_knowledge: dict[str, dict] = Field(default_factory=dict)
    chapter_formula_summary: list[str] = []


class ScoreBreakup(BaseModel):
    correct: int = Field(ge=0)
    total: int = Field(ge=0)
    percent: float = Field(ge=0, le=100)


class ResultLine(BaseModel):
    question_id: str
    your_answer: str | None = None
    correct_answer: str
    answer_text: str | None = None
    is_correct: bool
    solution_steps: list[str] = []
    difficulty: Difficulty
    chapter: str
    source: str


class TestResult(BaseModel):
    """Scored submission report (POST /api/v1/tests/submit)."""

    __test__ = False  # not a pytest test class

    test_id: str
    score: ScoreBreakup
    by_difficulty: dict[str, ScoreBreakup] = Field(default_factory=dict)
    by_chapter: dict[str, ScoreBreakup] = Field(default_factory=dict)
    by_source: dict[str, ScoreBreakup] = Field(default_factory=dict)
    elapsed_seconds: int | None = None
    results: list[ResultLine] = []


class KnowledgeTerms(BaseModel):
    formulas: list[str] = []
    short_tricks: list[str] = []


class ChapterKnowledge(BaseModel):
    """Source-less knowledge for one chapter (GET /chapters/{key}/knowledge)."""

    chapter: str
    topic: str | None = None
    formula_summary: list[str] = []
    topics: dict[str, KnowledgeTerms] = Field(default_factory=dict)


class ChapterInfo(BaseModel):
    key: str
    label: str
    question_count: int = Field(ge=0)
    difficulty_counts: dict[str, int] = Field(default_factory=dict)


class SourceInfo(BaseModel):
    name: str
    question_count: int = Field(ge=0)
    chapters: list[ChapterInfo] = []


class KnowledgeCoverage(BaseModel):
    covered_chapters: list[str] = []
    missing_chapters: list[str] = []
