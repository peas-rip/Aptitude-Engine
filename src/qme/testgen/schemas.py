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

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Difficulty = Literal["easy", "medium", "hard"]
DIFFICULTY_RANK = {"easy": 0, "medium": 1, "hard": 2}


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
    """One bucket query: keep every provided filter, take ``count`` questions."""

    count: int = Field(ge=1)
    chapter: str | None = None
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
                "chapter": self.chapter,
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
    test_id: str | None = None
    title: str | None = None
    seed: int | None = None
    selections: list[Selection] = Field(min_length=1)
    include_solutions: bool = True


class PracticeRequest(BaseModel):
    practice_id: str | None = None
    title: str | None = None
    seed: int | None = None
    count: int = Field(default=10, ge=1)
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


class PracticeSet(BaseModel):
    practice_id: str
    title: str | None = None
    generated_at: str
    mode: Literal["progressive", "mixed"]
    filters_applied: dict
    questions: list[BankQuestion]
    coverage: Coverage
    timing: Timing
    shortages: list[Shortage] = []
    topic_knowledge: dict[str, dict] = Field(default_factory=dict)
    chapter_formula_summary: list[str] = []
