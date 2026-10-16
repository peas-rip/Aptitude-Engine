import type { TestResult } from "../types/qme";

interface ScoreBreakdownProps {
  result: TestResult;
}

export function ScoreBreakdown({ result }: ScoreBreakdownProps) {
  const { score, by_difficulty, by_chapter, by_source } = result;

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">
          Overall Score
        </h3>
        <div className="text-center">
          <div className="text-5xl font-bold text-indigo-600 mb-2">
            {score.percent}%
          </div>
          <p className="text-sm text-gray-600">
            {score.correct} correct out of {score.total} questions
          </p>
          {result.elapsed_seconds !== null && (
            <p className="mt-2 text-sm text-gray-600">
              Time taken: {Math.floor(result.elapsed_seconds / 60)}m {
                result.elapsed_seconds % 60
              }s
            </p>
          )}
        </div>
      </div>

      {Object.keys(by_difficulty).length > 0 && (
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">
            Score by Difficulty
          </h3>
          <div className="grid gap-4 sm:grid-cols-3">
            {["easy", "medium", "hard"].map((diff) => {
              const bu = by_difficulty[diff as keyof typeof by_difficulty];
              if (!bu) return null;
              return (
                <div key={diff} className="text-center">
                  <div className="text-2xl font-bold text-indigo-600 mb-2">
                    {bu.percent}%
                  </div>
                  <p className="text-sm text-gray-600">
                    {bu.correct}/{bu.total}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {Object.keys(by_chapter).length > 0 && (
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">
            Score by Chapter
          </h3>
          <div className="space-y-3">
            {Object.entries(by_chapter).map(([chapter, bu]) => (
              <div key={chapter} className="flex justify-between text-sm">
                <span className="truncate max-w-xs">{chapter}</span>
                <span className="text-right">
                  {bu.percent}% ({bu.correct}/{bu.total})
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {Object.keys(by_source).length > 0 && (
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">
            Score by Source
          </h3>
          <div className="space-y-3">
            {Object.entries(by_source).map(([source, bu]) => (
              <div key={source} className="flex justify-between text-sm">
                <span className="truncate max-w-xs">{source}</span>
                <span className="text-right">
                  {bu.percent}% ({bu.correct}/{bu.total})
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}