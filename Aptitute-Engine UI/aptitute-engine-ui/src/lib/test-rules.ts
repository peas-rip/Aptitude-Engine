import type { Difficulty, DifficultySpec, FriendlyTestRequest, ChapterInfo } from "../types/qme";

export const DIFFS: Difficulty[] = ["easy", "medium", "hard"];

export interface TestRuleErrors {
  count?: string;
  difficulty?: string;
}

/**
 * Client-side mirror of the friendly-shape rule table
 * (docs/API_CONTRACTS.md §1.7 / API_INTEGRATION.md §3.3.3).
 *
 * Every rule here is deterministic, so a user should never see a 422 for one
 * of them. Extracted from the page so it is unit-testable.
 */
export function validateTestRequest(
  count: number,
  difficulty: DifficultySpec,
  chapterScopeSelected: boolean,
): TestRuleErrors {
  const errors: TestRuleErrors = {};

  if (count % 5 !== 0) {
    errors.count = "Length must be a multiple of 5.";
  } else if (chapterScopeSelected && count < 10) {
    errors.count = "Minimum 10 questions in a chapter scope.";
  } else if (!chapterScopeSelected && count < 30) {
    errors.count = "Minimum 30 questions when no chapter is selected.";
  }

  if (difficulty.mode === "single" && !difficulty.value) {
    errors.difficulty = "Pick a difficulty.";
  }

  if (difficulty.mode === "mixed") {
    const counts = difficulty.counts ?? {};
    const sum = DIFFS.reduce((s, d) => s + (counts[d] ?? 0), 0);
    if (DIFFS.some((d) => (counts[d] ?? 0) < 0)) {
      errors.difficulty = "Counts cannot be negative.";
    } else if (sum !== count) {
      errors.difficulty = `Counts add up to ${sum} — they must equal ${count}.`;
    }
  }

  return errors;
}

/** How many questions the requested filters can actually reach. */
export function availableFor(
  scope: ChapterInfo[],
  difficulty: Difficulty,
): number {
  return scope.reduce((sum, c) => sum + (c.difficulty_counts[difficulty] ?? 0), 0);
}

/** `null` when the request is feasible; otherwise human-readable corrective copy. */
export function feasibilityMessage(
  scope: ChapterInfo[],
  difficulty: DifficultySpec,
  count: number,
): string | null {
  if (difficulty.mode === "single") {
    const d = difficulty.value;
    if (!d) return null;
    const have = availableFor(scope, d);
    return have < count
      ? `Only ${have} ${d} question${have === 1 ? "" : "s"} in this scope — lower the length.`
      : null;
  }

  const counts = difficulty.counts ?? {};
  const short = DIFFS.filter((d) => (counts[d] ?? 0) > availableFor(scope, d));
  if (short.length === 0) return null;
  return short
    .map((d) => `${counts[d]} requested but only ${availableFor(scope, d)} ${d} exist`)
    .join("; ");
}

/**
 * Merge the seed echoed by `POST /tests` back into the body we sent.
 *
 * The runner sends no seed (the server mints one), but `POST /tests/submit`
 * requires `request.seed` — omitting it fails with `seed_required`. The stored
 * body must therefore be the original request plus the echoed seed, never a
 * reconstruction.
 */
export function withEchoedSeed(
  body: FriendlyTestRequest,
  seed: number | null | undefined,
): FriendlyTestRequest {
  return seed === null || seed === undefined ? body : { ...body, seed };
}
