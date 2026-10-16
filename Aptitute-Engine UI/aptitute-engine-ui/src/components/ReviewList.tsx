import type { BankQuestion, GeneratedTest, ResultLine, TestResult } from "../types/qme";
import { QuestionCard } from "./QuestionCard";

interface ReviewListProps {
  result: TestResult;
  /**
   * The test the result was scored against. `TestResult.results[]` carries only
   * ids + answers, so without this we cannot render real question text/options.
   * Pass it whenever the creating test is still stored (spec §8.4).
   */
  test?: GeneratedTest;
}

/**
 * Legacy fallback for results stored before the test was persisted alongside
 * the score: reconstruct a minimal BankQuestion from the result line. Question
 * text and options are genuinely unavailable here, so they stay empty rather
 * than being invented.
 */
function fallbackQuestion(line: ResultLine): BankQuestion {
  return {
    question_id: line.question_id,
    question_text: `Question ${line.question_id}`,
    options: {},
    correct_answer: line.correct_answer,
    answer_text: line.answer_text,
    classification: {
      chapter: line.chapter,
      topic: "",
      difficulty: line.difficulty,
      difficulty_basis: null,
      source_label_basis: null,
    },
    agent_metadata: {
      question_type: "",
      skills: [],
      generation_tags: [],
      recommended_use: [],
      estimated_time_seconds: 0,
    },
    solution: {
      method: "",
      steps: line.solution_steps,
      final_answer: {
        option_key: line.correct_answer,
        option_text: line.answer_text,
      },
      solution_basis: null,
    },
    formula_refs: [],
    source: {
      name: line.source,
      type: "",
      identifier: null,
      page: null,
      question_id: null,
    },
  };
}

/** Colour AND icon/text — never colour alone (spec §16.1). */
function ReviewHeader({ line }: { line: ResultLine }) {
  const correct = line.is_correct;
  return (
    <div className="mb-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
      <span
        className={
          correct
            ? "inline-flex items-center font-medium text-green-700"
            : "inline-flex items-center font-medium text-red-700"
        }
      >
        {correct ? "✓ Correct" : "✗ Incorrect"}
      </span>
      <span className="text-gray-600">
        Your answer:{" "}
        <span className="font-medium text-gray-900">{line.your_answer ?? "not answered"}</span>
      </span>
      <span className="text-gray-600">
        Correct:{" "}
        <span className="font-medium text-gray-900">
          {line.correct_answer}
          {line.answer_text ? ` (${line.answer_text})` : ""}
        </span>
      </span>
      <span className="text-gray-500">({line.difficulty})</span>
    </div>
  );
}

export function ReviewList({ result, test }: ReviewListProps) {
  const byId = new Map<string, BankQuestion>(
    (test?.questions ?? []).map((q) => [q.question_id, q]),
  );

  return (
    <div className="space-y-4">
      {result.results.map((line) => (
        // Default collapsed; incorrect rows open (spec §8.4).
        <details key={line.question_id} open={!line.is_correct} className="border-t pt-4">
          <summary className="cursor-pointer select-none">
            <ReviewHeader line={line} />
          </summary>
          <div className="mt-2">
            <QuestionCard question={byId.get(line.question_id) ?? fallbackQuestion(line)} reveal />
          </div>
        </details>
      ))}
    </div>
  );
}
