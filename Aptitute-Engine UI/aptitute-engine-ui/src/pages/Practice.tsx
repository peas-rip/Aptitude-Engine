import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useBankMeta } from "../hooks/useBankMeta";
import { usePractice } from "../hooks/usePractice";
import { toApiError, asApiError } from "../lib/qme-client";
import { PageHeader } from "../components/PageHeader";
import { Button } from "../components/Button";
import { Select } from "../components/Select";
import { QuestionCard } from "../components/QuestionCard";
import { KnowledgePanel } from "../components/KnowledgePanel";
import { ErrorBanner } from "../components/ErrorBanner";
import { EmptyState, Skeleton } from "../components/EmptyState";
import type { Difficulty, PracticeRequest, PracticeSet, TestMode } from "../types/qme";
import { practiceBody } from "../lib/practice-rules";

const ALL = "";
const DIFFS: Difficulty[] = ["easy", "medium", "hard"];

export default function Practice() {
  const [searchParams] = useSearchParams();
  const { meta, loading: metaLoading, error: metaError, refetch } = useBankMeta();
  const { practice, loading, error } = usePractice();

  // Draft controls (what the user is choosing) …
  const [source, setSource] = useState(ALL);
  const [chapter, setChapter] = useState(searchParams.get("chapter") ?? ALL);
  const [topic, setTopic] = useState(ALL);
  const [difficulty, setDifficulty] = useState(ALL);
  const [mode, setMode] = useState<TestMode>("progressive");

  // … versus the identity of the pool currently being paged through.
  const [applied, setApplied] = useState<PracticeRequest | null>(null);
  const [set, setSet] = useState<PracticeSet | null>(null);
  const [seed, setSeed] = useState<number | undefined>(undefined);
  const [page, setPage] = useState(1);
  const [attempt, setAttempt] = useState(0);

  const sourceChapters = useMemo(() => {
    if (!meta) return [];
    const s = meta.sources.find((x) => x.name === source);
    return s ? s.chapters : meta.sources.flatMap((x) => x.chapters);
  }, [meta, source]);

  const buildFilters = (): PracticeRequest => {
    const f: PracticeRequest = {};
    if (source) f.source = source;
    if (chapter) f.chapter = chapter;
    if (topic) f.topic = topic;
    if (difficulty) f.difficulty = difficulty as Difficulty;
    f.mode = mode;
    return f;
  };

  const load = useCallback(
    async (filters: PracticeRequest, nextPage: number, nextSeed?: number) => {
      const body: PracticeRequest = practiceBody(filters, nextPage, nextSeed);
      try {
        const res = await practice(body);
        setSet(res);
        setPage(nextPage);
        // Echo the seed — page 2 onward MUST resend it or the pool reshuffles.
        setSeed(res.seed ?? undefined);
        setApplied(filters);
      } catch (e) {
        const err = toApiError(e);
        const total = err?.details.total_pages;
        // Page past the end is an error, not a clamp — clamp and refetch once.
        if (err?.code === "INVALID_INPUT" && typeof total === "number" && total >= 1) {
          const clamped = { ...filters };
          const retry: PracticeRequest = practiceBody(clamped, total, nextSeed);
          try {
            const res = await practice(retry);
            setSet(res);
            setPage(total);
            setSeed(res.seed ?? undefined);
            setApplied(clamped);
          } catch {
            /* surface the original error via the hook's state */
          }
        }
      }
    },
    [practice],
  );

  // First render (and any `?chapter=` deep link) → fetch page 1.
  useEffect(() => {
    if (!meta) return;
    void load(buildFilters(), 1, undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [meta, attempt]);

  const applyFilters = () => {
    // Any filter change reshuffles the pool: identity resets to page 1/no seed.
    setSeed(undefined);
    setSet(null);
    void load(buildFilters(), 1, undefined);
  };

  const resetFilters = () => {
    setSource(ALL);
    setChapter(ALL);
    setTopic(ALL);
    setDifficulty(ALL);
    setMode("progressive");
    setSeed(undefined);
    setSet(null);
    setAttempt((a) => a + 1);
  };

  if (metaLoading) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-8 space-y-3">
        <Skeleton className="h-10 w-96" />
        <Skeleton className="h-64" />
      </div>
    );
  }

  if (metaError) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-8">
        <ErrorBanner error={asApiError(metaError)} onRetry={refetch} />
      </div>
    );
  }

  if (!meta) return null;

  const pagination = set?.pagination;
  const emptyPool =
    !loading && !error && set !== null && set.questions.length === 0;
  const noAttemptYet = !loading && !error && set === null;

  return (
    <div className="mx-auto max-w-4xl px-4 sm:px-6 py-8">
      <PageHeader title="Practice" />

      {/* Filters apply on explicit action — never on keystroke (spec §6-7) */}
      <section aria-label="Filters" className="mt-6 rounded-lg border border-gray-200 p-4">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <div>
            <p className="mb-1 text-sm font-medium text-gray-700">Source</p>
            <Select
              value={source}
              onChange={(v) => {
                setSource(v);
                setChapter(ALL);
              }}
              options={[
                { value: ALL, label: "All sources" },
                ...meta.sources.map((s) => ({ value: s.name, label: s.name })),
              ]}
            />
          </div>

          <div>
            <p className="mb-1 text-sm font-medium text-gray-700">Chapter</p>
            <Select
              value={chapter}
              onChange={setChapter}
              options={[
                { value: ALL, label: "All chapters" },
                ...sourceChapters.map((c) => ({ value: c.key, label: c.label })),
              ]}
            />
          </div>

          <div>
            <p className="mb-1 text-sm font-medium text-gray-700">Topic</p>
            <Select
              value={topic}
              onChange={setTopic}
              options={[
                { value: ALL, label: "All topics" },
                ...meta.topics.map((t) => ({ value: t, label: t })),
              ]}
            />
          </div>

          <div>
            <p className="mb-1 text-sm font-medium text-gray-700">Difficulty</p>
            <Select
              value={difficulty}
              onChange={setDifficulty}
              options={[
                { value: ALL, label: "All difficulties" },
                ...DIFFS.filter((d) => meta.difficulties.includes(d)).map((d) => ({
                  value: d,
                  label: d,
                })),
              ]}
            />
          </div>

          <div>
            <p className="mb-1 text-sm font-medium text-gray-700">Order</p>
            <Select
              value={mode}
              onChange={(v) => setMode(v as TestMode)}
              options={[
                { value: "progressive", label: "Easy → hard (progressive)" },
                { value: "mixed", label: "Shuffled (mixed)" },
              ]}
            />
          </div>
        </div>

        <div className="mt-4 flex gap-3">
          <Button onClick={applyFilters} loading={loading}>
            Apply
          </Button>
          <Button variant="ghost" onClick={resetFilters}>
            Reset
          </Button>
        </div>
      </section>

      {error && (
        <div className="mt-4">
          <ErrorBanner
            error={error}
            onRetry={() => applied && void load(applied, page, seed)}
          />
        </div>
      )}

      <section className="mt-6 space-y-4" aria-live="polite">
        {loading && noAttemptYet && (
          <>
            <Skeleton className="h-40" />
            <Skeleton className="h-40" />
          </>
        )}

        {!loading && !set && !error && (
          <EmptyState
            title="Pick some filters"
            description="Choose a source, chapter, topic or difficulty, then press Apply."
          />
        )}

        {emptyPool && (
          <EmptyState
            title="No questions match these filters"
            description="Loosen the selection and try again."
            action={
              <Button variant="secondary" onClick={resetFilters}>
                Reset filters
              </Button>
            }
          />
        )}

        {set &&
          set.questions.map((q) => (
            // Practice is self-study: answers and solutions are already in the
            // payload and revealed immediately (API_INTEGRATION.md §3.5).
            <QuestionCard key={q.question_id} question={q} reveal />
          ))}

        {set && (set.questions.length > 0) && (
          <KnowledgePanel
            topicKnowledge={set.topic_knowledge}
            chapterFormulaSummary={set.chapter_formula_summary}
          />
        )}
      </section>

      {pagination && (
        <nav
          aria-label="Pagination"
          className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-gray-200 pt-4"
        >
          <Button
            variant="secondary"
            disabled={page <= 1 || loading}
            onClick={() => applied && void load(applied, page - 1, seed)}
          >
            ◀ Prev
          </Button>

          <span className="text-sm text-gray-600">
            Page {pagination.page} of {pagination.total_pages} · {pagination.total} questions
            {seed !== undefined && <span className="text-gray-400"> · seed {seed}</span>}
          </span>

          <Button
            variant="secondary"
            disabled={!pagination.has_more || loading}
            onClick={() => applied && void load(applied, page + 1, seed)}
          >
            Next ▶
          </Button>
        </nav>
      )}
    </div>
  );
}
