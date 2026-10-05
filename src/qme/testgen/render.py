"""Markdown renderers for generated tests and practice sets."""

from qme.testgen.schemas import GeneratedTest, PracticeSet


def _coverage_line(c) -> str:
    parts = [f"{k}={v}" for k, v in sorted(c.by_chapter.items())]
    return f"total {c.total} | chapters: {', '.join(parts) if parts else '-'}"


def test_to_markdown(test: GeneratedTest) -> str:
    lines = [
        f"# {test.title or test.test_id}",
        "",
        f"- **test_id:** {test.test_id}",
        f"- **generated_at:** {test.generated_at}",
        f"- **coverage:** {_coverage_line(test.coverage)}",
        f"- **by difficulty:** {', '.join(f'{k}={v}' for k, v in sorted(test.coverage.by_difficulty.items()))}",
        f"- **timing:** {test.timing.estimated_total_sec}s total "
        f"(avg {test.timing.avg_per_question_sec}s/question)",
        f"- **bank:** {test.contract_source.get('question_bank', '?')}",
        "",
        "## Questions",
        "",
    ]
    for i, q in enumerate(test.questions, 1):
        c = q.classification
        lines += [
            f"### {i}. ({c.chapter} > {c.topic} | {c.difficulty})",
            "",
            q.question_text,
            "",
        ]
        lines += [f"- **{k}.** {v}" for k, v in q.options.items()]
        lines.append("")

    lines += ["## Answer key", ""]
    for i, (q, key) in enumerate(zip(test.questions, test.answer_key, strict=True), 1):
        answer_label = q.options.get(key.correct_answer, "")
        lines.append(
            f"{i}. **{key.correct_answer}** {answer_label}"
            + (f" — {key.answer_text}" if key.answer_text else "")
        )
        if key.solution_steps:
            lines.append("   - " + "\n   - ".join(key.solution_steps))
    lines.append("")

    if test.shortages:
        lines += ["## Shortages", ""]
        for s in test.shortages:
            lines.append(
                f"- selection #{s.selection_index}: requested {s.requested}, "
                f"provided {s.provided} (short {s.shortfall}) filters={s.filters}"
            )
        lines.append("")

    if test.notes:
        lines += ["## Notes", "", f"```json\n{test.notes}\n```", ""]

    return "\n".join(lines)


def practice_to_markdown(practice: PracticeSet) -> str:
    lines = [
        f"# {practice.title or practice.practice_id}",
        "",
        f"- **practice_id:** {practice.practice_id}",
        f"- **mode:** {practice.mode}",
        f"- **seed:** {practice.seed}",
        f"- **generated_at:** {practice.generated_at}",
        f"- **coverage:** {_coverage_line(practice.coverage)}",
        f"- **timing:** {practice.timing.estimated_total_sec}s total",
    ]
    if practice.pagination:
        p = practice.pagination
        lines.append(
            f"- **page:** {p.page}/{p.total_pages} (pool {p.total}, "
            f"page size {p.count}, has_more={p.has_more})"
        )
    lines.append("")
    if practice.chapter_formula_summary:
        lines += ["## Chapter formula summary", ""]
        lines += [f"- {f}" for f in practice.chapter_formula_summary]
        lines.append("")

    if practice.topic_knowledge:
        lines += ["## Formulas & tricks", ""]
        for topic, entry in practice.topic_knowledge.items():
            lines.append(f"**{topic}**")
            lines += [f"- formula: {f}" for f in entry.get("formulas", [])]
            lines += [f"- trick: {t}" for t in entry.get("short_tricks", [])]
            lines.append("")

    lines += ["## Questions", ""]
    for i, q in enumerate(practice.questions, 1):
        c = q.classification
        lines += [
            f"### {i}. ({c.difficulty}) {q.question_text}",
            "",
        ]
        lines += [f"- **{k}.** {v}" for k, v in q.options.items()]
        lines += [
            "",
            f"<details><summary>Answer: {q.correct_answer}"
            + (f" — {q.answer_text}" if q.answer_text else "")
            + "</summary>",
            "",
        ]
        lines += [f"- {s}" for s in q.solution.steps]
        lines += ["", "</details>", ""]

    if practice.shortages:
        s = practice.shortages[0]
        lines += [
            "> Note: bank supplied "
            f"{s.provided}/{s.requested} requested questions (short {s.shortfall}).",
            "",
        ]

    return "\n".join(lines)
