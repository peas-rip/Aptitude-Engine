import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useKnowledge } from "../hooks/useKnowledge";
import { toApiError } from "../lib/qme-client";
import { PageHeader } from "../components/PageHeader";
import { Button } from "../components/Button";
import { Select } from "../components/Select";
import { ErrorBanner } from "../components/ErrorBanner";
import { EmptyState, Skeleton } from "../components/EmptyState";

const ALL = "";

export default function FormulasDetail() {
  const params = useParams<{ chapterKey: string }>();
  // Route params arrive percent-encoded; these keys contain spaces, `›` and `&`.
  let chapterKey = params.chapterKey ?? "";
  try {
    chapterKey = decodeURIComponent(chapterKey);
  } catch {
    /* leave the raw value — the 404 state will explain it */
  }

  const [topic, setTopic] = useState(ALL);
  const { fetchKnowledge, data, loading, error } = useKnowledge(
    chapterKey,
    topic === ALL ? undefined : topic,
  );

  // Manual-fetch hook: drive it from (chapterKey, topic).
  useEffect(() => {
    if (chapterKey) void fetchKnowledge();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chapterKey, topic]);

  const notFound = error?.code === "NOT_FOUND";

  const backLink = (
    <Link to="/formulas">
      <Button variant="secondary">← All chapters</Button>
    </Link>
  );

  if (!chapterKey) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-16">
        <EmptyState title="No chapter specified" action={backLink} />
      </div>
    );
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-8 space-y-3">
        <Skeleton className="h-8 w-72" />
        <Skeleton className="h-40" />
      </div>
    );
  }

  if (error) {
    if (notFound) {
      return (
        <div className="mx-auto max-w-3xl px-4 py-8">
          <EmptyState
            title="Chapter not found"
            description="That chapter key is not in the question bank — it may have been renamed."
            action={backLink}
          />
        </div>
      );
    }
    const apiError = toApiError(error);
    return (
      <div className="mx-auto max-w-3xl px-4 py-8">
        {apiError ? (
          <ErrorBanner error={apiError} onRetry={() => void fetchKnowledge()} />
        ) : (
          <EmptyState title="Could not load formulas" action={backLink} />
        )}
      </div>
    );
  }

  const label =
    data?.chapter ??
    (chapterKey.split(" › ").slice(1).join(" › ") || chapterKey);
  const topicKeys = Object.keys(data?.topics ?? {});

  return (
    <div className="mx-auto max-w-3xl px-4 sm:px-6 py-8">
      <PageHeader title={label} actions={backLink} />

      {topicKeys.length > 1 && (
        <div className="mt-4 max-w-sm">
          <p className="mb-1 text-sm font-medium text-gray-700">Topic</p>
          <Select
            value={topic}
            onChange={setTopic}
            options={[
              { value: ALL, label: "All topics" },
              ...topicKeys.map((t) => ({ value: t, label: t })),
            ]}
          />
        </div>
      )}

      {!data || (data.formula_summary.length === 0 && topicKeys.length === 0) ? (
        // 200 with empty lists is a normal state, not an error (spec §6-10).
        <div className="mt-6">
          <EmptyState
            title="No formulas for this chapter yet"
            description="Knowledge is still being written for it. The chapter itself is fine."
            action={backLink}
          />
        </div>
      ) : (
        <>
          {data.formula_summary.length > 0 && (
            <section className="mt-6" aria-label="Chapter summary">
              <h2 className="text-base font-medium text-gray-900">Chapter summary</h2>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-gray-700">
                {data.formula_summary.map((line, i) => (
                  <li key={i}>{line}</li>
                ))}
              </ul>
            </section>
          )}

          <section className="mt-8" aria-label="Topics">
            <h2 className="text-base font-medium text-gray-900">Topics</h2>
            <div className="mt-3 space-y-2">
              {topicKeys.map((t) => {
                const terms = data.topics[t];
                return (
                  <details key={t} className="rounded-lg border border-gray-200 p-4" open>
                    <summary className="cursor-pointer select-none text-sm font-medium text-gray-900">
                      {t}
                    </summary>
                    <div className="mt-3 grid gap-6 sm:grid-cols-2">
                      <div>
                        <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                          Formulas
                        </h3>
                        {terms.formulas.length === 0 ? (
                          <p className="mt-1 text-sm text-gray-500">None recorded.</p>
                        ) : (
                          <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-gray-700">
                            {terms.formulas.map((f, i) => (
                              <li key={i}>{f}</li>
                            ))}
                          </ul>
                        )}
                      </div>
                      <div>
                        <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                          Short tricks
                        </h3>
                        {terms.short_tricks.length === 0 ? (
                          <p className="mt-1 text-sm text-gray-500">None recorded.</p>
                        ) : (
                          <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-gray-700">
                            {terms.short_tricks.map((s, i) => (
                              <li key={i}>{s}</li>
                            ))}
                          </ul>
                        )}
                      </div>
                    </div>
                  </details>
                );
              })}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
