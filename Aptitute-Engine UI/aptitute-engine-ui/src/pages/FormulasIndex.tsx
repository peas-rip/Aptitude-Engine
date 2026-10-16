import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useBankMeta } from "../hooks/useBankMeta";
import { asApiError } from "../lib/qme-client";
import { PageHeader } from "../components/PageHeader";
import { ErrorBanner } from "../components/ErrorBanner";
import { EmptyState, Skeleton } from "../components/EmptyState";
import { CHAPTER_SEP } from "../types/qme";

/** Knowledge coverage is reported against UNQUALIFIED chapter names. */
function labelOf(qualifiedKey: string): string {
  const idx = qualifiedKey.indexOf(CHAPTER_SEP);
  return idx === -1 ? qualifiedKey : qualifiedKey.slice(idx + CHAPTER_SEP.length);
}

export default function FormulasIndex() {
  const { meta, loading, error, refetch } = useBankMeta();
  const [query, setQuery] = useState("");

  const covered = useMemo(
    () => new Set(meta?.knowledge_coverage.covered_chapters ?? []),
    [meta],
  );

  const rows = useMemo(() => {
    if (!meta) return [];
    const q = query.trim().toLowerCase();
    return meta.chapters.filter((key) => {
      if (!q) return true;
      return labelOf(key).toLowerCase().includes(q) || key.toLowerCase().includes(q);
    });
  }, [meta, query]);

  if (loading) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-8 space-y-3">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-40" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-8">
        <ErrorBanner error={asApiError(error)} onRetry={refetch} />
      </div>
    );
  }

  if (!meta) return null;

  return (
    <div className="mx-auto max-w-3xl px-4 sm:px-6 py-8">
      <PageHeader title="Formulas" />

      <div className="mt-6">
        <label htmlFor="formula-search" className="sr-only">
          Search chapters
        </label>
        <input
          id="formula-search"
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search chapters…"
          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
        />
      </div>

      {rows.length === 0 ? (
        <div className="mt-6">
          <EmptyState title="No chapter matches that search" />
        </div>
      ) : (
        <ul className="mt-4 divide-y divide-gray-100">
          {rows.map((key) => {
            const label = labelOf(key);
            const hasFormulas = covered.has(label);
            return (
              <li key={key}>
                {hasFormulas ? (
                  <Link
                    to={`/formulas/${encodeURIComponent(key)}`}
                    className="flex items-center justify-between py-3 hover:bg-gray-50"
                  >
                    <span className="text-sm text-indigo-600">{label}</span>
                    <span className="inline-flex rounded bg-green-100 px-2 py-0.5 text-xs text-green-700">
                      available
                    </span>
                  </Link>
                ) : (
                  // Shown but disabled: the chapter exists, its knowledge is just
                  // empty — an expected state, not an error (spec §6-10).
                  <div
                    className="flex cursor-not-allowed items-center justify-between py-3 opacity-60"
                    aria-disabled="true"
                  >
                    <span className="text-sm text-gray-600">{label}</span>
                    <span className="inline-flex rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-500">
                      formulas pending
                    </span>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}

      <p className="mt-6 text-xs text-gray-400">
        {meta.question_count} questions across {meta.chapters.length} chapters ·{" "}
        {meta.knowledge_coverage.covered_chapters.length} with formulas
      </p>
    </div>
  );
}
