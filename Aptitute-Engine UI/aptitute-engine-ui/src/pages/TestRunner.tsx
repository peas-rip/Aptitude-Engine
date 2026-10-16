import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useDraft } from "../hooks/useDraft";
import { useSubmitTest } from "../hooks/useSubmitTest";
import { toApiError } from "../lib/qme-client";
import type { ApiError } from "../lib/qme-client";
import { Button } from "../components/Button";
import { Timer } from "../components/Timer";
import { ProgressBar } from "../components/ProgressBar";
import { QuestionCard } from "../components/QuestionCard";
import { QuestionNavigator } from "../components/QuestionNavigator";
import { ErrorBanner } from "../components/ErrorBanner";
import { EmptyState, Skeleton } from "../components/EmptyState";

export default function TestRunner() {
  const navigate = useNavigate();
  const { draft, saveDraft, clearDraft, saveResult } = useDraft();
  const { submitTest } = useSubmitTest();

  /** localStorage is read in `useDraft`'s effect, so the very first paint is
   *  neither "restoring" nor "absent" yet. */
  const [restoring, setRestoring] = useState(true);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [error, setError] = useState<ApiError | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [left, setLeft] = useState<number | null>(null);
  const submittedRef = useRef(false);
  const restoredRef = useRef(false);

  // Hydrate saved answers once the draft lands. A mount-only effect would read
  // `draft` as null (effects close over the first render), silently dropping
  // every saved answer on refresh — spec §16.1 requires them restored.
  useEffect(() => {
    if (draft && !restoredRef.current) {
      restoredRef.current = true;
      setAnswers(draft.answers);
    }
  }, [draft]);

  useEffect(() => setRestoring(false), []);

  const deadline = useMemo(
    () =>
      draft
        ? draft.startedAt + draft.test.timing.estimated_total_sec * 1000
        : null,
    [draft?.startedAt, draft?.test.timing.estimated_total_sec],
  );

  // Client-owned countdown (the server records elapsed time but never enforces it).
  useEffect(() => {
    if (deadline === null) return;
    const tick = () => setLeft(Math.max(0, Math.floor((deadline - Date.now()) / 1000)));
    tick();
    const id = window.setInterval(tick, 1000);
    return () => window.clearInterval(id);
  }, [deadline]);

  const finish = useCallback(
    async (elapsedOverride?: number) => {
      if (!draft || submittedRef.current) return;
      submittedRef.current = true;
      setSubmitting(true);
      setError(null);
      const elapsed =
        elapsedOverride ?? Math.max(0, Math.round((Date.now() - draft.startedAt) / 1000));
      try {
        // `draft.body` is the ORIGINAL creation request, seed included — the
        // server regenerates the test from it. Never rebuild it from state.
        const result = await submitTest({
          test_id: draft.test.test_id,
          request: draft.body,
          answers,
          elapsed_seconds: elapsed,
        });
        saveResult(result.test_id, {
          result,
          test: draft.test,
          request: draft.body,
          answers,
        });
        clearDraft();
        navigate("/test/result");
      } catch (e) {
        // Transport failure: keep answers, offer Retry. Submitting the identical
        // body again is idempotent, so a retry cannot double-count.
        submittedRef.current = false;
        setError(toApiError(e));
      } finally {
        setSubmitting(false);
      }
    },
    [draft, answers, submitTest, saveResult, clearDraft, navigate],
  );

  // Auto-submit on expiry.
  useEffect(() => {
    if (left === 0 && !submitting && !submittedRef.current) void finish(0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [left]);

  // Refresh / tab-close guard while the test is live (spec §11.5).
  useEffect(() => {
    if (!draft || submittedRef.current) return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [draft]);

  const choose = (questionId: string, optionKey: string) => {
    if (!draft) return;
    const next = { ...answers, [questionId]: optionKey };
    setAnswers(next);
    // Persist on every answer so a refresh restores without re-POSTing /tests.
    saveDraft({ ...draft, answers: next });
  };

  if (restoring) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-8 space-y-3">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64" />
      </div>
    );
  }

  if (!draft) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-16">
        <EmptyState
          title="No test in progress"
          description="Start a test to begin. Drafts are stored in this browser only."
          action={
            <Link to="/test/new">
              <Button>Start a test</Button>
            </Link>
          }
        />
      </div>
    );
  }

  const total = draft.test.questions.length;
  const answeredSet = new Set(
    draft.test.questions
      .map((q, i) => (answers[q.question_id] !== undefined ? i + 1 : -1))
      .filter((n) => n > 0),
  );
  const answeredCount = answeredSet.size;
  const unanswered = total - answeredCount;

  const jump = (index: number) => {
    document.getElementById(`q-${index}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const confirmSubmit = () => {
    if (unanswered > 0) {
      const ok = window.confirm(
        `${unanswered} question${unanswered === 1 ? " is" : "s are"} still unanswered. Unanswered questions score as wrong. Submit anyway?`,
      );
      if (!ok) return;
    }
    void finish();
  };

  return (
    <div className="mx-auto max-w-4xl px-4 sm:px-6 py-6">
      <header className="sticky top-0 z-10 -mx-4 mb-4 border-b border-gray-200 bg-white px-4 py-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0">
            <h1 className="truncate text-base font-semibold text-gray-900">
              {draft.test.title ?? "Test"}
              <span className="ml-2 font-normal text-gray-500">· {total} questions</span>
            </h1>
            <p className="text-sm text-gray-600">
              Answered {answeredCount}/{total}
            </p>
          </div>
          <div aria-live="polite">
            <Timer seconds={left ?? draft.test.timing.estimated_total_sec} />
          </div>
        </div>
        <div className="mt-2">
          <ProgressBar value={answeredCount} max={total} />
        </div>
      </header>

      {error && (
        <div className="mb-4">
          <ErrorBanner error={error} onRetry={() => void finish()}>
            Your answers are still here — retrying sends the same submission.
          </ErrorBanner>
        </div>
      )}

      <div className="space-y-4">
        {draft.test.questions.map((q, i) => (
          <section key={q.question_id} id={`q-${i}`} className="scroll-mt-28">
            <p className="mb-1 text-xs font-medium uppercase tracking-wide text-gray-400">
              {i + 1} · {q.classification.difficulty} · {q.classification.chapter}
            </p>
            {/* reveal stays false — correct_answer/solution must not reach the DOM */}
            <QuestionCard
              question={q}
              reveal={false}
              value={answers[q.question_id]}
              onChange={(key) => choose(q.question_id, key)}
              disabled={submitting}
            />
          </section>
        ))}
      </div>

      <footer className="sticky bottom-0 -mx-4 mt-6 border-t border-gray-200 bg-white px-4 py-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <QuestionNavigator total={total} answered={answeredSet} onJump={jump} />
          <div className="flex items-center gap-3">
            {/* Spec §7.3: /test/run is a bare route — no nav out of the test.
                The draft persists in localStorage, so browser-back is safe. */}
            <Button onClick={confirmSubmit} loading={submitting}>
              {submitting ? "Submitting…" : "Submit test"}
            </Button>
          </div>
        </div>
      </footer>
    </div>
  );
}
