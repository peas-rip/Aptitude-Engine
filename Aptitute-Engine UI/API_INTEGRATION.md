# Aptitude Engine — Frontend API Integration Guide

**Audience:** React / Next.js developers building UI on top of the Question
Metadata Engine (QME) Test & Practice API.

**Backend contract source of truth:** [`docs/API_CONTRACTS.md`](../docs/API_CONTRACTS.md)
§1.7 (Testgen Endpoints) and §4 (Error envelope). This document is derived
from that spec **and** from the implementing code
(`src/qme/api/routes/testgen.py`, `src/qme/api/exceptions.py`,
`src/qme/testgen/*.py`). Where the two ever disagree, the code and
`docs/API_CONTRACTS.md` win.

---

## Table of contents

1. [Overview](#1-overview)
   - [1.1 What exists today](#11-what-exists-today)
   - [1.2 Base URLs & environments](#12-base-urls--environments)
   - [1.3 Authentication](#13-authentication)
   - [1.4 Headers & content type](#14-headers--content-type)
   - [1.5 CORS](#15-cors)
2. [Core concepts](#2-core-concepts)
   - [2.1 Source key](#21-source-key)
   - [2.2 Chapter keys (qualified vs. raw)](#22-chapter-keys-qualified-vs-raw)
   - [2.3 Difficulty](#23-difficulty)
   - [2.4 Seeds & determinism](#24-seeds--determinism)
   - [2.5 Stateless round-trip](#25-stateless-round-trip)
   - [2.6 Knowledge is optional](#26-knowledge-is-optional)
3. [Endpoint reference](#3-endpoint-reference)
   - [3.1 GET /api/v1/health](#31-get-apiv1health)
   - [3.2 GET /api/v1/bank/meta](#32-get-apiv1bankmeta)
   - [3.3 POST /api/v1/tests](#33-post-apiv1tests)
   - [3.4 POST /api/v1/tests/submit](#34-post-apiv1testssubmit)
   - [3.5 POST /api/v1/practice](#35-post-apiv1practice)
   - [3.6 GET /api/v1/chapters/{chapter_key}/knowledge](#36-get-apiv1chapterschapter_keyknowledge)
4. [Data model reference](#4-data-model-reference)
5. [Error handling](#5-error-handling)
6. [Front-end flows](#6-front-end-flows)
7. [React / Next.js examples](#7-react--nextjs-examples)
8. [TypeScript types & API client](#8-typescript-types--api-client)
9. [Gotchas & pre-launch checklist](#9-gotchas--pre-launch-checklist)

---

## 1. Overview

The QME Test & Practice API assembles aptitude tests and practice sets from
a pre-built question bank. It is **deterministic** (same request + same seed
⇒ same result), **stateless** (no server-side session — the client stores
whatever it needs to remember), and **JSON-only** (no file uploads, no file
downloads, no client-supplied server paths).

The API does **not** call an LLM at request time. Responses are fast and
should be treated as ordinary low-latency REST calls — no polling, no job
queues, no streaming.

### 1.1 What exists today

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/health` | Liveness probe (no API key). |
| GET | `/api/v1/bank/meta` | Discovery: sources, qualified chapters, topic list, difficulty counts, knowledge coverage, contract. |
| POST | `/api/v1/tests` | Build a test (two accepted body shapes). |
| POST | `/api/v1/tests/submit` | Score a finished test (round-trip: client resends the original test request). |
| POST | `/api/v1/practice` | One paginated page of a practice pool. |
| GET | `/api/v1/chapters/{chapter_key}/knowledge` | Formulas + shortcut tricks for one chapter, on demand. |

> ⚠️ **Do not build against the other endpoints in `API_CONTRACTS.md`.**
> §1.1–§1.6 — `POST /api/v1/questions/process`, `POST /api/v1/batches`, batch
> status/results, review queue, `GET /api/v1/metrics` — are specified but
> **not implemented in this backend**. Hitting them returns `404`. Only §1.7
> and `/health` are live.

### 1.2 Base URLs & environments

| Environment | Base URL |
|---|---|
| Local dev | `http://localhost:8000` |
| Local dev (Docker) | `http://localhost:8000` (port mapped with `-p 8000:8000`) |
| Staging / production (Railway) | `https://<your-app>.up.railway.app` |

Start the backend locally with:

```bash
make run-api        # uvicorn qme.main:app --reload
# or, if uvicorn is on your PATH:
uvicorn qme.main:app --reload
```

Interactive Swagger UI is served at `{BASE_URL}/docs`, and ReDoc at
`{BASE_URL}/redoc`. Useful for exploration; the schemas in §4 below are the
stable reference for typing your client.

**Putting the base URL behind an env var (Next.js):**

```dotenv
# .env.local — OPTION A (recommended): call through the Next.js proxy (§7.6),
# the API key stays server-side.
NEXT_PUBLIC_QME_BASE_URL=/api/qme
# QME_BASE_URL=http://localhost:8000        # read by the proxy route (server-only)
# QME_API_KEY=dev-key                       # read by the proxy route (server-only)

# .env.local — OPTION B: call the API directly (same-origin, non-browser, or
# dev with the backend exposing CORS). NOTE: baseUrl includes /api/v1.
NEXT_PUBLIC_QME_BASE_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_QME_API_KEY=dev-key
```

Never hard-code the base URL. With Option B the key reaches the browser
bundle, so treat it as a public identifier and never use a production secret
there — prefer Option A.

### 1.3 Authentication

All §1.7 endpoints require the `X-API-Key` header — **except**
`GET /api/v1/health`, which is open (it is the service's health-check path).

```
X-API-Key: <QME_API_KEY>
```

- The key is configured **server-side only** on the backend
  (env var `QME_API_KEY`). The API refuses to boot in `production` without it.
- Missing or wrong key ⇒ `401` with error code `UNAUTHORIZED`.
- In local development the backend may run with an **empty** key — then the
  API is open and the header is ignored (a warning is logged at startup).
  Sending a header in that case is harmless.
- The backend never accepts a file path or credential from a request body;
  the blueprint path is server configuration (`QME_BLUEPRINT_PATH`).

> **How to ship the key from React/Next.js:** if the key must be sent from
> the browser, treat it as a *public* client identifier, not a secret — use a
> `NEXT_PUBLIC_` env var and restrict the backend with CORS / a reverse proxy.
> The robust option is a thin server-side proxy route (e.g.
> `app/api/qme/[...path]/route.ts`) that attaches the key from a
> server-only env var, so it never reaches the client bundle. See §7.6.

### 1.4 Headers & content type

Every request:

```
Content-Type: application/json
X-API-Key: <key>            # omitted only for /health
Accept: application/json
```

Every response body is JSON (`application/json; charset=utf-8`), success or
error. There is no streaming, no file output, and no
`application/x-ndjson` (that format only appears in the unimplemented
§1.4 batch endpoints).

### 1.5 CORS

The backend does not currently ship a CORS middleware. Consequences:

- **Same-origin deployment** (frontend and API behind one host/proxy) works
  with no configuration — this is the recommended shape.
- **Cross-origin browser calls** (e.g. `localhost:3000` →
  `localhost:8000`) will be blocked by the browser until the backend adds
  CORS headers. During local development, run your dev server through a
  proxy: in Next.js use
  [`experimental.proxy`](https://nextjs.org/docs/app/api-reference/config/next-config-js/rewrites)
  or `rewrites()` in `next.config.*`:

  ```js
  // next.config.mjs
  export default {
    async rewrites() {
      return [
        {
          source: "/qme/:path*",
          destination: `${process.env.QME_BASE_URL}/api/v1/:path*`,
        },
      ];
    },
  };
  ```

  Then call `/qme/bank/meta` from the browser — same-origin, no CORS, and the
  `X-API-Key` header can be set from a `NEXT_PUBLIC_` var safely because the
  browser talks only to your own origin.

---

## 2. Core concepts

Read this section before wiring any UI — most integration bugs come from
misunderstanding keys, seeds, and the round-trip rule.

### 2.1 Source key

A **source** is one book/collection in the bank (e.g.
`"Quantitative Aptitude EBook"`, or a future `"TCS NQT"` source).

- The source key is `source.name` **verbatim**, including case and spacing.
- Never re-case, trim, or slugify it — round-trip the value returned by
  `/bank/meta`.
- Sources are discovered at runtime: a new source appears in `/bank/meta`
  the moment its questions exist, with no backend redeploy.

### 2.2 Chapter keys (qualified vs. raw)

The separator is **`" › "`** (space, U+203A single right-pointing angle
quotation mark, space).

| Form | Example | Where it's used |
|---|---|---|
| **Qualified** key | `"Quantitative Aptitude EBook › Percentage, Profit & Loss"` | `POST /tests` `chapters[]`, `PracticeRequest.chapter` (recommended — always unambiguous) |
| **Raw** label | `"Percentage, Profit & Loss"` | Knowledge lookup; legacy `selections[].chapter`; accepted anywhere a qualified key is, **if it matches exactly one source** |

Rules:

- Filters **AND together**: `sources × chapters × difficulty`.
- A chapter's source qualifier is **engine-derived** from the questions —
  upstream data is never altered.
- A raw chapter name that exists under two sources is **ambiguous** and
  rejected with `422 INVALID_INPUT` (`details.ambiguous` lists the qualified
  forms to offer the user). The API never silently merges sources.
- `GET /bank/meta` returns `chapters` as **qualified, sorted** keys — use it
  as your chapter picker's option list.

### 2.3 Difficulty

Exactly three values: `"easy"`, `"medium"`, `"hard"`.

- `/bank/meta` → `difficulties` lists which ones actually exist in the bank.
- Per-chapter availability is at
  `sources[].chapters[].difficulty_counts` — use it to disable impossible
  options in your picker **before** the request fails a feasibility check.

### 2.4 Seeds & determinism

A **seed** is a non-negative integer (< 10⁹) that makes selection
reproducible.

- `seed` is **optional** on `POST /tests` and `POST /practice`. If you omit
  it, the server generates one and **echoes it back** (`test.seed` /
  `PracticeSet.seed`).
- Same seed + same request ⇒ byte-identical questions.
- For `POST /practice`, the response echoes `seed`; reuse it with `page + 1`
  to get the next, disjoint page. Changing *any* filter or the seed reshuffles
  the whole pool.
- Store the seed alongside the request for as long as you may need to
  resubmit (see §2.5).

**UI guidance:** surface "shuffle" as a user action — a new seed, not a new
request shape — and show the seed in dev/test tooling so a failing user
report can be reproduced exactly.

### 2.5 Stateless round-trip

There is **no** `GET /tests/{id}/result`. The flow is:

1. `POST /tests` → you receive `test_id`, `seed`, and the **original request
   body** is yours to keep.
2. The user answers in your UI; **you** store the answers and the timer.
3. On finish, `POST /tests/submit` with:
   - `request`: the **exact** body you sent to `POST /tests`, **including
     `seed`**,
   - `answers`: `{ [question_id]: optionKey }`,
   - `test_id` (optional, for traceability),
   - `elapsed_seconds` (optional, recorded but **not enforced**).

The server **regenerates** the test from `request` (deterministic per seed)
and scores `answers` against it. Submissions are idempotent — resubmitting
the same body returns the same result, so a retry after a network failure is
safe.

If `request` has no `seed` on submit ⇒ `422 INVALID_INPUT`
(`violations[0].rule === "seed_required"`). **This is the single most common
integration mistake.** Keep the request body object, not a derived copy.

### 2.6 Knowledge is optional

Formulas and shortcut tricks may be missing for some chapters/topics:

- Missing knowledge ⇒ `200` with **empty lists**, never an error.
- Unknown chapter ⇒ `404 NOT_FOUND`.
- Gaps are surfaced in `/bank/meta` →
  `knowledge_coverage.missing_chapters`.
- Render "no formulas available yet" gracefully — do not treat it as a
  failure.

---

## 3. Endpoint reference

Unless stated otherwise: base path `/api/v1`, `Content-Type: application/json`,
`X-API-Key` required.

### 3.1 GET /api/v1/health

Liveness probe. **No API key required.** Use it for a "backend reachable?"
banner or to gate the UI from showing an empty picker list.

```
GET /api/v1/health
```

**Response 200**

```json
{
  "status": "ok",
  "version": "0.1.0",
  "environment": "development",
  "openai_configured": false
}
```

| Field | Type | Notes |
|---|---|---|
| `status` | `"ok"` | Present ⇒ process is up. |
| `version` | `string` | Package version of `qme`. |
| `environment` | `string` | e.g. `development`, `production`. |
| `openai_configured` | `boolean` | LLM key presence — informational only; the testgen API never uses it. |

**Notes**
- `openai_configured: false` does **not** mean the test/practice API is
  broken — it never calls an LLM.
- This is the only endpoint that does not answer with the error envelope on
  failure; a non-200 here means the process is down or unreachable.

**Client example**

```ts
export async function ping(): Promise<boolean> {
  try {
    const res = await fetch(`${BASE_URL}/api/v1/health`);
    return res.ok;
  } catch {
    return false; // network error — treat as unreachable
  }
}
```

---

### 3.2 GET /api/v1/bank/meta

Discovery — **call this once on app start** and cache it. It powers every
picker (source → chapter → difficulty) and tells you what is feasible before
the user submits.

```
GET /api/v1/bank/meta
X-API-Key: <key>
```

**Response 200**

```json
{
  "sources": [
    {
      "name": "Quantitative Aptitude EBook",
      "question_count": 1310,
      "chapters": [
        {
          "key": "Quantitative Aptitude EBook › Percentage, Profit & Loss",
          "label": "Percentage, Profit & Loss",
          "question_count": 123,
          "difficulty_counts": { "easy": 52, "medium": 71, "hard": 0 }
        }
      ]
    }
  ],
  "chapters": [
    "Quantitative Aptitude EBook › Average",
    "Quantitative Aptitude EBook › Percentage, Profit & Loss"
  ],
  "topics": ["Average / Replacement Average", "..."],
  "difficulties": ["easy", "hard", "medium"],
  "question_count": 1310,
  "buckets": { "Average": { "Average": { "easy": 4, "medium": 6, "hard": 2 } } },
  "knowledge_coverage": {
    "covered_chapters": ["Average"],
    "missing_chapters": []
  },
  "contract": {
    "required_filters": ["chapter", "topic", "difficulty"],
    "optional_filters": ["question_type", "skills", "source.page"],
    "selection_rules": [
      "Prefer unique question_id per test.",
      "Respect requested chapter/topic/difficulty quotas.",
      "If a requested bucket has fewer questions than requested, return the available count and report shortage.",
      "Do not alter question_text, options, or correct_answer when generating a source-faithful test.",
      "Use knowledge_bank formulas/short_tricks to generate explanations or new questions only when explicitly requested."
    ],
    "output_fields": ["test_id", "questions", "answer_key", "coverage", "timing"]
  }
}
```

**Field guide**

| Field | Type | UI usage |
|---|---|---|
| `sources[].name` | `string` | Source selector option values (verbatim). |
| `sources[].question_count` | `number` | Show "N questions" per source. |
| `sources[].chapters[].key` | `string` | **Qualified** chapter key — value for `chapters[]` / practice `chapter`. |
| `sources[].chapters[].label` | `string` | Display text (raw chapter name). |
| `sources[].chapters[].difficulty_counts` | `{easy?, medium?, hard?}` | Feasibility pre-check: disable a difficulty when its count is `0` or below the requested count. Missing key ⇒ `0`. |
| `chapters` | `string[]` | Flat qualified chapter list (sorted) — use when you need a single chapter dropdown. |
| `topics` | `string[]` | Topic selector values (sorted), used by practice `topic`. |
| `difficulties` | `string[]` | Which difficulty values exist. |
| `question_count` | `number` | Bank size; show in a header/footer. |
| `buckets` | `Record<chapter, Record<topic, Record<difficulty, count>>>` | **Blueprint-verbatim, unqualified chapter names** — aggregate counts only. Prefer `sources[].chapters[].difficulty_counts` for UI feasibility. |
| `knowledge_coverage.covered_chapters` | `string[]` | Chapters that will return formulas. |
| `knowledge_coverage.missing_chapters` | `string[]` | Chapters that return empty lists — badge them "formulas pending". |
| `contract` | `object` | The blueprint's contract, verbatim. Mostly informational; `selection_rules` is human-readable text you can show in a tooltip. |

**Notes**
- The response is derived from the live bank; it hot-reloads when any of the
  three bank files change — **no restart**, and no frontend redeploy either.
- `chapters` (top-level) is sorted; `sources[].chapters[]` is sorted by
  chapter label within each source.
- `difficulties` order is not meaningful (sorted alphabetically in practice)
  — render your own `easy → medium → hard` order.

**Client example**

```ts
const meta = await qme.get<BankMeta>("/bank/meta");
// Build picker options:
const sourceOptions = meta.sources.map((s) => ({ value: s.name, label: s.name }));
const chapterOptions = meta.sources
  .flatMap((s) => s.chapters)
  .map((c) => ({ value: c.key, label: `${c.label}` }));
```

**Errors**

| Status | Code | Typical cause |
|---|---|---|
| 401 | `UNAUTHORIZED` | Missing/wrong `X-API-Key`. |
| 503 | `SERVICE_UNAVAILABLE` | A bank file is missing or violates its contract. `details.issues` is a field-level report — show a "service misconfigured" screen; retrying won't help until an operator fixes the bank. |

---

### 3.3 POST /api/v1/tests

Build a test. **Exactly one of two body shapes per request** — send neither
and you get a schema error; send both and you get
`422 INVALID_INPUT (rule: "single_shape")`.

> **Frontend recommendation:** use the **friendly shape** (`TestSpec`). The
> legacy `selections[]` shape exists for backward compatibility and v1
> semantics; the friendly shape maps cleanly onto a picker UI and enforces
> the friendlier rule table (§3.3.3).

```
POST /api/v1/tests
X-API-Key: <key>
Content-Type: application/json
```

#### 3.3.1 Friendly shape

```json
{
  "title": "Unit Test 3",
  "seed": 42,
  "sources": ["Quantitative Aptitude EBook"],
  "chapters": ["Quantitative Aptitude EBook › Percentage, Profit & Loss"],
  "difficulty": { "mode": "mixed", "counts": { "easy": 10, "medium": 5, "hard": 5 } },
  "count": 20
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `count` | `number` | ✅ | Number of questions. Must be a **multiple of 5** and satisfy the minimums (§3.3.3). |
| `difficulty` | `DifficultySpec` | ✅ | `{ "mode": "single", "value": "easy" \| "medium" \| "hard" }` **or** `{ "mode": "mixed", "counts": { "easy": n, "medium": n, "hard": n } }`. |
| `sources` | `string[]` | ❌ | Omit ⇒ all sources. `[]` ⇒ **error** (`sources_not_empty`), don't send empty arrays. |
| `chapters` | `string[]` | ❌ | Qualified chapter keys (§2.2). Omit ⇒ all chapters (inside `sources`). `[]` ⇒ error. |
| `seed` | `number` | ❌ | Omit and the server generates + echoes one. |
| `title` | `string` | ❌ | Echoed back as `title`. |
| `test_id` | `string` | ❌ | Supply your own id, otherwise the server generates one (`T-YYYYMMDD-HHMMSS-N`). |

Minimal request (20 questions, easy/medium/hard mixed proportionally is
*your* job — the API does not auto-balance):

```json
{ "count": 10, "difficulty": { "mode": "single", "value": "medium" } }
```

#### 3.3.2 Legacy shape

```json
{
  "selections": [
    {
      "count": 10,
      "chapter": "Percentage, Profit & Loss",
      "source": "Quantitative Aptitude EBook",
      "difficulty": "hard"
    }
  ]
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `selections` | `Selection[]` (min 1) | ✅ | Each entry is one bucket query; **results are unioned** (no duplicate `question_id`s). |
| `selections[].count` | `number ≥ 1` | ✅ | **Per-selection** count — v1 semantics, no multiple-of-5/minimum rules. |
| `selections[].source` | `string` | ❌ | **Additive** in this API version. |
| `selections[].chapter` | `string` | ❌ | **Unqualified** here — must match exactly one source, else `422`. |
| `selections[].chapters` | `string[]` | ❌ | Qualified keys (alternative to `chapter`). |
| `selections[].topic` | `string` | ❌ | |
| `selections[].difficulty` | `easy\|medium\|hard` | ❌ | |
| `selections[].question_type` | `string` | ❌ | |
| `selections[].skills` | `string[]` | ❌ | |
| `selections[].page_min` / `page_max` | `number ≥ 1` | ❌ | Source-page range filter. |
| `seed` | `number` | ❌ | Same rules as friendly. |
| `title` / `test_id` | `string` | ❌ | Same rules as friendly. |
| `include_solutions` | `boolean` | ❌ | Default **`true`**. Setting `false` empties `answer_key[].solution_steps` only — `questions[].solution` still ships. |

**Shape discrimination** is by key presence:
`selections` ⇒ legacy; `difficulty` / `count` / `chapters` / `sources` ⇒
friendly; both ⇒ rejected.

#### 3.3.3 Test rules (friendly shape only)

Every violation ⇒ **422 `INVALID_INPUT`** with `details.violations[]` naming
the rule, the actual value, and valid/available options. Nothing is clamped,
rounded, or silently dropped.

| Rule | Value |
|---|---|
| `count_multiple_of_5` | `count % 5 === 0` |
| `count_minimum` | `count >= 10` when `chapters` is **present** |
| `count_minimum` | `count >= 30` when `chapters` is **absent** (all-chapters test) |
| `mixed_counts_sum` | `sum(difficulty.counts) === count` |
| `feasibility` | `sources × chapters × difficulty` must hold **≥ `count`** questions; `details.available_by_difficulty` reports what exists |
| `single_requires_value` | `mode: "single"` must include `value` |
| `mixed_requires_counts` | `mode: "mixed"` must include non-empty `counts` |
| `mixed_unknown_difficulty` | counts keys ⊆ `{easy, medium, hard}` |
| `mixed_negative_count` | all counts `>= 0` |
| `single_shape` | not both `selections` and friendly fields |
| `sources_not_empty` / `chapters_not_empty` | omit the field for "all", don't send `[]` |
| `unknown_source` | `details.expected` lists valid sources |
| `unknown_chapter` / `ambiguous_chapter` | `details.expected` / `details.ambiguous` list the qualified keys |
| `chapter_outside_sources` | chapter must live in the selected sources |

**Pre-validate in the UI** using `/bank/meta` so the user never sees an
error: enforce multiple-of-5 with a step `<input type="number" min="10"
step="5">`, and check
`sum(counts) === count` plus per-difficulty availability from
`difficulty_counts`.

#### 3.3.4 Response

`200` with a `GeneratedTest` (§4.1) — verbatim, never altered.

Key points for UI work:

- `test_id` — echo this back on submit for traceability.
- `seed` — **store the original request body too** (§2.5).
- `questions[]` — the full question objects, **including
  `correct_answer` and `solution`**. You must hide them until reveal; the
  API does not do it for you.
- `answer_key[]` — parallel answer list in `questions[]` order:
  `question_id`, `correct_answer`, `answer_text`, `solution_steps`.
- `coverage.by_chapter` keys are **qualified** chapter keys.
- `selections_applied` — what the server actually ran (compiled form for the
  friendly shape: one `Selection` per difficulty).
- `selection_rules_applied` — the blueprint's human-readable rules.
- `shortages[]` — **should be empty** for a friendly-shape request (a
  shortage fails feasibility up front). Non-empty only possible via the
  legacy shape: render as a warning banner ("8 of 10 hard questions were
  available").
- `notes.overlaps_dropped` — number of duplicate questions removed across
  overlapping legacy selections; show nothing when absent/`0`.
- `contract_source` — provenance of the bank (blueprint filename, schema
  version, bank filenames). Good for a debug/details panel.
- `timing` — `estimated_total_sec` is ideal for seeding your countdown
  timer (still **client-enforced**, see §2.5).

**Example**

```ts
const body = {
  title: "Unit Test 3",
  sources: ["Quantitative Aptitude EBook"],
  chapters: ["Quantitative Aptitude EBook › Percentage, Profit & Loss"],
  difficulty: { mode: "mixed" as const, counts: { easy: 5, medium: 3, hard: 2 } },
  count: 10,
};

const test = await qme.post<GeneratedTest>("/tests", body);

// Persist BOTH for the round-trip:
localStorage.setItem("activeTest", JSON.stringify({ body, test }));
```

**Errors** — see §5; the ones you'll actually hit are `INVALID_INPUT`
(rule/feasibility/unknown key) and `VALIDATION_ERROR` (schema).

---

### 3.4 POST /api/v1/tests/submit

End the test and get the score. **Stateless round-trip**: the server
regenerates the test from your request and scores your answers against it.
There is no `GET .../result` endpoint — the client stores the result.

```
POST /api/v1/tests/submit
X-API-Key: <key>
Content-Type: application/json
```

**Request**

```json
{
  "test_id": "T-20261005-120000-20",
  "request": {
    "title": "Unit Test 3",
    "seed": 42,
    "sources": ["Quantitative Aptitude EBook"],
    "chapters": ["Quantitative Aptitude EBook › Percentage, Profit & Loss"],
    "difficulty": { "mode": "mixed", "counts": { "easy": 5, "medium": 3, "hard": 2 } },
    "count": 10
  },
  "answers": { "p5-1": "B", "p9-3": "C" },
  "elapsed_seconds": 540
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `request` | `object` | ✅ | The **exact** body you POSTed to `/tests`, **including `seed`**. Any shape (friendly or legacy) works. |
| `answers` | `Record<question_id, option_key>` | ❌ (default `{}`) | Only the questions the user actually answered — **unanswered questions are scored as wrong**, they are not skipped from the total. |
| `test_id` | `string` | ❌ | Echoed by `POST /tests`; carried into the result for traceability. Server generates one if omitted. |
| `elapsed_seconds` | `number ≥ 0` | ❌ | **Recorded, never enforced.** Your UI owns the timer and auto-submits on expiry. |

> ⚠️ **`seed` is mandatory in `request`.** If it's missing you get
> `422 INVALID_INPUT` with `violations[0].rule === "seed_required"` and a
> message telling you to send the original body. Store the request object
> verbatim (§2.5) — do not rebuild it from form state.

**Response 200 — `TestResult`**

```json
{
  "test_id": "T-20261005-120000-20",
  "score": { "correct": 7, "total": 10, "percent": 70.0 },
  "by_difficulty": {
    "easy":   { "correct": 4, "total": 5, "percent": 80.0 },
    "medium": { "correct": 3, "total": 3, "percent": 100.0 },
    "hard":   { "correct": 0, "total": 2, "percent": 0.0 }
  },
  "by_chapter": {
    "Quantitative Aptitude EBook › Percentage, Profit & Loss": { "correct": 7, "total": 10, "percent": 70.0 }
  },
  "by_source": {
    "Quantitative Aptitude EBook": { "correct": 7, "total": 10, "percent": 70.0 }
  },
  "elapsed_seconds": 540,
  "results": [
    {
      "question_id": "p5-1",
      "your_answer": "B",
      "correct_answer": "A",
      "answer_text": "24 seconds",
      "is_correct": false,
      "solution_steps": ["Step 1: ...", "Step 2: ..."],
      "difficulty": "hard",
      "chapter": "Quantitative Aptitude EBook › Percentage, Profit & Loss",
      "source": "Quantitative Aptitude EBook"
    }
  ]
}
```

| Field | UI usage |
|---|---|
| `score.percent` | Headline number; `round(correct / total * 100, 1)` server-side. |
| `by_difficulty` / `by_chapter` / `by_source` | Charts. `by_chapter` keys are **qualified** chapter keys; breakups are only emitted for buckets that appear in the test. |
| `results[]` | One entry **per question in the test**, in test order — including unanswered ones (`your_answer: null`). `is_correct` drives right/wrong coloring. |
| `results[].solution_steps` | The walkthrough to reveal (may be empty if `include_solutions: false` was used). |
| `results[].answer_text` | Human-readable correct answer, `null` if the bank omits it. |
| `elapsed_seconds` | What you sent (or `null`). Display "took X min Y s". |

**Notes**
- **Idempotent:** same `request` + same `answers` ⇒ same result. Safe to
  retry a failed submit (network blip) without double-counting.
- An empty `answers` object is valid and scores `0%` against the full test.
- If `request` no longer resolves (unknown chapter/source because the bank
  changed) you get `422 INVALID_INPUT`, not a partial score — show "this
  test could not be re-verified" rather than a silent result.

**Client example**

```ts
type StoredTest = { body: Record<string, unknown>; test: GeneratedTest };

async function submitTest(answers: Record<string, string>, elapsed: number) {
  const stored = JSON.parse(localStorage.getItem("activeTest")!) as StoredTest;
  return qme.post<TestResult>("/tests/submit", {
    test_id: stored.test.test_id,
    request: stored.body,          // ← exact original body, seed included
    answers,
    elapsed_seconds: elapsed,
  });
}
```

---

### 3.5 POST /api/v1/practice

One page of a practice pool. Answers and solutions are **always** included —
practice is self-study, so your UI should reveal immediately rather than
hide.

```
POST /api/v1/practice
X-API-Key: <key>
Content-Type: application/json
```

**Request**

```json
{
  "count": 5,
  "page": 2,
  "seed": 42,
  "source": "Quantitative Aptitude EBook",
  "chapter": "Quantitative Aptitude EBook › Percentage, Profit & Loss",
  "topic": "...",
  "difficulty": "hard",
  "mode": "progressive",
  "include_knowledge": true
}
```

| Field | Type | Default | Notes |
|---|---|---|---|
| `count` | `number ≥ 1` | `10` | Page size. **No** multiple-of-5/minimum rules here. |
| `page` | `number ≥ 1` | `1` | 1-based. Beyond the pool ⇒ `422`. |
| `seed` | `number` | random | **Echoed back** — reuse for the next page. |
| `source` | `string` | all sources | |
| `chapter` | `string` | all chapters | Qualified or raw (§2.2). If qualified, its source **overrides/conflicts-checked** against `source` — a mismatch is a `422`. |
| `topic` | `string` | all topics | |
| `difficulty` | `easy\|medium\|hard` | all | |
| `mode` | `"progressive" \| "mixed"` | `"progressive"` | `progressive` orders easy→hard (still randomized *within* a level by the seed); `mixed` fully shuffles. |
| `include_knowledge` | `boolean` | `true` | `false` skips `topic_knowledge` / `chapter_formula_summary`. |
| `title` / `practice_id` | `string` | generated | |

**Response 200 — `PracticeSet`**

```json
{
  "practice_id": "P-20261005-120000-5",
  "title": null,
  "seed": 42,
  "generated_at": "2026-10-05T12:00:00+00:00",
  "mode": "progressive",
  "filters_applied": {
    "source": "Quantitative Aptitude EBook",
    "chapter": "Percentage, Profit & Loss",
    "topic": "Successive Percentages",
    "difficulty": "hard"
  },
  "questions": [ /* BankQuestion[] — correct_answer + solution included */ ],
  "coverage": { "total": 5, "by_chapter": {}, "by_topic": {}, "by_difficulty": {}, "by_source": {} },
  "timing": { "estimated_total_sec": 420, "avg_per_question_sec": 84, "min_sec": 60, "max_sec": 120 },
  "pagination": { "page": 2, "count": 5, "total": 123, "total_pages": 25, "has_more": true },
  "shortages": [],
  "topic_knowledge": { "Successive Percentages": { "formulas": ["..."], "short_tricks": ["..."] } },
  "chapter_formula_summary": ["..."]
}
```

> `filters_applied` echoes what was **actually applied**, with `chapter`
> resolved to its **raw label** (not the qualified key) and empty filters
> omitted. Useful for a "Showing: …" subtitle.

**Pagination contract (the important part)**

- The pool is **ordered once from `seed`** and sliced — pages are disjoint
  and together cover the whole pool. No repeats across pages.
- Response echoes `seed`. To get the next page, send the **same** body with
  `page: page + 1` and the **same `seed`**.
- Changing *any* filter or the seed reshuffles the pool — page numbers no
  longer mean the same thing.
- A partial last page is normal (`total: 123`, `count: 5` ⇒ page 25 has 3).
- `pagination.total` is the pool size; `has_more` drives the "Load more"
  button. Stop when `has_more === false`.
- Practice **never** reports shortages (`shortages` is always `[]`).

**Gotcha:** if you omit `seed` on page 1 the server invents one — you *must*
send back the echoed `seed` from page 2 onward, or you'll reshuffle and see
duplicates.

```ts
const page1 = await qme.post<PracticeSet>("/practice", { count: 5, chapter });
const page2 = await qme.post<PracticeSet>("/practice", {
  ...sameFilters,
  seed: page1.seed,   // ← echo
  page: 2,
});
```

**Errors**

| Status | Code | Cause |
|---|---|---|
| 422 | `INVALID_INPUT` | `details.filters` = the filters that matched nothing (empty pool); or `page` exceeds `total_pages` (`details = {page, total_pages, total}`); or unknown/conflicting `source`/`chapter` (`details.available.sources` / `details.ambiguous`). |

---

### 3.6 GET /api/v1/chapters/{chapter_key}/knowledge

Formulas + shortcut tricks for one chapter, fetched **on demand** — call it
only when the user asks (a "Formulas" drawer), not on page load.

```
GET /api/v1/chapters/{chapter_key}/knowledge?topic=<name>
X-API-Key: <key>
```

- `chapter_key` — **path segment, must be URL-encoded** (it contains `›`,
  spaces, `&`, etc.). Accepts a qualified key (source part ignored for
  lookup) **or** a raw chapter name. Knowledge is **source-less**: one
  shared pool.
- `topic` — optional query param narrowing to one topic. Omit for all
  topics of the chapter.

```ts
const path = `/chapters/${encodeURIComponent(chapterKey)}/knowledge`;
const k = await qme.get<ChapterKnowledge>(path, { topic: "Successive Percentages" });
// => /chapters/Quantitative%20Aptitude%20EBook%20%E2%80%BA%20Percentage%2C%20Profit%20%26%20Loss/knowledge?topic=...
```

**Response 200**

```json
{
  "chapter": "Percentage, Profit & Loss",
  "topic": null,
  "formula_summary": ["Profit % = (SP - CP) / CP × 100"],
  "topics": {
    "Linear Equations": {
      "formulas": ["a/b = c/d ⟹ ad = bc"],
      "short_tricks": ["If A is x% more than B, B is x·100/(100+x)% less than A"]
    }
  }
}
```

| Field | Notes |
|---|---|
| `chapter` | **Unqualified** chapter name (the source qualifier is stripped). |
| `topic` | Echo of the query param, `null` when omitted. |
| `formula_summary` | Chapter-level summary lines. `[]` when the chapter has no knowledge. |
| `topics` | `{ [topic]: { formulas: string[], short_tricks: string[] } }`. With `?topic=` it contains at most that one topic; an unknown topic yields `{}` (still `200`). |

**Errors**

| Status | Code | Cause |
|---|---|---|
| 200 | — | Chapter exists but has no knowledge ⇒ empty lists (not an error). |
| 404 | `NOT_FOUND` | Chapter does not exist at all. Offer the valid names from `/bank/meta` → `chapters`. |
| 401 | `UNAUTHORIZED` | Missing/wrong key. |

---

## 4. Data model reference

These interfaces are the canonical types for your client — copy them into
`types/qme.ts`. They mirror the Pydantic models in
`src/qme/testgen/schemas.py` exactly (nullability included), so anything
extra the backend later adds is a **non-breaking** addition: keep your
readers tolerant and avoid `exactOptionalPropertyTypes`-style strictness on
response types.

```ts
// ── Enums & primitives ────────────────────────────────────────────────────
export type Difficulty = "easy" | "medium" | "hard";
export type TestMode = "progressive" | "mixed";

/** Chapter separator: " › " (space + U+203A + space). */
export const CHAPTER_SEP = " › ";

// ── Questions (bank records, returned byte-for-byte, never altered) ───────
export interface BankClassification {
  chapter: string;                     // raw chapter label, NOT qualified
  topic: string;
  difficulty: Difficulty;
  difficulty_basis: string | null;
  source_label_basis: string | null;
}

export interface BankAgentMetadata {
  question_type: string;               // e.g. "mcq"
  skills: string[];
  generation_tags: string[];
  recommended_use: string[];
  estimated_time_seconds: number;      // >= 0, drives `timing`
}

export interface BankFinalAnswer {
  option_key: string;                  // e.g. "B"
  option_text: string | null;
}

export interface BankSolution {
  method: string;
  steps: string[];
  final_answer: BankFinalAnswer;
  solution_basis: string | null;
}

export interface BankSource {
  name: string;                        // == source key (verbatim)
  type: string;                        // e.g. "pdf"
  identifier: string | null;
  page: number | null;
  question_id: string | null;
}

export interface BankQuestion {
  question_id: string;                 // globally unique, your answers-map key
  question_text: string;
  options: Record<string, string>;     // { "A": "...", "B": "..." }
  correct_answer: string;              // option key, e.g. "B"
  answer_text: string | null;
  classification: BankClassification;
  agent_metadata: BankAgentMetadata;
  solution: BankSolution;
  formula_refs: string[];
  source: BankSource;
}

// ── Test assembly ─────────────────────────────────────────────────────────
export interface Selection {
  count: number;                       // required, >= 1
  source?: string | null;
  chapter?: string | null;             // legacy: RAW chapter name
  chapters?: string[];                 // friendly scope: QUALIFIED keys
  topic?: string | null;
  difficulty?: Difficulty | null;
  question_type?: string | null;
  skills?: string[];
  page_min?: number | null;
  page_max?: number | null;
}

export interface Shortage {
  selection_index: number;
  requested: number;
  provided: number;
  shortfall: number;
  filters: Record<string, unknown>;
}

export interface Coverage {
  total: number;
  by_chapter: Record<string, number>;  // QUALIFIED chapter keys
  by_topic: Record<string, number>;
  by_difficulty: Record<string, number>;
  by_source: Record<string, number>;
}

export interface Timing {
  estimated_total_sec: number;         // good seed for your countdown
  avg_per_question_sec: number;
  min_sec: number;
  max_sec: number;
}

export interface AnswerKeyEntry {
  question_id: string;
  correct_answer: string;
  answer_text: string | null;
  solution_steps: string[];
}

export interface GeneratedTest {
  test_id: string;
  title: string | null;
  seed: number | null;
  generated_at: string;                // ISO-8601
  contract_source: {
    blueprint: string;
    schema_version: string | number;
    question_bank: string;
    knowledge_bank: string;
  };
  selections_applied: Selection[];     // compiled form for friendly requests
  selection_rules_applied: string[];   // human-readable
  questions: BankQuestion[];
  answer_key: AnswerKeyEntry[];        // parallel to `questions`
  coverage: Coverage;
  timing: Timing;
  shortages: Shortage[];               // empty for friendly-shape requests
  notes: Record<string, unknown>;      // e.g. { overlaps_dropped: 3 }
}

// ── Practice ──────────────────────────────────────────────────────────────
export interface Pagination {
  page: number;                        // >= 1
  count: number;                       // page size
  total: number;                       // full pool size
  total_pages: number;
  has_more: boolean;
}

export interface KnowledgeTerms {
  formulas: string[];
  short_tricks: string[];
}

export interface PracticeSet {
  practice_id: string;
  title: string | null;
  seed: number | null;                 // ECHO — reuse for page+1
  generated_at: string;
  mode: TestMode;
  filters_applied: Record<string, unknown>;
  questions: BankQuestion[];
  coverage: Coverage;
  timing: Timing;
  pagination: Pagination | null;
  shortages: Shortage[];               // always [] for practice
  topic_knowledge: Record<string, KnowledgeTerms>;
  chapter_formula_summary: string[];   // [] unless the page spans one chapter
}

// ── Scoring ───────────────────────────────────────────────────────────────
export interface ScoreBreakup {
  correct: number;
  total: number;
  percent: number;                     // 0..100, 1 decimal
}

export interface ResultLine {
  question_id: string;
  your_answer: string | null;          // null => not answered (counts wrong)
  correct_answer: string;
  answer_text: string | null;
  is_correct: boolean;
  solution_steps: string[];
  difficulty: Difficulty;
  chapter: string;                     // QUALIFIED chapter key
  source: string;
}

export interface TestResult {
  test_id: string;
  score: ScoreBreakup;
  by_difficulty: Partial<Record<Difficulty, ScoreBreakup>>;
  by_chapter: Record<string, ScoreBreakup>;
  by_source: Record<string, ScoreBreakup>;
  elapsed_seconds: number | null;
  results: ResultLine[];               // one per question, in test order
}

// ── Knowledge ─────────────────────────────────────────────────────────────
export interface ChapterKnowledge {
  chapter: string;                     // UNQUALIFIED label
  topic: string | null;
  formula_summary: string[];
  topics: Record<string, KnowledgeTerms>;
}

// ── Discovery (GET /bank/meta) ────────────────────────────────────────────
export interface ChapterInfo {
  key: string;                         // QUALIFIED "Source › Chapter"
  label: string;                       // raw chapter name
  question_count: number;
  difficulty_counts: Partial<Record<Difficulty, number>>; // absent key => 0
}

export interface SourceInfo {
  name: string;                        // source key, verbatim
  question_count: number;
  chapters: ChapterInfo[];
}

export interface KnowledgeCoverage {
  covered_chapters: string[];          // UNQUALIFIED names
  missing_chapters: string[];
}

export interface TestGenerationContract {
  required_filters: string[];
  optional_filters: string[];
  selection_rules: string[];
  output_fields: string[];
}

export interface BankMeta {
  sources: SourceInfo[];
  chapters: string[];                  // qualified, sorted
  topics: string[];                    // sorted
  difficulties: string[];              // only those present
  question_count: number;
  buckets: Record<string, Record<string, Partial<Record<Difficulty, number>>>>;
  knowledge_coverage: KnowledgeCoverage;
  contract: TestGenerationContract;
}
```

### 4.1 Request types

```ts
/** POST /tests — friendly shape (recommended). */
export interface FriendlyTestRequest {
  count: number;                       // required
  difficulty: DifficultySpec;          // required
  sources?: string[];                  // omit = all; [] is an error
  chapters?: string[];                 // omit = all; [] is an error
  seed?: number;                       // omit = server-generated (echoed)
  title?: string;
  test_id?: string;
}

export interface DifficultySpec {
  mode: "single" | "mixed";
  value?: Difficulty;                  // mode: "single"
  counts?: Partial<Record<Difficulty, number>>; // mode: "mixed", sums to count
}

/** POST /tests — legacy shape. Exactly one of the two shapes per body. */
export interface LegacyTestRequest {
  selections: Selection[];             // min length 1
  seed?: number;
  title?: string;
  test_id?: string;
  include_solutions?: boolean;         // default true
}

export type TestRequest = FriendlyTestRequest | LegacyTestRequest;

/** POST /tests/submit */
export interface SubmitRequest {
  request: TestRequest;                // EXACT original body, seed included
  answers?: Record<string, string>;    // question_id => option key
  test_id?: string;
  elapsed_seconds?: number;
}

/** POST /practice */
export interface PracticeRequest {
  count?: number;                      // default 10, >= 1
  page?: number;                       // default 1, >= 1
  seed?: number;                       // echo it for stable pagination
  source?: string;
  chapter?: string;                    // qualified or raw
  topic?: string;
  difficulty?: Difficulty;
  mode?: TestMode;                     // default "progressive"
  include_knowledge?: boolean;         // default true
  title?: string;
  practice_id?: string;
}
```

### 4.2 Conventions to remember

| Convention | Rule |
|---|---|
| Chapter keys | `coverage.by_chapter`, `ResultLine.chapter`, `/bank/meta → chapters` and `ChapterInfo.key` are **qualified**; `BankQuestion.classification.chapter`, `ChapterKnowledge.chapter`, `knowledge_coverage.*`, `buckets` are **raw**. |
| Source names | Always verbatim — compare/round-trip, never normalize. |
| Optional numbers | `difficulty_counts` may omit a level entirely ⇒ treat as `0`. |
| ISO timestamps | `generated_at` is UTC ISO-8601; `new Date(v).toLocaleString()` is safe. |
| Order | `results[]` and `answer_key[]` follow `questions[]` order — index-parallel, but key off `question_id` when joining. |
| Extra fields | Types above are closed for what the backend sends today; ignore unknown keys on read. |

---

## 5. Error handling

### 5.1 The envelope

Every non-2xx response from a §1.7 endpoint follows one shape:

```json
{
  "error": {
    "code": "INVALID_INPUT",
    "message": "test request violates the request rules: count_multiple_of_5 (actual: 12)",
    "details": { "violations": [ ... ] },
    "request_id": "0f1e2d3c-4b5a-6978-8765-43210fedcba9"
  }
}
```

| Field | Type | Notes |
|---|---|---|
| `error.code` | `ErrorCode` | **Branch on this**, not on HTTP status — two statuses carry multiple codes. |
| `error.message` | `string` | Human-readable; also suitable as fallback UI text (English only). |
| `error.details` | `object` | Machine-readable context; shape depends on `code` (§5.3). Always an object, never `null`. |
| `error.request_id` | `string` (UUID) | **Per-response** UUID — surface it in your error UI / logs so a user report can be matched to backend logs. |

> **Not** an error envelope: `404` from an unmatched route (Next.js/
> proxy-level, or FastAPI's default `{"detail":"Not Found"}`) and any
> network/`TypeError: Failed to fetch`. Detect envelope errors by the
> presence of `error.code`.

### 5.2 Status → code

| Status | `error.code` | When | Retry? |
|---|---|---|---|
| 401 | `UNAUTHORIZED` | Missing/incorrect `X-API-Key`. | No — fix the key. |
| 404 | `NOT_FOUND` | Unknown chapter on the knowledge endpoint. | No — fix the key/value. |
| 422 | `VALIDATION_ERROR` | Body failed schema validation (missing/incorrectly-typed fields). `details.fields` lists them. | No — fix the request. |
| 422 | `INVALID_INPUT` | Rule violation, unknown/ambiguous filter, infeasible scope, empty practice pool, page out of range, missing `seed` on submit, both shapes sent. | No — adjust inputs. |
| 422 | `ANSWER_MISMATCH` | Submitted answers don't map onto the regenerated test. | No — resync answers. |
| 503 | `SERVICE_UNAVAILABLE` | Bank file missing or violates its contract. `details.issues` is the field report. | Later — show "temporarily unavailable". |
| 200 (no `error`) | — | Success. | — |

`UNAUTHORIZED`, `SERVICE_UNAVAILABLE`, `NOT_FOUND`, `ANSWER_MISMATCH`
extend the core enum in `docs/API_CONTRACTS.md` §4.

### 5.3 `details` shapes by code

**`VALIDATION_ERROR`** → field-level schema problems:

```ts
{ fields: Array<{ location: string; message: string }> }
// e.g. location: "difficulty", message: "Field required"
//      location: "count", message: "Input should be greater than or equal to 1"
```

**`INVALID_INPUT`** → rule violations. The dominant shape:

```ts
{
  violations?: Array<{
    rule: string;
    actual?: unknown;
    expected?: unknown;
    [k: string]: unknown;    // e.g. conflicting_fields, detail, requested, available
  }>;
  available?: { sources: string[]; chapters: string[] };   // unknown source/chapter
  available_by_difficulty?: Record<Difficulty, number>;    // feasibility failures
  filters?: Record<string, unknown>;                       // empty practice pool
  ambiguous?: string[];                                    // chapter needs qualifying
  page?: number; total_pages?: number; total?: number;     // practice page out of range
}
```

Known `violations[].rule` values (friendly shape + submit):
`count_multiple_of_5`, `count_minimum`, `mixed_counts_sum`,
`single_requires_value`, `mixed_requires_counts`,
`mixed_unknown_difficulty`, `mixed_negative_count`, `single_shape`,
`sources_not_empty`, `chapters_not_empty`, `unknown_source`,
`unknown_chapter`, `ambiguous_chapter`, `chapter_outside_sources`,
`feasibility`, `seed_required`.

**`ANSWER_MISMATCH`** → answers didn't map onto the regenerated test:

```ts
{ unknown_question_ids: string[]; invalid_option_keys: Record<string, string> }
```

**`SERVICE_UNAVAILABLE`** → `{ issues: string[] }` — bank contract report.

**`UNAUTHORIZED` / `NOT_FOUND`** → `{}` (empty object).

### 5.4 Client-side strategy

1. **Normalize transport failures.** No envelope ⇒ network/CORS/proxy
   problem, not a backend error — show a different message ("Can't reach the
   server") than a `503` ("Service unavailable").
2. **One `ApiError` class** (§8) carrying `status`, `code`, `message`,
   `details`, `requestId`.
3. **Map to UX:**
   - `VALIDATION_ERROR` → inline field errors from `details.fields`.
   - `INVALID_INPUT` → banner listing the rules; when `violations[].rule`
     includes `feasibility`, show `available_by_difficulty` ("Only 7 hard
     questions exist in this scope — lower the count").
   - `unknown_source` / `unknown_chapter` / `ambiguous_chapter` → reset the
     picker from `details.available` / `details.ambiguous`.
   - `seed_required` on submit → **a bug in your client**: log loudly, don't
     silently regenerate (the test would be unscoreable).
   - `UNAUTHORIZED` → clear cached key, surface config help; do not loop.
   - `SERVICE_UNAVAILABLE` → full-page "unavailable", include
     `details.issues[0]` and `request_id` for support.
4. **Never auto-retry 422/401.** `200` and `503` are the retry candidates
   (the bank cache self-heals on `503` once files are fixed).
5. **Always log `request_id`** for any error you surface.
6. **Guard against missing envelopes** — `res.ok && isJson(res)` before
   parsing.

---

## 6. Front-end flows

### 6.1 Test-taking journey (the main one)

```
┌────────────┐  GET /bank/meta  ┌──────────────┐
│ App start  │ ───────────────► │  Build picker │
└────────────┘  (cache)         │ src/chap/diff │
                                └──────┬───────┘
                                       │ POST /tests
                                       ▼
                                ┌──────────────┐  persist { body, test }
                                │  Render test │ ───────────────────────┐
                                │ (hide answers)                        │
                                └──────┬───────┘                        │
                                       │ client timer counts down       │
                                       │ (seed = timing.estimated_total)│
                                       ▼                                │
                                ┌──────────────┐                        │
                                │  POST /tests │ ◄── answers + request  │
                                │   /submit    │     (verbatim body)    │
                                └──────┬───────┘                        │
                                       ▼                                │
                                ┌──────────────┐                        │
                                │  Results UI  │  store TestResult      │
                                │  + review    │ ◄──────────────────────┘
                                └──────────────┘
```

**State to persist between screens** (and across a refresh):

```ts
type ActiveTest = {
  body: FriendlyTestRequest | LegacyTestRequest;  // ← the ORIGINAL request
  test: GeneratedTest;                            // ← for rendering
  answers: Record<string, string>;
  startedAt: number;                              // Date.now() at creation
  deadlineAt: number;                             // startedAt + timing.estimated_total_sec*1000
};
```

**Rules**

1. Call `/bank/meta` once per session; use
   `sources[].chapters[].difficulty_counts` to disable infeasible options
   *before* POSTing.
2. Enforce the friendly-shape rules client-side (multiple of 5, minimums,
   mixed sum) — they are deterministic and the API returns `422` otherwise.
3. **Store the raw request body**, not a reconstruction. The submit needs it
   byte-equivalent (especially `seed`).
4. Hide `questions[].correct_answer` and `questions[].solution` while
   rendering; `answer_key[]` is the same information in a convenient order.
5. The countdown is **yours**: initialise from `test.timing.estimated_total_sec`
   (or a user-chosen limit) and auto-submit on expiry with
   `elapsed_seconds` — the server records but never enforces it.
6. On `200`, persist `TestResult` (there is no way to fetch it again) and
   route to the report page. Keep `request + answers` too so the user can
   "review my answers" without resubmitting.
7. Resubmitting identical payloads is idempotent → safe retry on network
   errors.

**Optional: reveal-on-demand review.** If you want a "show solutions" pass
without a second request, use the `solution_steps` already present in
`answer_key[]` / `questions[].solution.steps`.

---

### 6.2 Practice journey

```
pick filters ─► POST /practice {seed?, page:1, count} ─► render page
                      │                                    │  answers +
                      │  ← echo seed, pagination           │  reveal inline
                      ▼                                    ▼
              POST /practice {seed, page:n+1}      user marks "next"
```

1. First request may omit `seed` — **capture the echoed value**.
2. Next page: identical filters + same `seed` + `page + 1`. Changing any
   filter (or the seed) reshuffles — treat filters + seed as one identity
   key; reset to `page: 1` whenever they change.
3. Stop at `pagination.has_more === false`. A short final page is normal.
4. `mode: "progressive"` gives easy→hard ordering (good default);
   `"mixed"` shuffles everything (good for revision).
5. Show `topic_knowledge` and `chapter_formula_summary` as a side panel;
   send `include_knowledge: false` when you won't render it (smaller
   payloads).
6. `chapter_formula_summary` is only populated when the page spans a single
   chapter — don't render an empty section as an error.
7. For a per-question "formulas" button, call
   `GET /chapters/{key}/knowledge?topic=…` lazily (§3.6) and cache in memory.

---

### 6.3 Error-triggering events worth special UI

| Event | Signal | Suggested UI |
|---|---|---|
| Backend reachable but bank broken | 503 `SERVICE_UNAVAILABLE` | Full-page "Service unavailable" + `request_id`. |
| Wrong/missing key | 401 `UNAUTHORIZED` | Config/help screen, stop retrying. |
| Count not multiple of 5 | 422 rule `count_multiple_of_5` | Inline validation on the input. |
| Not enough hard questions | 422 rule `feasibility` | Show `details.available_by_difficulty` and offer lowered counts. |
| Chapter exists in 2 sources | 422 `ambiguous_chapter` | Re-open picker with `details.ambiguous` options. |
| Submit without stored seed | 422 `seed_required` | Client bug — log with `request_id`, show "start the test again". |
| Answers not matching test | 422 `ANSWER_MISMATCH` | "Test changed — please retake", list `unknown_question_ids`. |
| Practice page past the end | 422 with `total_pages` | Clamp to `total_pages` and refetch. |
| Unknown chapter in knowledge call | 404 `NOT_FOUND` | Hide the formulas button (use `/bank/meta.knowledge_coverage` to know in advance). |

---

## 7. React / Next.js examples

> The `qme` client used below is the typed wrapper defined in [§8](#8-typescript-types--api-client).
> Types come from [§4](#4-data-model-reference). Put both in
> `src/lib/` (or `lib/`) and import from there.
>
> These examples assume **App Router** (`app/`) with the proxy from §7.6, so
> the browser only ever talks to your own origin. Client components are marked
> `"use client"`.

### 7.1 Bank meta — fetch once, share everywhere

```tsx
// src/lib/use-bank-meta.ts
"use client";
import useSWR from "swr";
import { qme } from "./qme-client";

export function useBankMeta() {
  const { data, error, isLoading } = useSWR<BankMeta>(
    "bank/meta",                       // cache key
    () => qme.get<BankMeta>("/bank/meta"),
    { revalidateOnFocus: false, staleTime: 10 * 60 * 1000 }
  );
  return { meta: data, loading: isLoading, error };
}
```

`BankMeta` changes only when the backend's bank files change — a long
`staleTime` (10 min) is appropriate. If you don't use SWR/React Query, cache
in module scope or `useEffect` + `useState`.

### 7.2 Test setup picker (feasibility-aware)

```tsx
"use client";
import { useState } from "react";
import { useBankMeta } from "./use-bank-meta";

export function TestPicker({ onStart }: { onStart: (b: FriendlyTestRequest) => void }) {
  const { meta, loading, error } = useBankMeta();
  const [source, setSource] = useState<string>("");
  const [chapter, setChapter] = useState<string>("");
  const [difficulty, setDifficulty] = useState<Difficulty>("medium");
  const [count, setCount] = useState(10);

  if (loading) return <p>Loading question bank…</p>;
  if (error)   return <p>Could not reach the question bank.</p>;
  if (!meta)   return null;

  const chapters = (meta.sources.find((s) => s.name === source)?.chapters) ?? [];
  const chapterInfo = chapters.find((c) => c.key === chapter);
  const available = chapterInfo?.difficulty_counts[difficulty] ?? 0;

  // Friendly-shape rules, enforced before we ever POST.
  const countValid = count % 5 === 0 && count >= 10;
  const feasible = count <= available;
  const canStart = countValid && feasible && chapter !== "";

  return (
    <div>
      <select value={source} onChange={(e) => { setSource(e.target.value); setChapter(""); }}>
        <option value="">All sources</option>
        {meta.sources.map((s) => (
          <option key={s.name} value={s.name}>{s.name} ({s.question_count})</option>
        ))}
      </select>

      <select value={chapter} onChange={(e) => setChapter(e.target.value)}>
        <option value="">All chapters</option>
        {chapters.map((c) => (
          <option key={c.key} value={c.key}>
            {c.label} — {c.question_count}q
          </option>
        ))}
      </select>

      <select value={difficulty} onChange={(e) => setDifficulty(e.target.value as Difficulty)}>
        {(meta.difficulties as Difficulty[]).map((d) => (
          <option key={d} value={d}>
            {d} ({chapterInfo?.difficulty_counts[d] ?? 0})
          </option>
        ))}
      </select>

      <input
        type="number" min={10} step={5} value={count}
        onChange={(e) => setCount(Number(e.target.value))}
      />
      {!countValid && <p role="alert">Count must be a multiple of 5 (min 10).</p>}
      {countValid && !feasible && (
        <p role="alert">Only {available} {difficulty} questions in this scope.</p>
      )}

      <button
        disabled={!canStart}
        onClick={() => onStart({
          sources: source ? [source] : undefined,
          chapters: chapter ? [chapter] : undefined,
          difficulty: { mode: "single", value: difficulty },
          count,
        })}
      >
        Start test
      </button>
    </div>
  );
}
```

### 7.3 Taking a test (create → answer → submit)

```tsx
"use client";
import { useEffect, useState } from "react";
import { qme } from "./qme-client";

const STORAGE = "qme.activeTest";

type ActiveTest = {
  body: FriendlyTestRequest;
  test: GeneratedTest;
  answers: Record<string, string>;
  startedAt: number;
};

export function TestRunner({ body }: { body: FriendlyTestRequest }) {
  const [active, setActive] = useState<ActiveTest | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [result, setResult] = useState<TestResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [left, setLeft] = useState<number | null>(null);

  // 1. create
  useEffect(() => {
    qme.post<GeneratedTest>("/tests", body).then((test) => {
      setActive({ body, test, answers: {}, startedAt: Date.now() });
      setLeft(test.timing.estimated_total_sec);
    }).catch((e: ApiError) => { /* show e.message + e.requestId (§5) */ });
  }, [body]);

  // 2. client-owned countdown; auto-submit on expiry
  useEffect(() => {
    if (!active || left === null || left <= 0) return;
    const t = setTimeout(() => setLeft((s) => (s ?? 1) - 1), 1000);
    return () => clearTimeout(t);
  }, [active, left]);

  useEffect(() => {
    if (left !== null && left <= 0 && active && !busy) void finish();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [left]);

  // 3. submit — send the ORIGINAL body + answers
  async function finish() {
    if (!active) return;
    setBusy(true);
    try {
      const res = await qme.post<TestResult>("/tests/submit", {
        test_id: active.test.test_id,
        request: active.body,     // ← verbatim, seed included
        answers,
        elapsed_seconds: Math.round((Date.now() - active.startedAt) / 1000),
      });
      setResult(res);
      localStorage.removeItem(STORAGE);
    } finally {
      setBusy(false);
    }
  }

  if (result) return <Report result={result} />;

  return (
    <main>
      {left !== null && <div aria-live="polite">{Math.floor(left / 60)}:{String(left % 60).padStart(2, "0")}</div>}

      {active?.test.questions.map((q, i) => (
        <section key={q.question_id}>
          <p>{i + 1}. {q.question_text}</p>
          {/* Never render q.correct_answer / q.solution here. */}
          {Object.entries(q.options).map(([key, text]) => (
            <label key={key}>
              <input
                type="radio"
                name={q.question_id}
                checked={answers[q.question_id] === key}
                onChange={() => setAnswers((a) => ({ ...a, [q.question_id]: key }))}
              />
              {key}. {text}
            </label>
          ))}
        </section>
      ))}

      <button onClick={() => void finish()} disabled={busy}>
        {busy ? "Submitting…" : "Submit"}
      </button>
      <p>{Object.keys(answers).length} / {active?.test.questions.length} answered</p>
    </main>
  );
}
```

> Persist `active` (e.g. `sessionStorage`, see `STORAGE`) if you want
> refresh-survival; on reload, restore `body` + `test` and **do not** re-POST
> `/tests` (a new `seed` would silently replace the test).

### 7.4 Results report

```tsx
function Report({ result }: { result: TestResult }) {
  return (
    <div>
      <h1>{result.score.correct}/{result.score.total} — {result.score.percent}%</h1>

      {Object.entries(result.by_chapter).map(([chapter, s]) => (
        <div key={chapter}>{chapter}: {s.correct}/{s.total} ({s.percent}%)</div>
      ))}

      {result.results.map((r) => (
        <details key={r.question_id} open={!r.is_correct}>
          <summary>{r.is_correct ? "✓" : "✗"} {r.question_id} — {r.difficulty}</summary>
          <p>You: {r.your_answer ?? "not answered"} · Correct: {r.correct_answer}
             {r.answer_text ? ` (${r.answer_text})` : ""}</p>
          <ol>{r.solution_steps.map((s, i) => <li key={i}>{s}</li>)}</ol>
        </details>
      ))}
    </div>
  );
}
```

### 7.5 Practice with pagination

```tsx
"use client";
import { useState } from "react";

export function Practice({ chapter }: { chapter: string }) {
  const [page, setPage] = useState(1);
  const [seed, setSeed] = useState<number | undefined>(undefined);
  const [set, setSet] = useState<PracticeSet | null>(null);

  async function load(nextPage: number, nextSeed?: number) {
    const res = await qme.post<PracticeSet>("/practice", {
      chapter, count: 5, page: nextPage, seed: nextSeed,
    });
    setSet(res);
    setPage(nextPage);
    setSeed(res.seed ?? undefined);   // echo for the next page
  }

  return (
    <div>
      {set?.questions.map((q) => (
        <article key={q.question_id}>
          <p>{q.question_text}</p>
          <p>Answer: {q.correct_answer} — {q.solution.steps[0]}</p>
        </article>
      ))}

      <button disabled={page <= 1} onClick={() => void load(page - 1, seed)}>Prev</button>
      <button disabled={!set?.pagination?.has_more} onClick={() => void load(page + 1, seed)}>Next</button>
      {set && <span>Page {set.pagination?.page} of {set.pagination?.total_pages}</span>}
    </div>
  );
}
```

> Changing `chapter` must reset `seed` and `page` to `undefined`/`1` —
> otherwise you slice a pool that no longer matches your filters.

### 7.6 Keeping the API key server-side (recommended)

```ts
// app/api/qme/[...path]/route.ts  (App Router, Node runtime)
export async function GET(req: Request, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  const url = new URL(req.url);
  const target = `${process.env.QME_BASE_URL}/api/v1/${path.join("/")}${url.search}`;

  const res = await fetch(target, {
    headers: { "X-API-Key": process.env.QME_API_KEY ?? "" },
    cache: "no-store",
  });
  return new Response(res.body, { status: res.status, headers: { "content-type": "application/json" } });
}
export const POST = GET;   // same forwarding; add PUT/PATCH/DELETE if ever needed
```

Then configure the client's `baseUrl` to `/api/qme` and the key to `""`
(never sent — the proxy adds it). The secret never enters the browser bundle.

⚠️ A proxy like this must not become an open relay: it only forwards to
your configured `QME_BASE_URL`, and you should still restrict who can reach
your Next.js origin (middleware auth / rate limiting).

---

## 8. TypeScript types & API client

Types live in [§4](#4-data-model-reference) (`types/qme.ts`). The client
below is framework-agnostic — works with React, Next.js, Vue, or plain
TS. Save as `src/lib/qme-client.ts`.

```ts
/**
 * Typed client for the QME Test & Practice API (API_CONTRACTS §1.7).
 *
 *   const qme = new QmeClient({ baseUrl: "/api/qme" }); // via Next.js proxy
 *   const meta = await qme.get<BankMeta>("/bank/meta");
 */

export type ErrorCode =
  | "UNAUTHORIZED"
  | "VALIDATION_ERROR"
  | "INVALID_INPUT"
  | "ANSWER_MISMATCH"
  | "NOT_FOUND"
  | "SERVICE_UNAVAILABLE"
  | "NETWORK_ERROR"   // local — transport failure, no envelope
  | "UNKNOWN_ERROR";  // local — non-envelope non-2xx (e.g. proxy 404)

export interface ErrorEnvelope {
  error: {
    code: string;
    message: string;
    details: Record<string, unknown>;
    request_id: string;
  };
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: ErrorCode;
  readonly details: Record<string, unknown>;
  readonly requestId?: string;

  constructor(
    status: number,
    code: ErrorCode,
    message: string,
    details: Record<string, unknown> = {},
    requestId?: string,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
    this.requestId = requestId;
  }

  /** Rule violations from an INVALID_INPUT response, if present. */
  get violations(): Array<{ rule: string; actual?: unknown; expected?: unknown }> {
    const v = this.details.violations;
    return Array.isArray(v) ? (v as Array<{ rule: string }>) : [];
  }

  /** Field errors from a VALIDATION_ERROR response, if present. */
  get fields(): Array<{ location: string; message: string }> {
    const f = this.details.fields;
    return Array.isArray(f) ? (f as Array<{ location: string; message: string }>) : [];
  }
}

const KNOWN_CODES = new Set<string>([
  "UNAUTHORIZED", "VALIDATION_ERROR", "INVALID_INPUT",
  "ANSWER_MISMATCH", "NOT_FOUND", "SERVICE_UNAVAILABLE",
]);

export interface QmeClientOptions {
  /** API root INCLUDING /api/v1, or a proxy prefix that forwards to it. */
  baseUrl: string;
  apiKey?: string;             // omit when a server-side proxy injects it
  fetchImpl?: typeof fetch;    // injectable for tests / interceptors
  timeoutMs?: number;          // default 15000
  onRequestId?: (id: string) => void;  // hook for logging/telemetry
}

export class QmeClient {
  private readonly baseUrl: string;
  private readonly apiKey?: string;
  private readonly fetchImpl: typeof fetch;
  private readonly timeoutMs: number;
  private readonly onRequestId?: (id: string) => void;

  constructor(opts: QmeClientOptions) {
    this.baseUrl = opts.baseUrl.replace(/\/+$/, "");
    this.apiKey = opts.apiKey;
    this.fetchImpl = opts.fetchImpl ?? fetch;
    this.timeoutMs = opts.timeoutMs ?? 15_000;
    this.onRequestId = opts.onRequestId;
  }

  get<T>(path: string, query?: Record<string, string | number | boolean | undefined>): Promise<T> {
    return this.request<T>(path, { method: "GET" }, query);
  }

  post<T>(path: string, body?: unknown, query?: Record<string, string | number | boolean | undefined>): Promise<T> {
    return this.request<T>(path, { method: "POST", body }, query);
  }

  private async request<T>(
    path: string,
    init: { method: string; body?: unknown },
    query?: Record<string, string | number | boolean | undefined>,
  ): Promise<T> {
    const qs = query
      ? new URLSearchParams(
          Object.entries(query)
            .filter(([, v]) => v !== undefined && v !== "")
            .map(([k, v]) => [k, String(v)] as [string, string]),
        ).toString()
      : "";

    const url = `${this.baseUrl}${path.startsWith("/") ? path : `/${path}`}${qs ? `?${qs}` : ""}`;

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.timeoutMs);

    let res: Response;
    try {
      res = await this.fetchImpl(url, {
        method: init.method,
        signal: controller.signal,
        headers: {
          Accept: "application/json",
          ...(init.body !== undefined ? { "Content-Type": "application/json" } : {}),
          ...(this.apiKey ? { "X-API-Key": this.apiKey } : {}),
        },
        body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
      });
    } catch (cause) {
      // No HTTP response at all: network failure, CORS, or abort.
      const aborted = cause instanceof DOMException && cause.name === "AbortError";
      throw new ApiError(
        0,
        "NETWORK_ERROR",
        aborted ? `Request timed out after ${this.timeoutMs}ms` : "Network request failed",
        { url, cause: String(cause) },
      );
    } finally {
      clearTimeout(timeout);
    }

    // 204 / empty body safety
    const text = await res.text();
    let payload: unknown = undefined;
    if (text) {
      try {
        payload = JSON.parse(text);
      } catch {
        /* non-JSON body — fall through to the generic handler */
      }
    }

    if (res.ok) return payload as T;

    const envelope = payload as Partial<ErrorEnvelope> | undefined;
    if (envelope && typeof envelope.error?.code === "string") {
      const { code, message, details, request_id } = envelope.error;
      this.onRequestId?.(request_id);
      throw new ApiError(
        res.status,
        (KNOWN_CODES.has(code) ? code : "UNKNOWN_ERROR") as ErrorCode,
        message,
        details ?? {},
        request_id,
      );
    }

    // Not our envelope (proxy/nginx/404 from a wrong path).
    throw new ApiError(
      res.status,
      res.status === 401 ? "UNAUTHORIZED" : "UNKNOWN_ERROR",
      text ? `HTTP ${res.status}: ${text.slice(0, 200)}` : `HTTP ${res.status}`,
      { url },
    );
  }
}

/** App-wide singleton — configure once, import everywhere. */
export const qme = new QmeClient({
  // With the Next.js proxy (§7.6): baseUrl "/api/qme", no key in the browser.
  // Without a proxy (same-origin or non-browser): full API root INCLUDING /api/v1.
  baseUrl:
    (typeof process !== "undefined" && process.env.NEXT_PUBLIC_QME_BASE_URL) || "/api/qme",
  apiKey:
    (typeof process !== "undefined" && process.env.NEXT_PUBLIC_QME_API_KEY) || undefined,
  timeoutMs: 15_000,
  onRequestId: (id) => console.debug("[qme] request_id", id),
});
```

### 8.1 Domain helpers (optional sugar)

```ts
// src/lib/qme-api.ts
import { qme } from "./qme-client";
import type {
  BankMeta, GeneratedTest, TestResult, PracticeSet, ChapterKnowledge,
  FriendlyTestRequest, LegacyTestRequest, SubmitRequest, PracticeRequest,
} from "./types/qme";

export const api = {
  meta: () => qme.get<BankMeta>("/bank/meta"),

  createTest: (body: FriendlyTestRequest | LegacyTestRequest) =>
    qme.post<GeneratedTest>("/tests", body),

  submitTest: (body: SubmitRequest) => qme.post<TestResult>("/tests/submit", body),

  practice: (body: PracticeRequest) => qme.post<PracticeSet>("/practice", body),

  /** Next page helper: same filters, echoed seed, page + 1. */
  nextPage: (body: PracticeRequest, current: PracticeSet) =>
    qme.post<PracticeSet>("/practice", {
      ...body,
      seed: current.seed ?? undefined,
      page: (current.pagination?.page ?? 1) + 1,
    }),

  knowledge: (chapterKey: string, topic?: string) =>
    qme.get<ChapterKnowledge>(
      `/chapters/${encodeURIComponent(chapterKey)}/knowledge`,
      topic ? { topic } : undefined,
    ),

  health: () => qme.get<{ status: string; version: string }>("/health"),
};
```

### 8.2 A tiny `useAsync` for React

```tsx
"use client";
import { useCallback, useState } from "react";
import { ApiError } from "./qme-client";

export function useAsync<TArgs extends unknown[], TResult>(
  fn: (...args: TArgs) => Promise<TResult>,
) {
  const [data, setData] = useState<TResult | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(false);

  const run = useCallback(async (...args: TArgs) => {
    setLoading(true);
    setError(null);
    try {
      const r = await fn(...args);
      setData(r);
      return r;
    } catch (e) {
      const err =
        e instanceof ApiError ? e : new ApiError(0, "UNKNOWN_ERROR", String(e));
      setError(err);
      return undefined as unknown as TResult;
    } finally {
      setLoading(false);
    }
  }, [fn]);

  return { data, error, loading, run };
}

// Usage
const { data: meta, error, loading, run } = useAsync(() => api.meta());
useEffect(() => { void run(); }, [run]);

if (error) return <ErrorBanner code={error.code} requestId={error.requestId} />;
```

---

## 9. Gotchas & pre-launch checklist

### 9.1 Gotchas (read twice)

| # | Gotcha | Why it bites |
|---|---|---|
| 1 | **Store the original `POST /tests` body.** | `submit.request` must include `seed`. Rebuilding the body from form state loses it ⇒ `422 INVALID_INPUT (seed_required)` and the test can't be scored. |
| 2 | **There is no `GET` for results.** | `TestResult` exists only in the submit response. Persist it; you cannot refetch. |
| 3 | **The timer is client-side only.** | `elapsed_seconds` is recorded, never enforced. Auto-submit on expiry yourself. |
| 4 | **Answers and solutions ship in every test response.** | `questions[].correct_answer`, `questions[].solution`, and `answer_key[]` are all present at creation time. Hide them in the render path or the user can cheat from devtools — the API offers no "answer-free" mode. |
| 5 | **` › ` is U+203A, not `>` or `>>`.** | Build the qualified key from `ChapterInfo.key`, never by string surgery on user input. Always `encodeURIComponent` it in a path. |
| 6 | **Two different "chapter" fields.** | `classification.chapter` is raw; `coverage.by_chapter` / `ResultLine.chapter` / `/bank/meta.chapters` are qualified. Mixing them breaks grouping and joins. |
| 7 | **Omit ≠ empty array.** | `sources: []` and `chapters: []` are errors — send the field only when you mean "some". |
| 8 | **Practice `seed` must be echoed.** | Omit it on page 2 and the pool reshuffles ⇒ duplicate/missing questions. Reset `seed` + `page` whenever filters change. |
| 9 | **Feasibility fails before assembly.** | Requesting more `hard` questions than exist in scope is a `422`, not a partial test. Pre-check with `difficulty_counts`. |
| 10 | **All-chapters tests need ≥ 30.** | With `chapters` absent the minimum is 30; with any explicit chapter scope it's 10. Both must be multiples of 5. |
| 11 | **Two body shapes, never both.** | `selections` vs `difficulty`/`count`/`chapters`/`sources`. Sending both ⇒ `single_shape` error. |
| 12 | **503 = bank problem, not your bug.** | `details.issues` lists file-level violations; retry later, log `request_id`. |
| 13 | **CORS isn't configured server-side.** | Cross-origin browser calls fail until you use the proxy (§7.6) or the backend adds headers. |
| 14 | **Health is the only keyless route.** | And the only one that doesn't use the error envelope. |
| 15 | **Solutions are in the answer key.** | `include_solutions: false` (legacy shape only — the friendly shape has no such field) empties `answer_key[].solution_steps` but **not** `questions[].solution` — it is not a secrecy switch. |
| 16 | **§1.1–§1.6 endpoints don't exist.** | `/questions/process`, `/batches`, `/metrics` return 404. Don't plan features around them. |

### 9.2 Integration checklist

**Setup**
- [ ] Base URL + API key read from env (Option A proxy, §7.6, for production)
- [ ] `GET /health` reachable; UI shows a clear state when it isn't
- [ ] `GET /bank/meta` fetched once, cached (`staleTime` ≥ 10 min)
- [ ] Swagger UI (`/docs`) sanity-checked against these types

**Test creation**
- [ ] Source / chapter / difficulty pickers populated from `meta.sources[]`
- [ ] `difficulty_counts` disables infeasible combinations
- [ ] Count input enforces multiple of 5 and the correct minimum (10 / 30)
- [ ] Mixed mode: `sum(counts) === count` validated inline
- [ ] Empty arrays never sent for `sources` / `chapters`
- [ ] Server-side `422 INVALID_INPUT` rendered as a readable message, including `request_id`
- [ ] Original request body persisted with `seed`

**Taking the test**
- [ ] `correct_answer` / `solution` never rendered pre-submit
- [ ] Answers keyed by `question_id`, values are option keys
- [ ] Timer seeded from `test.timing.estimated_total_sec`, auto-submits
- [ ] Unanswered questions still counted (total = all questions)
- [ ] Refresh mid-test restores state without re-POSTing `/tests`

**Submit & report**
- [ ] `request` sent verbatim (shape + `seed` intact)
- [ ] `test_id` echoed; `elapsed_seconds` sent from `startedAt`
- [ ] Network errors retried (idempotent); 422/401 not retried
- [ ] `TestResult` persisted before routing to the report
- [ ] Score + `by_difficulty`/`by_chapter` charts render (note qualified keys)
- [ ] `results[].your_answer === null` rendered as "not answered"

**Practice**
- [ ] Echoed `seed` reused for `page + 1`
- [ ] Filter change resets `seed` and `page`
- [ ] `has_more === false` disables Next; partial last page handled
- [ ] `topic_knowledge` / `chapter_formula_summary` degrade gracefully when empty

**Knowledge**
- [ ] `encodeURIComponent(chapter_key)` in the path
- [ ] Lazy-loaded on user action, results cached
- [ ] Empty lists shown as "formulas pending" (check `knowledge_coverage`)
- [ ] 404 handled by hiding/disabling the button

**Errors & observability**
- [ ] Single `ApiError` type; branching on `error.code`, not status
- [ ] Envelope-less failures (CORS/network/proxy 404) surfaced distinctly
- [ ] `error.request_id` logged and shown on fatal screens
- [ ] 503 shows a "temporarily unavailable" screen, not a crash
- [ ] 401 does not retry-loop

### 9.3 Quick smoke test

With the backend on `localhost:8000` and a key set:

```bash
BASE=http://localhost:8000
KEY=dev-key

curl -s $BASE/api/v1/health
curl -s -H "X-API-Key: $KEY" $BASE/api/v1/bank/meta | head -c 400

# friendly shape
curl -s -X POST -H "X-API-Key: $KEY" -H 'Content-Type: application/json' \
  -d '{"seed":42,"count":10,"difficulty":{"mode":"single","value":"medium"}}' \
  $BASE/api/v1/tests > test.json

# round-trip: echo the SAME body, with seed intact
curl -s -X POST -H "X-API-Key: $KEY" -H 'Content-Type: application/json' \
  -d "{\"request\":{\"seed\":42,\"count\":10,\"difficulty\":{\"mode\":\"single\",\"value\":\"medium\"}},\"answers\":{}}" \
  $BASE/api/v1/tests/submit
```

Expected: `200` for health/meta/tests; `submit` returns `score: 0` with
`results.length === 10` (empty `answers` ⇒ everything wrong, by design).

---

## Appendix — Where things live in the backend

| Topic | File |
|---|---|
| Route definitions (health, meta, tests, submit, practice, knowledge) | `src/qme/api/routes/testgen.py`, `src/qme/main.py` |
| Error envelope + status mapping | `src/qme/api/exceptions.py` |
| Request/response Pydantic models (source of truth for §4) | `src/qme/testgen/schemas.py` |
| Friendly-shape rules & shape discrimination | `src/qme/testgen/spec.py` |
| Scoring (`TestResult` construction) | `src/qme/testgen/scoring.py` |
| Practice pagination & determinism | `src/qme/testgen/practice.py` |
| Test assembly (shortages, notes) | `src/qme/testgen/assembler.py` |
| Bank loading / contract errors | `src/qme/testgen/bank.py` |
| API key + blueprint path settings | `src/qme/config/settings.py` (`QME_API_KEY`, `QME_BLUEPRINT_PATH`) |
| Normative contract | `docs/API_CONTRACTS.md` §1.7, §4 |
