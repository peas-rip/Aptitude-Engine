"""Builders for Test & Practice Agent tests.

Not collected by pytest (filename lacks the ``test_`` prefix).
"""

import json
from pathlib import Path

from qme.testgen.schemas import Blueprint, Selection, TestRequest

CONTRACT_DEFAULT = {
    "required_filters": ["chapter", "topic", "difficulty"],
    "optional_filters": ["question_type", "skills", "source.page"],
    "selection_rules": [
        "Return unique question_id values.",
        "Respect requested chapter/topic/difficulty quotas.",
        "Report shortages instead of silently dropping requirements.",
        "Do not alter question_text, options or correct_answer.",
        "Use the knowledge bank only when explicitly requested.",
    ],
    "output_fields": ["test_id", "questions", "answer_key", "coverage", "timing"],
}


def make_question(
    qid: str,
    chapter: str = "Percentage",
    topic: str = "Successive Percentages",
    difficulty: str = "easy",
    page: int = 10,
    skills: list[str] | None = None,
    question_type: str = "mcq",
    seconds: int = 30,
    source: str = "book.pdf",
) -> dict:
    return {
        "question_id": qid,
        "question_text": f"Question {qid}?",
        "options": {"A": "1", "B": "2", "C": "3", "D": "4"},
        "correct_answer": "A",
        "answer_text": "1",
        "classification": {
            "chapter": chapter,
            "topic": topic,
            "difficulty": difficulty,
        },
        "agent_metadata": {
            "question_type": question_type,
            "skills": skills or ["arithmetic"],
            "generation_tags": [],
            "recommended_use": [],
            "estimated_time_seconds": seconds,
        },
        "solution": {
            "method": "Test method",
            "steps": ["step one", "step two"],
            "final_answer": {"option_key": "A", "option_text": "1"},
            "solution_basis": "source_answer_key_plus_topic_method",
        },
        "formula_refs": [],
        "source": {"name": source, "type": "pdf", "page": page, "question_id": qid},
    }


def default_questions() -> list[dict]:
    return [
        make_question("q1", difficulty="easy"),
        make_question("q2", difficulty="easy"),
        make_question("q3", difficulty="medium"),
        make_question("q4", difficulty="medium", page=20, skills=["algebra"], question_type="numeric"),
        make_question("q5", difficulty="hard", chapter="Time & Work", topic="Work Rate"),
        make_question("q6", difficulty="easy", chapter="Time & Work", topic="Work Rate", page=30),
    ]


def big_questions() -> list[dict]:
    """30 questions (15 easy / 10 medium / 5 hard) — satisfies the friendly
    rule table (minimum 10, all-chapters minimum 30, feasibility)."""
    questions: list[dict] = []
    for i in range(15):
        questions.append(make_question(f"e{i:02d}", difficulty="easy"))
    for i in range(10):
        questions.append(
            make_question(f"m{i:02d}", difficulty="medium", page=15 + i)
        )
    for i in range(5):
        questions.append(
            make_question(
                f"h{i:02d}",
                difficulty="hard",
                chapter="Time & Work",
                topic="Work Rate",
                page=25 + i,
            )
        )
    return questions


def _buckets(questions: list[dict]) -> dict:
    buckets: dict = {}
    for q in questions:
        c = q["classification"]
        buckets.setdefault(c["chapter"], {}).setdefault(c["topic"], {}).setdefault(
            c["difficulty"], 0
        )
        buckets[c["chapter"]][c["topic"]][c["difficulty"]] += 1
    return buckets


def _knowledge(questions: list[dict]) -> dict:
    chapters: dict = {}
    for q in questions:
        c = q["classification"]
        chapter = chapters.setdefault(
            c["chapter"],
            {"question_count": 0, "topics": {}, "chapter_formula_summary": []},
        )
        chapter["question_count"] += 1
        topic = chapter["topics"].setdefault(
            c["topic"],
            {"question_count": 0, "difficulty_counts": {}, "formulas": [], "short_tricks": []},
        )
        topic["question_count"] += 1
        d = c["difficulty"]
        topic["difficulty_counts"][d] = topic["difficulty_counts"].get(d, 0) + 1
        topic["formulas"] = [f"{c['topic']} formula"]
        topic["short_tricks"] = [f"{c['topic']} trick"]
        chapter["chapter_formula_summary"] = [f"{c['chapter']} summary"]
    return {
        "schema_version": "1.0",
        "purpose": "test fixture",
        "provenance": {"note": "fixture"},
        "chapters": chapters,
        "web_sources": ["https://example.com"],
    }


def write_bank(
    tmp_path: Path,
    questions: list[dict] | None = None,
    contract_overrides: dict | None = None,
    buckets_override: dict | None = None,
    knowledge_override: dict | None = None,
    duplicate_ids: bool = False,
) -> Path:
    questions = questions if questions is not None else default_questions()
    bank_lines = [json.dumps(q) for q in questions]
    if duplicate_ids and questions:
        bank_lines.append(json.dumps(questions[0]))
    (tmp_path / "bank.jsonl").write_text("\n".join(bank_lines), encoding="utf-8")

    knowledge = knowledge_override if knowledge_override is not None else _knowledge(questions)
    (tmp_path / "knowledge.json").write_text(json.dumps(knowledge), encoding="utf-8")

    contract = dict(CONTRACT_DEFAULT)
    if contract_overrides:
        contract.update(contract_overrides)
    blueprint = {
        "schema_version": "1.0",
        "question_bank": "bank.jsonl",
        "knowledge_bank": "knowledge.json",
        "test_generation_contract": contract,
        "buckets": buckets_override if buckets_override is not None else _buckets(questions),
    }
    blueprint_path = tmp_path / "blueprint.json"
    blueprint_path.write_text(json.dumps(blueprint), encoding="utf-8")
    return blueprint_path


def sample_selection(**kwargs) -> Selection:
    defaults = {"count": 2}
    defaults.update(kwargs)
    return Selection(**defaults)


def sample_request(**kwargs) -> TestRequest:
    defaults = {"seed": 42, "selections": [sample_selection()]}
    defaults.update(kwargs)
    return TestRequest(**defaults)


def blueprint_model() -> Blueprint:
    return Blueprint.model_validate(
        {
            "schema_version": "1.0",
            "question_bank": "bank.jsonl",
            "knowledge_bank": "knowledge.json",
            "test_generation_contract": CONTRACT_DEFAULT,
            "buckets": {},
        }
    )
