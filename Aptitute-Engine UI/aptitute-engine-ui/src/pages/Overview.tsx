import { Link } from "react-router-dom";
import { useBankMeta } from "../hooks/useBankMeta";
import { useHealth } from "../hooks/useHealth";
import { asApiError } from "../lib/qme-client";
import { ErrorBanner } from "../components/ErrorBanner";
import { Skeleton } from "../components/EmptyState";
import { Button } from "../components/Button";
import type { ChapterInfo, Difficulty } from "../types/qme";

const ORDER: Difficulty[] = ["easy", "medium", "hard"];

function countFor(chapters: ChapterInfo[], d: Difficulty): number {
  return chapters.reduce((sum, c) => sum + (c.difficulty_counts[d] ?? 0), 0);
}

export default function Overview() {
  const { meta, loading, error, refetch } = useBankMeta();
  const health = useHealth();

  const apiError = error ? asApiError(error) : null;

  if (loading) {
    return (
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-20" />
          ))}
        </div>
        <Skeleton className="mt-8 h-8 w-64" />
        <div className="mt-4 space-y-2">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="h-10" />
          ))}
        </div>
      </div>
    );
  }

  if (apiError) {
    return (
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
        <ErrorBanner error={apiError} onRetry={refetch} />
      </div>
    );
  }

  if (!meta) return null;

  const allChapters = meta.sources.flatMap((s) => s.chapters);
  const byDifficulty = Object.fromEntries(
    ORDER.map((d) => [d, countFor(allChapters, d)]),
  ) as Record<Difficulty, number>;
  const pending = new Set(meta.knowledge_coverage.missing_chapters);

  const rows = [...allChapters].sort((a, b) => b.question_count - a.question_count);

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
      {health.error && (
        <div className="mb-6">
          <ErrorBanner error={asApiError(health.error)} onRetry={health.refetch} />
        </div>
      )}

      {/* Bank summary strip — every value from GET /bank/meta, never hardcoded */}
      <section aria-label="Bank summary" className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className="rounded-lg border border-gray-200 p-4">
          <p className="text-2xl font-semibold text-gray-900">{meta.question_count}</p>
          <p className="text-sm text-gray-600">questions</p>
        </div>
        <div className="rounded-lg border border-gray-200 p-4">
          <p className="text-2xl font-semibold text-gray-900">{meta.chapters.length}</p>
          <p className="text-sm text-gray-600">chapters</p>
        </div>
        <div className="rounded-lg border border-gray-200 p-4">
          <p className="text-2xl font-semibold text-gray-900">{meta.sources.length}</p>
          <p className="text-sm text-gray-600">sources</p>
        </div>
        <div className="rounded-lg border border-gray-200 p-4">
          <div className="flex h-8 w-full overflow-hidden rounded bg-gray-100">
            {ORDER.map((d) => {
              const total = byDifficulty.easy + byDifficulty.medium + byDifficulty.hard;
              const pct = total ? (byDifficulty[d] / total) * 100 : 0;
              const cls =
                d === "easy" ? "bg-green-400" : d === "medium" ? "bg-amber-400" : "bg-red-400";
              return pct > 0 ? <span key={d} className={cls} style={{ width: `${pct}%` }} /> : null;
            })}
          </div>
          <p className="mt-1 text-xs text-gray-600">
            {ORDER.map((d) => `${d} ${byDifficulty[d]}`).join(" · ")}
          </p>
        </div>
      </section>

      {/* Primary actions */}
      <section aria-label="Primary actions" className="mt-8 flex flex-wrap gap-3">
        <Link to="/test/new">
          <Button>Start a test →</Button>
        </Link>
        <Link to="/practice">
          <Button variant="secondary">Practice a chapter</Button>
        </Link>
        <Link to="/formulas">
          <Button variant="secondary">Formulas</Button>
        </Link>
      </section>

      {/* Coverage */}
      <section aria-label="Coverage by chapter" className="mt-10">
        <h2 className="text-lg font-medium text-gray-900">Coverage by chapter</h2>
        <div className="mt-3 overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead>
              <tr className="text-left text-gray-500">
                <th className="py-2 pr-4 font-medium">Chapter</th>
                <th className="py-2 pr-4 text-right font-medium">Total</th>
                <th className="py-2 pr-4 text-right font-medium">Easy</th>
                <th className="py-2 pr-4 text-right font-medium">Medium</th>
                <th className="py-2 pr-4 text-right font-medium">Hard</th>
                <th className="py-2 font-medium">Formulas</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {rows.map((c) => (
                <tr key={c.key} className="hover:bg-gray-50">
                  <td className="py-2 pr-4">
                    <Link
                      to={`/practice?chapter=${encodeURIComponent(c.key)}`}
                      className="text-indigo-600 hover:underline"
                    >
                      {c.label}
                    </Link>
                  </td>
                  <td className="py-2 pr-4 text-right tabular-nums">{c.question_count}</td>
                  <td className="py-2 pr-4 text-right tabular-nums">
                    {c.difficulty_counts.easy ?? 0}
                  </td>
                  <td className="py-2 pr-4 text-right tabular-nums">
                    {c.difficulty_counts.medium ?? 0}
                  </td>
                  <td className="py-2 pr-4 text-right tabular-nums">
                    {c.difficulty_counts.hard ?? 0}
                  </td>
                  <td className="py-2">
                    {pending.has(c.label) ? (
                      <span className="inline-flex rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-500">
                        formulas pending
                      </span>
                    ) : (
                      <span className="inline-flex rounded bg-green-100 px-2 py-0.5 text-xs text-green-700">
                        available
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Admin lives outside the primary nav (spec §7.3) */}
      <footer className="mt-12 border-t border-gray-200 pt-4">
        <Link to="/admin" className="text-xs text-gray-400 hover:text-gray-600">
          Admin (not available)
        </Link>
      </footer>
    </div>
  );
}
