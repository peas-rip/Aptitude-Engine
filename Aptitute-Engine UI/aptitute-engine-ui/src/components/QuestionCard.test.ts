import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QuestionCard } from "./QuestionCard";
import type { BankQuestion } from "../types/qme";

/**
 * Spec §16.1 (acceptance): "No correct-answer or solution text is present in
 * the runner DOM (automated assertion)". The runner renders QuestionCard with
 * `reveal={false}`, so proving the primitive is safe is most of the claim.
 */
const question: BankQuestion = {
  question_id: "q-average-1",
  question_text: "The average of 2, 4 and 6 is:",
  options: { A: "3", B: "4", C: "5", D: "6" },
  correct_answer: "B",
  answer_text: "4",
  classification: {
    chapter: "Quantitative Aptitude EBook › Average",
    topic: "Average",
    difficulty: "easy",
    difficulty_basis: "heuristic",
    source_label_basis: "source_bank",
  },
  agent_metadata: {
    question_type: "quantitative",
    skills: ["arithmetic"],
    generation_tags: [],
    recommended_use: [],
    estimated_time_seconds: 30,
  },
  solution: {
    method: "Sum / count",
    steps: ["Sum = 2 + 4 + 6 = 12", "Count = 3", "12 / 3 = 4"],
    final_answer: { option_key: "B", option_text: "4" },
    solution_basis: "source_bank",
  },
  formula_refs: [],
  source: {
    name: "Quantitative Aptitude EBook",
    type: "jsonl",
    identifier: null,
    page: null,
    question_id: null,
  },
};

const SOLUTION_TEXT = ["Sum = 2 + 4 + 6 = 12", "Count = 3", "12 / 3 = 4"];

function render(reveal: boolean, value?: string): string {
  return renderToStaticMarkup(
    createElement(QuestionCard, { question, reveal, value }),
  );
}

/** Option keys of the radio inputs that are currently selected. */
function selectedKeys(html: string): string[] {
  return (html.match(/<input[^>]*>/g) ?? [])
    .filter((tag) => /\schecked/.test(tag))
    .map((tag) => (tag.match(/value="([^"]*)"/) ?? [])[1] ?? "?");
}

describe("QuestionCard — answer leakage (spec §16.1)", () => {
  it("runner mode (reveal=false) hides the correct answer and the solution", () => {
    const html = render(false, "A");

    expect(html).toContain("The average of 2, 4 and 6 is:");
    for (const label of ["Correct Answer:", "Answer Text:", "Solution:"]) {
      expect(html).not.toContain(label);
    }
    for (const step of SOLUTION_TEXT) {
      expect(html).not.toContain(step);
    }
    // The solution method must not leak either.
    expect(html).not.toContain(question.solution.method);
  });

  it("renders every option as a selectable radio keyed A-D", () => {
    const html = render(false, "A");
    for (const key of ["A", "B", "C", "D"]) {
      expect(html).toContain(`value="${key}"`);
    }
  });

  /**
   * The input must carry its option key. Without `value`, HTML defaults a
   * radio's `.value` to "on", and every answer would submit as "on".
   */
  it("submits the option key the user actually picked, not the HTML default", () => {
    expect(selectedKeys(render(false, "A"))).toEqual(["A"]);
    expect(selectedKeys(render(false, "C"))).toEqual(["C"]);
    expect(selectedKeys(render(false))).toEqual([]);
    // Guards the literal default that would otherwise be submitted.
    expect(render(false, "A")).not.toContain('value="on"');
  });

  it("practice/review mode (reveal=true) shows answer + solution steps", () => {
    const html = render(true);
    expect(html).toContain("Correct Answer:");
    expect(html).toContain("Solution:");
    for (const step of SOLUTION_TEXT) {
      expect(html).toContain(step);
    }
    // correct_answer + its option text, rendered together.
    expect(html).toContain(`B. ${question.options.B}`);
  });
});

describe("TestRunner — answer leakage wiring", () => {
  const src = readFileSync(
    fileURLToPath(new URL("../pages/TestRunner.tsx", import.meta.url)),
    "utf8",
  );

  it("never reveals answers while the test is running", () => {
    expect(src).toContain("reveal={false}");
    expect(src).not.toContain("reveal={true}");
  });

  it("submits the ORIGINAL stored request body, never a rebuild", () => {
    expect(src).toContain("request: draft.body");
  });
});
