import { useState, useEffect } from "react";
import type { GeneratedTest, TestResult } from "../types/qme";
import type { TestRequest } from "../types/qme";

const DRAFT_KEY = "qme.activeTest";
const RESULT_PREFIX = "qme.result.";
const LAST_RESULT_KEY = "qme.lastResult";

/**
 * Everything persisted after submit. There is no `GET /tests/{id}/result`, so
 * the report is unrecoverable if this is lost (spec §6-3).
 *
 * - `test`    — supplies real question text/options for the review list.
 * - `request` — the original creation body (with seed) for "Retake".
 * - `answers` — what the user chose, for "review my answers" without a resubmit.
 */
export interface StoredResult {
  result: TestResult;
  test?: GeneratedTest;
  request?: TestRequest;
  answers?: Record<string, string>;
}

export interface DraftState {
  body: TestRequest;
  test: GeneratedTest;
  answers: Record<string, string>;
  startedAt: number;
}

export function useDraft() {
  const [draft, setDraft] = useState<DraftState | null>(null);

  // Load draft from localStorage on init
  useEffect(() => {
    const saved = localStorage.getItem(DRAFT_KEY);
    if (saved) {
      try {
        const parsed = JSON.parse(saved) as Partial<DraftState>;
        if (
          parsed.body &&
          parsed.test &&
          parsed.answers &&
          typeof parsed.startedAt === "number"
        ) {
          setDraft(parsed as DraftState);
        }
      } catch {
        // ignore corrupt data
        localStorage.removeItem(DRAFT_KEY);
      }
    }
  }, []);

  const saveDraft = (draftData: DraftState) => {
    try {
      localStorage.setItem(DRAFT_KEY, JSON.stringify(draftData));
      setDraft(draftData);
    } catch (e) {
      console.warn("Failed to save draft", e);
    }
  };

  const clearDraft = () => {
    localStorage.removeItem(DRAFT_KEY);
    setDraft(null);
  };

  // ── Result persistence ──────────────────────────────────────────────────
  const saveResult = (testId: string, entry: StoredResult) => {
    try {
      localStorage.setItem(RESULT_PREFIX + testId, JSON.stringify(entry));
      // Point the report route at it — submit navigates without an id.
      localStorage.setItem(LAST_RESULT_KEY, testId);
    } catch (e) {
      console.warn("Failed to save result", e);
    }
  };

  /** Whole stored record, or null. Tolerates the legacy bare-TestResult shape. */
  const loadStoredResult = (testId: string): StoredResult | null => {
    if (!testId) return null;
    try {
      const saved = localStorage.getItem(RESULT_PREFIX + testId);
      if (!saved) return null;
      const parsed = JSON.parse(saved) as Partial<StoredResult>;
      if (parsed && parsed.result) return parsed as StoredResult;
      return { result: parsed as unknown as TestResult };
    } catch {
      return null;
    }
  };

  /** What `/test/result` renders on a fresh load or hard refresh. */
  const loadLastResult = (): (StoredResult & { testId: string }) | null => {
    try {
      const testId = localStorage.getItem(LAST_RESULT_KEY);
      if (!testId) return null;
      const entry = loadStoredResult(testId);
      return entry ? { ...entry, testId } : null;
    } catch {
      return null;
    }
  };

  const loadResult = (testId: string): TestResult | null =>
    loadStoredResult(testId)?.result ?? null;

  const clearResult = (testId: string) => {
    localStorage.removeItem(RESULT_PREFIX + testId);
    if (localStorage.getItem(LAST_RESULT_KEY) === testId) {
      localStorage.removeItem(LAST_RESULT_KEY);
    }
  };

  return {
    draft,
    setDraft,
    saveDraft,
    clearDraft,
    saveResult,
    loadStoredResult,
    loadLastResult,
    loadResult,
    clearResult,
  };
}
