import type { ChangeEvent } from "react";
import type { Difficulty, DifficultySpec } from "../types/qme";

interface DifficultyPickerProps {
  value: DifficultySpec;
  onChange: (value: DifficultySpec) => void;
  error?: boolean;
  errorMessage?: string;
  disabled?: boolean;
}

const DIFFS: Difficulty[] = ["easy", "medium", "hard"];

/**
 * Fully controlled: every change is reported through `onChange` so the parent
 * always builds the request from what is on screen. (An internal copy that was
 * never flushed would silently submit the initial difficulty.)
 */
export function DifficultyPicker({
  value,
  onChange,
  error = false,
  errorMessage,
  disabled = false,
}: DifficultyPickerProps) {
  const handleModeChange = (e: ChangeEvent<HTMLInputElement>) => {
    const mode = e.target.value as "single" | "mixed";
    onChange(
      mode === "single"
        ? { mode, value: value.value ?? "medium" }
        : { mode, counts: { easy: 0, medium: 0, hard: 0 } },
    );
  };

  const handleValueChange = (e: ChangeEvent<HTMLSelectElement>) => {
    onChange({ mode: "single", value: e.target.value as Difficulty });
  };

  const handleCountChange = (diff: Difficulty, e: ChangeEvent<HTMLInputElement>) => {
    const num = Number(e.target.value);
    if (Number.isNaN(num) || num < 0) return;
    onChange({
      mode: "mixed",
      counts: { ...(value.counts ?? {}), [diff]: num },
    });
  };

  return (
    <div className={error ? "mb-4" : "mb-2"}>
      <div className="space-y-2">
        <div className="flex items-center space-x-4">
          <label className="flex items-center cursor-pointer">
            <input
              type="radio"
              name="difficulty-mode"
              value="single"
              checked={value.mode === "single"}
              onChange={handleModeChange}
              disabled={disabled}
              className="h-4 w-4 text-indigo-600"
            />
            <span className="ml-2 text-sm font-medium text-gray-700">Single</span>
          </label>
          <label className="flex items-center cursor-pointer">
            <input
              type="radio"
              name="difficulty-mode"
              value="mixed"
              checked={value.mode === "mixed"}
              onChange={handleModeChange}
              disabled={disabled}
              className="h-4 w-4 text-indigo-600"
            />
            <span className="ml-2 text-sm font-medium text-gray-700">Mixed</span>
          </label>
        </div>

        {value.mode === "single" && (
          <div className="pl-4">
            <label
              htmlFor="difficulty-value"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Value
            </label>
            <select
              id="difficulty-value"
              value={value.value ?? "medium"}
              onChange={handleValueChange}
              disabled={disabled}
              className={`
                block w-full rounded-md border-gray-300 shadow-sm
                focus:border-indigo-500 focus:ring-indigo-500
                sm:text-sm
                ${disabled ? "bg-gray-50 cursor-not-allowed" : ""}
              `}
            >
              <option value="easy">Easy</option>
              <option value="medium">Medium</option>
              <option value="hard">Hard</option>
            </select>
          </div>
        )}

        {value.mode === "mixed" && (
          <div className="pl-4 grid gap-4 grid-cols-3">
            {DIFFS.map((diff) => (
              <div key={diff}>
                <label
                  htmlFor={`difficulty-count-${diff}`}
                  className="block text-sm font-medium text-gray-700 mb-1"
                >
                  {diff.charAt(0).toUpperCase() + diff.slice(1)}
                </label>
                <input
                  id={`difficulty-count-${diff}`}
                  type="number"
                  value={value.counts?.[diff] ?? 0}
                  onChange={(e) => handleCountChange(diff, e)}
                  min={0}
                  step={1}
                  className={`
                    block w-full rounded-md border-gray-300 shadow-sm
                    focus:border-indigo-500 focus:ring-indigo-500
                    sm:text-sm
                    ${disabled ? "bg-gray-50 cursor-not-allowed" : ""}
                  `}
                  disabled={disabled}
                />
              </div>
            ))}
          </div>
        )}
      </div>
      {error && errorMessage && (
        <p className="mt-1 text-sm text-red-600" role="alert">
          {errorMessage}
        </p>
      )}
    </div>
  );
}
