import { describe, it, expect, beforeAll } from "vitest";
import type { ReactNode } from "react";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";

// localStorage is touched during render by TestResult (report lookup) and by
// useDraft. Vitest runs in the node environment, so provide a minimal stub.
beforeAll(() => {
  const store = new Map<string, string>();
  const stub = {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => void store.set(k, v),
    removeItem: (k: string) => void store.delete(k),
    clear: () => store.clear(),
    key: () => null,
    length: 0,
  };
  if (typeof globalThis.localStorage === "undefined") {
    Object.defineProperty(globalThis, "localStorage", { value: stub, writable: true });
  }
});

import Overview from "./Overview";
import TestSetup from "./TestSetup";
import TestRunner from "./TestRunner";
import TestResult from "./TestResult";
import Practice from "./Practice";
import FormulasIndex from "./FormulasIndex";
import FormulasDetail from "./FormulasDetail";
import Admin from "./Admin";
import AdminBatches from "./Admin/Batches";
import AdminReview from "./Admin/Review";
import AdminMetrics from "./Admin/Metrics";

/** Render one route in isolation and return its markup. */
function render(routePath: string, element: ReactNode, entries = [routePath]): string {
  return renderToStaticMarkup(
    createElement(
      MemoryRouter,
      { initialEntries: entries },
      createElement(
        Routes,
        null,
        createElement(Route, { path: routePath, element }),
      ),
    ),
  );
}

const PAGES: Array<[name: string, path: string, element: ReactNode, entries?: string[]]> = [
  ["Overview", "/", createElement(Overview)],
  ["TestSetup", "/test/new", createElement(TestSetup)],
  ["TestRunner", "/test/run", createElement(TestRunner)],
  ["TestResult", "/test/result", createElement(TestResult)],
  ["Practice", "/practice", createElement(Practice)],
  ["FormulasIndex", "/formulas", createElement(FormulasIndex)],
  [
    "FormulasDetail",
    "/formulas/:chapterKey",
    createElement(FormulasDetail),
    ["/formulas/Quantitative%20Aptitude%20EBook%20%E2%80%BA%20Average"],
  ],
  ["Admin", "/admin", createElement(Admin)],
  ["AdminBatches", "/admin/batches", createElement(AdminBatches)],
  ["AdminReview", "/admin/review", createElement(AdminReview)],
  ["AdminMetrics", "/admin/metrics", createElement(AdminMetrics)],
];

describe("every route renders in isolation (spec §16.2)", () => {
  for (const [name, path, element, entries] of PAGES) {
    it(`${name} renders at ${path}`, () => {
      const html = render(path, element, entries);
      expect(html.length).toBeGreaterThan(0);
      // No leaked error boundary / undefined text.
      expect(html).not.toContain("undefined");
      expect(html).not.toContain("[object Object]");
    });
  }
});

describe("rendered content", () => {
  it("Overview shows its loading skeleton while /bank/meta is in flight", () => {
    const html = render("/", createElement(Overview));
    expect(html).toContain("animate-pulse");
  });

  it("TestRunner shows the draft-restoring skeleton, never a crash", () => {
    const html = render("/test/run", createElement(TestRunner));
    expect(html).toContain("animate-pulse");
  });

  it("TestResult falls back to an explicit empty state with no stored result", () => {
    const html = render("/test/result", createElement(TestResult));
    expect(html).toContain("No saved result");
    expect(html).toContain("Start a test");
  });

  it("Admin surfaces the BLOCKED panel with its exact endpoint, never fake data", () => {
    const html = render("/admin/batches", createElement(AdminBatches));
    expect(html).toContain("/api/v1/batches");
    expect(html).toContain("Not available");
    expect(html).toContain("docs/API_CONTRACTS.md");
  });

  it("Admin Review and Metrics are both BLOCKED", () => {
    expect(render("/admin/review", createElement(AdminReview))).toContain("/review");
    expect(render("/admin/metrics", createElement(AdminMetrics))).toContain("/metrics");
  });
});
