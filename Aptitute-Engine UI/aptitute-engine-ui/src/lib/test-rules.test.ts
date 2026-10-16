import { describe, it, expect } from "vitest";
import type { ChapterInfo, FriendlyTestRequest } from "../types/qme";
import {
  validateTestRequest,
  availableFor,
  feasibilityMessage,
  withEchoedSeed,
  DIFFS,
} from "./test-rules";

const medium = { mode: "single" as const, value: "medium" as const };

function chapter(easy = 0, medium_ = 0, hard = 0): ChapterInfo {
  return {
    key: `Quantitative Aptitude EBook › Ch`,
    label: "Ch",
    question_count: easy + medium_ + hard,
    difficulty_counts: { easy, medium: medium_, hard },
  };
}

describe("count rules", () => {
  it("rejects a count that is not a multiple of 5", () => {
    expect(validateTestRequest(12, medium, true).count).toMatch(/multiple of 5/);
  });

  it("requires >= 10 when a chapter scope is selected", () => {
    expect(validateTestRequest(5, medium, true).count).toMatch(/Minimum 10/);
    expect(validateTestRequest(10, medium, true).count).toBeUndefined();
  });

  it("requires >= 30 when no chapter is selected (all-chapters test)", () => {
    expect(validateTestRequest(10, medium, false).count).toMatch(/Minimum 30/);
    expect(validateTestRequest(30, medium, false).count).toBeUndefined();
  });

  it("accepts 30 for an all-chapters test but rejects 10 — the rule the API enforces", () => {
    // Mirrors the live 422: count_minimum (actual: 10, expected: ">= 30")
    expect(validateTestRequest(10, medium, false).count).toBeDefined();
  });
});

describe("difficulty rules", () => {
  it("requires a value for mode single", () => {
    expect(validateTestRequest(10, { mode: "single" }, true).difficulty).toMatch(/Pick/);
  });

  it("requires mixed counts to sum to the count", () => {
    const e = validateTestRequest(
      10,
      { mode: "mixed", counts: { easy: 5, medium: 3, hard: 2 } },
      true,
    );
    expect(e.difficulty).toBeUndefined();

    const bad = validateTestRequest(
      10,
      { mode: "mixed", counts: { easy: 5, medium: 3, hard: 1 } },
      true,
    );
    expect(bad.difficulty).toMatch(/add up to 9/);
  });

  it("rejects negative counts", () => {
    const e = validateTestRequest(
      10,
      { mode: "mixed", counts: { easy: -1, medium: 11, hard: 0 } },
      true,
    );
    expect(e.difficulty).toMatch(/negative/);
  });

  it("treats a missing difficulty key as 0", () => {
    expect(validateTestRequest(10, { mode: "mixed", counts: { easy: 10 } }, true).difficulty)
      .toBeUndefined();
  });
});

describe("feasibility", () => {
  it("sums difficulty_counts over the scoped chapters, missing key = 0", () => {
    const scope = [chapter(5, 4, 0), chapter(3, 0, 2)];
    expect(availableFor(scope, "easy")).toBe(8);
    expect(availableFor(scope, "medium")).toBe(4);
    expect(availableFor(scope, "hard")).toBe(2);
  });

  it("blocks a single-difficulty request that exceeds supply", () => {
    const scope = [chapter(0, 9, 0)];
    expect(feasibilityMessage(scope, { mode: "single", value: "medium" }, 10))
      .toMatch(/Only 9 medium/);
    expect(feasibilityMessage(scope, { mode: "single", value: "medium" }, 5)).toBeNull();
  });

  it("blocks a mixed request per difficulty and names the shortfall", () => {
    const scope = [chapter(0, 5, 0)];
    const msg = feasibilityMessage(
      scope,
      { mode: "mixed", counts: { easy: 5, medium: 5, hard: 0 } },
      10,
    );
    expect(msg).toMatch(/5 requested but only 0 easy exist/);
  });
});

describe("seed round-trip (the single most common integration mistake)", () => {
  const body: FriendlyTestRequest = {
    count: 10,
    difficulty: { mode: "single", value: "medium" },
    chapters: ["Quantitative Aptitude EBook › Average"],
  };

  it("folds the echoed seed back into the original body", () => {
    const stored = withEchoedSeed(body, 48792822);
    expect(stored.seed).toBe(48792822);
    // Every original field survives untouched — the body is not rebuilt.
    expect(stored.count).toBe(body.count);
    expect(stored.difficulty).toEqual(body.difficulty);
    expect(stored.chapters).toEqual(body.chapters);
  });

  it("leaves the body alone when the server sent no seed", () => {
    expect(withEchoedSeed(body, null)).toBe(body);
    expect(withEchoedSeed(body, undefined)).toBe(body);
  });

  it("does not mutate the original", () => {
    withEchoedSeed(body, 42);
    expect(body.seed).toBeUndefined();
  });

  it("DIFFS covers exactly the three API values", () => {
    expect(DIFFS).toEqual(["easy", "medium", "hard"]);
  });
});
