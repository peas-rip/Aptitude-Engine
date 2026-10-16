import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useDraft } from "../hooks/useDraft";
import { useCreateTest } from "../hooks/useCreateTest";
import { toApiError } from "../lib/qme-client";
import { PageHeader } from "../components/PageHeader";
import { Button } from "../components/Button";
import { ScoreBreakdown } from "../components/ScoreBreakdown";
import { ReviewList } from "../components/ReviewList";
import { ErrorBanner } from "../components/ErrorBanner";
import { EmptyState } from "../components/EmptyState";
import type { ResultLine, TestResult } from "../types/qme";

type Filter = "all" | "incorrect";

function worstChapter(result: TestResult): string | null {
  const entries = Object.entries(result.by_chapter);
  if (entries.length === 0) return null;
  entries.sort((a, b) => a[1].percent - b[1].percent);
  return entries[0][0];
}

export default function TestResult() {
  const navigate = useNavigate();
  const { loadLastResult, saveDraft } = useDraft();
  const { createTest, loading: retaking } = useCreateTest();
  const [filter, setFilter] = useState<Filter>("all");
  const [error, setError] = useState<ReturnType<typeof toApiError>>(null);

  // Read once on mount: the report must survive a hard refresh (spec §6-3).
  const stored = useMemo(() => loadLastResult(), []);

  const result = stored?.result;

  const retake = async () => {
    if (!stored?.request) {
      navigate("/test/new");
      return;
    }
    setError(null);
    try {
      // Same request (same seed) => the identical questions, fresh attempt.
      const test = await createTest(stored.request);
      saveDraft({ body: stored.request, test, answers: {}, startedAt: Date.now() });
      navigate("/test/run");
    } catch (e) {
      setError(toApiError(e));
    }
  };

  if (!result) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-16">
        <EmptyState
          title="No saved result"
          description="Results are stored in this browser after you submit — there is no endpoint to fetch one later."
          action={
            <Link to="/test/new">
              <Button>Start a test</Button>
            </Link>
          }
        />
      </div>
    );
  }

  const filtered: ResultLine[] =
    filter === "incorrect" ? result.results.filter((r) => !r.is_correct) : result.results;

  const weak = worstChapter(result);
  const seed = stored?.test?.seed;

  return (
    <div className="mx-auto max-w-4xl px-4 sm:px-6 py-8">
      <PageHeader
        title={`Result · ${result.score.correct}/${result.score.total} correct`}
        actions={
          <div className="flex flex-wrap gap-3">
            <Button variant="secondary" onClick={() => void retake()} loading={retaking}>
              Retake
            </Button>
            {weak && (
              <Link
                to={`/practice?chapter=${encodeURIComponent(weak)}`}
              >
                <Button variant="secondary">Practice weak chapter</Button>
              </Link>
            )}
          </div>
        }
      />

      <p className="mt-2 text-sm text-gray-600">
        {result.elapsed_seconds !== null && (
          <>Time {Math.floor(result.elapsed_seconds / 60)}m {result.elapsed_seconds % 60}s · </>
        )}
        {seed !== undefined && seed !== null && <>seed {seed} · </>}
        {result.test_id}
      </p>

      {error && (
        <div className="mt-4">
          <ErrorBanner error={error} />
        </div>
      )}

      <div className="mt-6">
        <ScoreBreakdown result={result} />
      </div>

      <section className="mt-8" aria-label="Review">
        <div className="mb-3 flex items-center justify-between gap-4">
          <h2 className="text-lg font-medium text-gray-900">
            Review ({filtered.length})
          </h2>
          <div className="flex rounded-md border border-gray-200 p-0.5 text-sm">
            <button
              onClick={() => setFilter("all")}
              className={`rounded px-3 py-1 ${
                filter === "all" ? "bg-indigo-600 text-white" : "text-gray-600 hover:bg-gray-50"
              }`}
            >
              All
            </button>
            <button
              onClick={() => setFilter("incorrect")}
              className={`rounded px-3 py-1 ${
                filter === "incorrect"
                  ? "bg-indigo-600 text-white"
                  : "text-gray-600 hover:bg-gray-50"
              }`}
            >
              Incorrect only
            </button>
          </div>
        </div>

        {filtered.length === 0 ? (
          <EmptyState
            title={filter === "incorrect" ? "Nothing incorrect" : "No questions"}
            description={
              filter === "incorrect"
                ? "Every question in this test was answered correctly."
                : undefined
            }
          />
        ) : (
          // `test` supplies the real question text/options for each result line.
          <ReviewList result={{ ...result, results: filtered }} test={stored?.test} />
        )}
      </section>
    </div>
  );
}
