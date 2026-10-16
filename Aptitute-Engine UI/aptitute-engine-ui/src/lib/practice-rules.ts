import type { PracticeRequest } from "../types/qme";

/**
 * Build one page request.
 *
 * The pool is ordered once from `seed` and then sliced, so page N+1 must send
 * back the seed echoed by page N — otherwise the whole pool reshuffles and
 * pages repeat. On the first page (or after a filter change) the seed is
 * omitted so the server mints a fresh one.
 */
export function practiceBody(
  filters: PracticeRequest,
  page: number,
  seed?: number,
): PracticeRequest {
  const body: PracticeRequest = { ...filters, page };
  if (seed !== undefined) body.seed = seed;
  return body;
}

/** Identity of a pool: change any filter (or the seed) and it reshuffles. */
export function poolIdentity(filters: PracticeRequest, seed?: number): string {
  return JSON.stringify([filters, seed ?? null]);
}
