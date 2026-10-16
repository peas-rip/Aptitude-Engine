import type { BankQuestion } from "../types/qme";

interface QuestionCardProps {
  question: BankQuestion;
  /** If true, show correct answer and solution; if true, value and onChange are ignored */
  reveal?: boolean;
  /** Selected option key (if not revealing) */
  value?: string;
  /** Called when option changes (only when not revealing) */
  onChange?: (optionKey: string) => void;
  disabled?: boolean;
}

export function QuestionCard({
  question,
  reveal = false,
  value,
  onChange,
  disabled = false,
}: QuestionCardProps) {
  const options = Object.entries(question.options).map(([key, text]) => ({
    key,
    text,
  }));

  return (
    <div className="mb-6 p-4 bg-white rounded-lg shadow">
      <div className="mb-2 text-lg font-medium text-gray-900">
        {question.question_text}
      </div>
      {reveal ? (
        <>
          <div className="mb-2">
            <span className="font-medium text-gray-700">Correct Answer:</span>
            <span className="ml-2 text-indigo-600">
              {question.correct_answer}. {question.options[question.correct_answer] ?? ""}
            </span>
          </div>
          {question.answer_text && (
            <div className="mb-2">
              <span className="font-medium text-gray-700">Answer Text:</span>
              <span className="ml-2 text-gray-600">{question.answer_text}</span>
            </div>
          )}
          <div className="mb-2">
            <span className="font-medium text-gray-700">Solution:</span>
            <ol className="list-decimal pl-5 space-y-1 text-sm text-gray-700">
              {question.solution.steps.map((step, idx) => (
                <li key={idx}>{step}</li>
              ))}
            </ol>
          </div>
        </>
      ) : (
        <div className="space-y-3">
          {options.map(({ key, text }) => (
            <label key={key} className="flex items-center space-x-3">
              <input
                type="radio"
                name={`question-${question.question_id}`}
                value={key}
                checked={value === key}
                onChange={(e) => {
                  if (e.target.value) onChange?.(e.target.value);
                }}
                disabled={disabled}
                className="h-4 w-4 text-indigo-600"
              />
              <span className="text-sm text-gray-700">{text}</span>
            </label>
          ))}
        </div>
      )}
    </div>
  );
}