import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useBankMeta } from "../hooks/useBankMeta";
import { useCreateTest } from "../hooks/useCreateTest";
import { useDraft } from "../hooks/useDraft";
import { toApiError, asApiError } from "../lib/qme-client";
import { PageHeader } from "../components/PageHeader";
import { Button } from "../components/Button";
import { Select } from "../components/Select";
import { NumberStepper } from "../components/NumberStepper";
import { DifficultyPicker } from "../components/DifficultyPicker";
import { ErrorBanner } from "../components/ErrorBanner";
import { Skeleton } from "../components/EmptyState";
import type { Difficulty, DifficultySpec, FriendlyTestRequest } from "../types/qme";
import {
  DIFFS,
  validateTestRequest,
  availableFor,
  feasibilityMessage,
  withEchoedSeed,
} from "../lib/test-rules";

const ALL = "";

export default function TestSetup() {
  const navigate = useNavigate();
  const { meta, loading, error: metaError, refetch } = useBankMeta();
  const { createTest, loading: creating } = useCreateTest();
  const { saveDraft } = useDraft();

  const [source, setSource] = useState(ALL);
  const [chapter, setChapter] = useState(ALL);
  const [difficulty, setDifficulty] = useState<DifficultySpec>({
    mode: "single",
    value: "medium",
  });
  const [count, setCount] = useState(10);
  const [serverError, setServerError] = useState<ReturnType<typeof toApiError>>(null);

  const sourceChapters = useMemo(() => {
    if (!meta) return [];
    const s = meta.sources.find((x) => x.name === source);
    return s ? s.chapters : meta.sources.flatMap((x) => x.chapters);
  }, [meta, source]);

  /** Everything the request would actually scope to, so feasibility is checked
   *  against the real pool before we ever POST. */
  const scopeChapters = useMemo(() => {
    if (!meta) return [];
    if (chapter) {
      const c = sourceChapters.find((x) => x.key === chapter);
      return c ? [c] : [];
    }
    return sourceChapters;
  }, [meta, sourceChapters, chapter]);

  const available = (d: Difficulty): number => availableFor(scopeChapters, d);

  const errors = meta ? validateTestRequest(count, difficulty, Boolean(chapter)) : {};

  const feasibilityProblem =
    meta && !errors.count && !errors.difficulty
      ? feasibilityMessage(scopeChapters, difficulty, count)
      : null;

  const canStart =
    Boolean(meta) &&
    !creating &&
    Object.keys(errors).length === 0 &&
    !feasibilityProblem;

  const buildBody = (): FriendlyTestRequest => {
    // "All sources"/"All chapters" OMIT the field — an empty array is an error.
    const body: FriendlyTestRequest = { count, difficulty };
    if (source) body.sources = [source];
    if (chapter) body.chapters = [chapter];
    return body;
  };

  const start = async () => {
    if (!canStart) return;
    setServerError(null);
    const body = buildBody();
    try {
      const test = await createTest(body);
      // Start sends no seed (the server mints one); the echoed value must be
      // folded back into the stored request or submit fails `seed_required`.
      const storedBody = withEchoedSeed(body, test.seed);
      saveDraft({ body: storedBody, test, answers: {}, startedAt: Date.now() });
      navigate("/test/run");
    } catch (e) {
      setServerError(toApiError(e));
    }
  };

  if (loading) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-8 space-y-4">
        <Skeleton className="h-10 w-56" />
        <Skeleton className="h-64" />
      </div>
    );
  }

  if (metaError) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-8">
        <ErrorBanner error={asApiError(metaError)} onRetry={refetch} />
      </div>
    );
  }

  if (!meta) return null;

  const chapterOption = sourceChapters.find((c) => c.key === chapter);

  return (
    <div className="mx-auto max-w-3xl px-4 sm:px-6 py-8">
      <PageHeader title="New test" />

      <div className="mt-6 space-y-6">
        <div className="grid gap-6 sm:grid-cols-2">
          <div>
            <p className="mb-2 text-sm font-medium text-gray-700">Source</p>
            <Select
              value={source}
              onChange={(v) => {
                setSource(v);
                setChapter(ALL);
              }}
              options={[
                { value: ALL, label: `All sources (${meta.sources.length})` },
                ...meta.sources.map((s) => ({
                  value: s.name,
                  label: `${s.name} (${s.question_count})`,
                })),
              ]}
            />
          </div>

          <div>
            <p className="mb-2 text-sm font-medium text-gray-700">Chapter</p>
            <Select
              value={chapter}
              onChange={setChapter}
              disabled={sourceChapters.length === 0}
              options={[
                { value: ALL, label: `All chapters (${sourceChapters.length})` },
                ...sourceChapters.map((c) => ({
                  value: c.key,
                  label: `${c.label} (${c.question_count})`,
                })),
              ]}
            />
          </div>
        </div>

        {chapterOption && (
          <p className="-mt-4 text-sm text-gray-600">
            {chapterOption.question_count} questions ·{" "}
            {DIFFS.map((d) => `${chapterOption.difficulty_counts[d] ?? 0} ${d}`).join(" · ")}
          </p>
        )}

        <div>
          <p className="mb-2 text-sm font-medium text-gray-700">Difficulty</p>
          <DifficultyPicker
            value={difficulty}
            onChange={setDifficulty}
            error={Boolean(errors.difficulty)}
            errorMessage={errors.difficulty}
          />
        </div>

        <div>
          <p className="mb-2 text-sm font-medium text-gray-700">Length</p>
          <NumberStepper
            value={count}
            onChange={setCount}
            min={chapter ? 10 : 30}
            step={5}
            error={Boolean(errors.count)}
            errorMessage={errors.count}
          />
          {feasibilityProblem ? (
            <p className="mt-1 text-sm text-red-600" role="alert">
              {feasibilityProblem}
            </p>
          ) : (
            !errors.count && (
              <p className="mt-1 text-sm text-gray-600">
                {DIFFS.map((d) => `${available(d)} ${d} available`).join(" · ")}
              </p>
            )
          )}
        </div>

        <p className="text-sm text-gray-600">Seed: auto (generated by the server)</p>

        {serverError && (
          <ErrorBanner error={serverError} />
        )}

        <Button onClick={() => void start()} disabled={!canStart} loading={creating}>
          {creating ? "Starting…" : "Start test"}
        </Button>
      </div>
    </div>
  );
}
