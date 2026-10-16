import { describe, it, expect } from "vitest";
import type { PracticeRequest } from "../types/qme";
import { practiceBody, poolIdentity } from "./practice-rules";

const filters: PracticeRequest = {
  chapter: "Quantitative Aptitude EBook › Average",
  difficulty: "medium",
  mode: "progressive",
};

describe("practice pagination identity", () => {
  it("omits the seed on page 1 so the server mints one", () => {
    const body = practiceBody(filters, 1);
    expect(body.page).toBe(1);
    expect("seed" in body).toBe(false);
  });

  it("echoes the server seed from page 2 onward — pages stay disjoint", () => {
    const page2 = practiceBody(filters, 2, 48792822);
    expect(page2.seed).toBe(48792822);
    expect(page2.page).toBe(2);
    // Filters are carried through unchanged: same pool, next slice.
    expect(page2.chapter).toBe(filters.chapter);
    expect(page2.difficulty).toBe(filters.difficulty);
    expect(page2.mode).toBe(filters.mode);
  });

  it("keeps the same identity for identical filters + seed", () => {
    expect(poolIdentity(filters, 7)).toBe(poolIdentity({ ...filters }, 7));
  });

  it("changes identity when any filter changes", () => {
    expect(poolIdentity(filters, 7)).not.toBe(
      poolIdentity({ ...filters, difficulty: "hard" }, 7),
    );
    expect(poolIdentity(filters, 7)).not.toBe(
      poolIdentity({ ...filters, mode: "mixed" }, 7),
    );
    expect(poolIdentity(filters, 7)).not.toBe(
      poolIdentity({ ...filters, chapter: "Other" }, 7),
    );
  });

  it("changes identity when the seed changes (reshuffle)", () => {
    expect(poolIdentity(filters, 7)).not.toBe(poolIdentity(filters, 8));
    expect(poolIdentity(filters, 7)).not.toBe(poolIdentity(filters, undefined));
  });

  it("does not mutate the filters object it was given", () => {
    const before = JSON.stringify(filters);
    practiceBody(filters, 3, 99);
    expect(JSON.stringify(filters)).toBe(before);
  });
});
