# Aptitude Engine UI — Frontend Design Specification

**Status:** Build specification · v1.0 · 2026-10-16
**Audience:** The frontend agent (or developer) implementing this UI.
**Authority:** This file is the design contract for the UI. API field-level
reference lives in [`API_INTEGRATION.md`](./API_INTEGRATION.md) (do not
duplicate it here). Where this spec and the backend disagree, **the backend
and `docs/API_CONTRACTS.md` win** — raise it as a spec bug.

**How to use this document**

- Read §2, §7 and §15 before writing any code.
- Build **P0 first** (§15). Do not start P1 until §16 P0 checklist passes.
- Status legend used throughout:

| Marker | Meaning |
|---|---|
| `AVAILABLE` | Buildable today against live endpoints. |
| `BLOCKED` | Designed, but requires backend endpoints that **do not exist**. Ship the route shell + types only; never fake data. |
| `FUTURE` | Depends on unimplemented non-API work (packaging, licensing). |

---

## 1. Purpose and scope

### 1.1 Purpose

Deliver a **formal, efficient, bloat-free web UI** over the QME
Test & Practice API so a user can: configure a test, take it under a timer,
get a scored report, practice questions in pages, and read formulas for a
chapter.

### 1.2 In scope

| Area | Detail |
|---|---|
| Test flow | Setup (discovery-driven) → timed runner → submit → scored report. |
| Practice flow | Filtered, paginated practice with inline reveal. |
| Knowledge flow | Formulas / shortcut-tricks viewer per chapter or topic. |
| Bank overview | Coverage, difficulty distribution, knowledge gaps (read-only). |
| Admin shell | **`BLOCKED`** — batch/ingest/review/metrics screens designed and routed, types only, no fabricated data. |
| Cross-cutting | Error envelope handling, loading/empty states, keyboard access, responsive layout, offline draft persistence. |

### 1.3 Out of scope

- **Any LLM-driven feature** in the browser (classification, difficulty
  scoring, solution generation) — these live server-side and are not exposed
  over HTTP (§2.3).
- **Server-side persistence** of test results, drafts or history — the API
  is stateless; the client owns state (§5).
- **Authentication UI for a user account system** — there is none. The
  backend authenticates with an `X-API-Key` header injected by config/proxy,
  not by a login screen.
- **Activation / licensing screen** — `FUTURE`; the license endpoints are
  not specified or implemented (§17).
- **Payments, multi-tenancy, student accounts, leaderboard** — out of
  product scope entirely (`docs/PRD.md` §5).

### 1.4 Non-goals for the design

- No decorative dashboard aesthetic. This is a study tool: dense where it
  helps (results, coverage), quiet everywhere else.
- No animations that delay a common action. Motion is limited to
  state-change feedback (§9.7).
- No speculative features with no data source behind them.

---

## 2. Repository and stack findings

*All items below were observed in the repository, not assumed.*

### 2.1 What exists

| Finding | Evidence |
|---|---|
| **No frontend exists.** No `package.json`, `tsconfig.json`, `vite.config.*`, `next.config.*`, `tailwind.config.*`, or any `.tsx`/`.jsx` anywhere in the repo. | repository-wide glob search |
| Backend: Python 3.11, FastAPI app factory | `src/qme/main.py:18` |
| App mounts **one** router (testgen) + health | `src/qme/main.py:39-49` |
| API key dependency on the whole testgen router | `src/qme/api/routes/testgen.py:45` (`_require_api_key`), applied at `:105-109` |
| Error envelope handlers registered app-wide | `src/qme/api/exceptions.py:41` (`register_exception_handlers`) |
| **No CORS middleware** — `create_app()` adds only exception handlers and the router | `src/qme/main.py:30-49` |
| Settings are env-driven; blueprint path is server config only | `src/qme/config/settings.py:84-85` |
| CLI has `ingest`, `testgen`, `practice` implemented; `process`, `review`, `eval` are explicit stubs | `src/qme/cli.py:108`, `:118`, `:128` (each calls `_not_implemented`) |
| Existing product shipping plan sketches a React frontend | `docs/SHIPPING_PLAN.md` §4 (Phase 3), currently **PARKED** |
| Repo rule: no code outside `src/qme/` and `tests/`; docs live in `docs/` | `AGENTS.md` → *Hard rules* |

### 2.2 Proposed stack (confirmed by owner)

| Layer | Choice | Rationale |
|---|---|---|
| Build | **Vite** | Fast HMR, static `dist/` output — fits same-origin serving. |
| UI | **React 18 + TypeScript (strict)** | Owner decision; matches `docs/SHIPPING_PLAN.md`. |
| Routing | **react-router v6** | Route map in §7; supports the blocked `/admin` tree. |
| Styling | **Tailwind CSS** + design tokens | Enforces a single reusable system (§9) instead of per-page styling. Owner decision resolved the open "Tailwind vs plain CSS" item in `docs/SHIPPING_PLAN.md` §7 item 5. |
| Data | **React Query (or a thin wrapper)** for server state; component state for drafts | Server state ≠ UI state; results are client-owned (§5). |
| Tests | **Vitest + React Testing Library** | Logic-heavy rules (count/feasibility pre-validation, pagination) deserve unit tests. |
| Dev proxy | Vite `server.proxy` → API origin | Required: backend ships no CORS (§2.1). |

### 2.3 Feature inventory — implemented vs. not

The UI must only design for what the backend actually serves.

| Feature (ID) | Backend module | HTTP surface | UI treatment |
|---|---|---|---|
| Question ingestion & normalization (FE-001) | `src/qme/ingestion/` | ❌ none — CLI `qme ingest` only (`src/qme/cli.py:62`) | `BLOCKED` admin screen (§8.9) |
| Source tracking & provenance (FE-008) | `src/qme/ingestion/source_tracker.py` | ❌ not exposed | Show provenance **fields** already present in question objects |
| Topic classification (FE-002) | `src/qme/pipeline/stages/classifier.py` | ❌ not exposed | Display `classification.*` as read-only metadata |
| Difficulty scoring (FE-003) | `src/qme/pipeline/stages/difficulty.py` | ❌ not exposed | Display `difficulty` + `difficulty_basis` |
| Solution engine (FE-004) | `src/qme/pipeline/stages/solution.py` | ❌ not present (module absent) | N/A — bank ships its own `solution.steps` |
| Formula extraction (FE-005) | — | ❌ not implemented | Use the knowledge endpoint instead (§3.4) |
| Validation pipeline (FE-006) | `src/qme/validation/` (package stub) | ❌ not implemented | N/A |
| Batch processing (FE-007) | — | ❌ `POST /batches` specified but unimplemented | `BLOCKED` (§8.9) |
| Human review (FE-009) | — | ❌ `GET /review` specified but unimplemented | `BLOCKED` (§8.9) |
| Observability / cost (FE-010) | — | ❌ `GET /metrics` specified but unimplemented | `BLOCKED` (§8.9) |
| **Test & Practice engine** | `src/qme/testgen/` | ✅ `docs/API_CONTRACTS.md` §1.7 routes | `AVAILABLE` — the core of this UI |
| Health | `src/qme/main.py:41` | ✅ `GET /api/v1/health` | Connectivity indicator |

> **Hard rule for the implementer:** `docs/API_CONTRACTS.md` §1.1–§1.6
> (`/questions/process`, `/batches/*`, `/metrics`) are *specified* but return
> `404` today. Never call them from P0 code, and never populate a `BLOCKED`
> screen with mock data presented as real.

---

## 3. Product understanding and assumptions

### 3.1 Product

A self-study aptitude trainer backed by a curated, source-faithful question
bank (exact size comes from `GET /bank/meta`; the contract example in
`docs/API_CONTRACTS.md` §1.7 shows `question_count: 1310`). Questions are
never rewritten; the app **selects, orders, scores and
explains**. That constraint defines the experience: the value is the
*structure* (chapter, difficulty, coverage, timing, answer key), not novelty
of content.

### 3.2 Users and primary goals

| Persona | Primary goal | Success signal |
|---|---|---|
| **Student** (primary) | Take a timed test; understand every mistake; drill weak chapters with practice. | Correct score, clear per-question solution, one more practice round. |
| **Reviewer / content QA** (secondary) | Inspect what the bank actually contains: chapters, difficulty spread, knowledge coverage. | Spot a gap (e.g. zero hard questions in a chapter) without shell access. |
| **Data engineer / operator** (`BLOCKED`) | Run and monitor batch ingestion jobs. | Not buildable until §17.1 (gap 1) lands. |

### 3.3 Core user intents (design every screen around these)

1. *Give me a test that fits my study plan* — source / chapter / difficulty /
   length.
2. *Don't let me cheat, don't let me lose my work.*
3. *Show me my score, then why I was wrong.*
4. *Let me practice a weak chapter and reveal instantly.*
5. *Hand me the formulas when I'm stuck.*

### 3.4 Assumptions (explicitly marked — verify before building)

| # | Assumption | Basis | If false |
|---|---|---|---|
| A1 | Single-user app; no login, no history server-side. | Stateless API; `docs/PRD.md` §5 excludes auth/user management. | Requires backend work, out of scope. |
| A2 | English-only content. | `docs/PRD.md` §6. | i18n would be a P2 decision. |
| A3 | ~1,300 questions; `/bank/meta` is small enough to fetch once and cache. | Observed `question_count` example = 1310. | Add paging to the picker. |
| A4 | Answers/solutions must be hidden in the test flow but shown in practice. | `docs/API_CONTRACTS.md` §1.7; responses always include `correct_answer` + `solution`. | None — enforcement is purely client-side. |
| A5 | Deployment is same-origin (static `dist/` served by the API host) or via dev proxy. | No CORS middleware (§2.1). | CORS middleware must be added server-side. |
| A6 | The test `seed` can round-trip through client state reliably (localStorage/session). | `docs/API_CONTRACTS.md` §1.7 requires `request` verbatim on submit. | Tests become unscoreable — see §6-1. |

---

## 4. Existing user journeys and end-to-end workflow map

*There is no existing UI — this map is the **target** journey set, traced
against the live API. Each row lists its failure behaviour explicitly; full
error matrix in §5.3.*

### 4.1 Journey A — take a timed test `AVAILABLE`

| Step | UI | State | API call |
|---|---|---|---|
| 1 | App shell loads | `booting` | `GET /api/v1/health` (keyless) |
| 2 | Bank meta loads | `meta_loading` | `GET /api/v1/bank/meta` |
| 3 | User picks source → chapter → difficulty → count | `form_dirty`, client-validated | — |
| 4 | Start | `creating` | `POST /api/v1/tests` |
| 5 | Runner renders; timer starts | `running`, `draft` in localStorage | — (answers are local) |
| 6 | User answers / navigates | `draft_updated` | — |
| 7 | Timer expires **or** user submits | `submitting` | `POST /api/v1/tests/submit` with `{test_id, request, answers, elapsed_seconds}` |
| 8 | Report renders | `scored` | —; persist `TestResult` (no GET exists) |

Failure branches:
- Step 4 → `422 INVALID_INPUT` (rule/feasibility) → inline banner, form stays
  populated (§5.3).
- Step 7 → network error → **retry is safe** (idempotent), show retry action.
- Step 7 → `422 seed_required` → client bug; show recovery, log `request_id`.

### 4.2 Journey B — practice a chapter `AVAILABLE`

| Step | UI | API |
|---|---|---|
| 1 | Filters (source/chapter/topic/difficulty/mode) | — |
| 2 | Load page 1 | `POST /api/v1/practice` `{page:1}` |
| 3 | Reveal answer/solution per question (inline) | — (data already returned) |
| 4 | Next page | `POST /api/v1/practice` **same filters + echoed `seed` + `page+1`** |
| 5 | Formula panel toggle | `GET /api/v1/chapters/{key}/knowledge?topic=` |

Failure branches: `422` with `details.page/total_pages` (clamp and refetch);
`422` empty pool (offer reset-filters); `404 NOT_FOUND` on knowledge
(hide the toggle using `knowledge_coverage.missing_chapters`).

### 4.3 Journey C — inspect the bank `AVAILABLE`

`/` → `GET /bank/meta` → coverage cards, per-chapter difficulty bars,
knowledge gaps, jump-off buttons into Journey B filtered for that chapter.

Failure branches: `503 SERVICE_UNAVAILABLE` (broken bank) → full-page
unavailable with `request_id`; health down → offline banner.

### 4.4 Journey D — admin batch pipeline `BLOCKED`

Upload file → status → progress → results → review queue. **Requires
`POST /api/v1/batches`, `GET /batches/{id}`, `/results`, `/review`,
`GET /metrics` — none exist** (`src/qme/main.py:39` mounts only the testgen
router). Build route shell + request/response types only (§8.9, §15 P2).

### 4.5 Journey E — activation gate `FUTURE`

Product-key screen from `docs/SHIPPING_PLAN.md` §3. **No license endpoints
exist.** Excluded from this spec's build plan; listed in §17.

### 4.6 Journey F — interrupted test recovery `AVAILABLE`

Refresh mid-test → runner restores `{body, test, answers, startedAt}` from
localStorage → continues **without re-posting `/tests`** (re-posting would
mint a new `seed` and silently replace the test). "Abandon test" is a
confirmed destructive action clearing the draft (§11.5).

---

## 5. API integration audit

*Field-level schemas, request/response examples and TypeScript types are in
[`API_INTEGRATION.md`](./API_INTEGRATION.md) §3–§4 — this section audits
**integration behaviour and states only**. Auth for every row below except
health: `X-API-Key` header.*

### 5.1 Endpoint inventory with states

| # | Endpoint | Method | Success state | Failure states the UI must handle |
|---|---|---|---|---|
| 1 | `/api/v1/health` | GET | `status:"ok"`, version, environment | transport error only (no envelope) → offline banner |
| 2 | `/api/v1/bank/meta` | GET | sources, qualified chapters, difficulties, coverage, contract | `401 UNAUTHORIZED` (bad key), `503 SERVICE_UNAVAILABLE` (bank contract broken → `details.issues`), transport error |
| 3 | `/api/v1/tests` | POST | `GeneratedTest` (questions + answer key + timing) | `422 INVALID_INPUT` (rule table / feasibility / unknown key / both shapes), `422 VALIDATION_ERROR` (`details.fields[]`), `401`, `503` |
| 4 | `/api/v1/tests/submit` | POST | `TestResult` (score + breakups + per-question solutions) | `422 INVALID_INPUT` incl. **`seed_required`**, `422 ANSWER_MISMATCH` (`unknown_question_ids`, `invalid_option_keys`), `422 VALIDATION_ERROR`, `401`, `503`, transport (safe to retry — idempotent) |
| 5 | `/api/v1/practice` | POST | `PracticeSet` + `seed` + `pagination` | `422 INVALID_INPUT` (empty pool `details.filters`; page out of range `details.page/total_pages`; unknown/conflicting source/chapter), `401`, `503` |
| 6 | `/api/v1/chapters/{key}/knowledge` | GET | `ChapterKnowledge` (may be **empty lists** — not an error) | `404 NOT_FOUND` (unknown chapter), `401`, transport |
| 7 | `/api/v1/questions/process`, `/batches/*`, `/review`, `/metrics` | — | — | **`BLOCKED` — return 404 today; do not call** |

### 5.2 Per-endpoint integration notes

**1 — health.** Keyless; the only route without the error envelope. Use it
for a cheap boot check and a "cannot reach server" state. Do **not** gate
the app on it: the UI should still render its own error shell if health
fails.

**2 — bank meta.** The single discovery call behind every picker. Cache
aggressively (10 min `staleTime`); it only changes when the server's bank
files change (mtime cache, `src/qme/api/routes/testgen.py:68-90`).
`503` here is an operator-level fault — full-page unavailable, no retry
loop.

**3 — tests (friendly shape recommended).** The API returns **no clamped or
auto-balanced result**: every rule violation is a `422` carrying
`details.violations[]` with `rule`, `actual`, `expected`. Therefore the UI
must pre-validate locally (§11.3) and treat the server as a backstop, not a
corrector. Feasibility is the exception the UI *cannot* fully predict — but
`difficulty_counts` from meta makes it predictable in almost all cases.

**4 — submit.** The defining constraint: `request` must be the **exact**
creation body including `seed` (`docs/API_CONTRACTS.md` §1.7). The server
regenerates the test deterministically and scores against it. Two
consequences for the UI:
- Persist `{body, test, answers, startedAt}` as one atomic draft object.
- Retries are safe; **never** "regenerate a seed to make submit work".

**5 — practice.** Pagination is seed-dependent: the response **echoes
`seed`**, and omitting it on the next page reshuffles the pool
(`src/qme/testgen/practice.py:111-127`). Filters + seed form a single
identity — changing filters resets seed and page. `shortages` is always
`[]`; do not render a shortage region for practice.

**6 — knowledge.** Path parameter must be `encodeURIComponent`-ed (qualified
keys contain ` › `, spaces, `&`). Empty result ≠ error: render
"formulas pending" using `knowledge_coverage.missing_chapters` from meta to
disable the control proactively.

### 5.3 Error handling contract (all endpoints)

Envelope — `{"error": {code, message, details, request_id}}`
(`src/qme/api/exceptions.py:27-38`):

| Status | `code` | UI treatment |
|---|---|---|
| 401 | `UNAUTHORIZED` | Config problem: show "check API key", stop retrying. |
| 404 | `NOT_FOUND` | Hide/disable the referenced control (knowledge only). |
| 422 | `VALIDATION_ERROR` | Map `details.fields[].location` → inline field errors. |
| 422 | `INVALID_INPUT` | Map `details.violations[].rule` → contextual message; show `available_by_difficulty` / `details.available` as corrective options. |
| 422 | `ANSWER_MISMATCH` | Recovery screen: "this test could not be re-verified — retake". |
| 503 | `SERVICE_UNAVAILABLE` | Full-page unavailable; show `details.issues` (first line) + `request_id`. |
| transport | (none) | "Can't reach the server" + Retry; classify explicitly as non-HTTP. |

Rules for the implementer:
1. Branch on `error.code`, **never** on HTTP status alone (two statuses
   carry multiple codes).
2. Capture and display `request_id` on every surfaced error.
3. Auto-retry only transport failures and `503`; never `422`/`401`.
4. An error response lacking `error.code` is a proxy/CORS fault — classify
   it as such, not as a backend error.

### 5.4 Client-state contract

| Client-owned state | Store | Lifetime | Why |
|---|---|---|---|
| Active test draft `{body, test, answers, startedAt}` | `sessionStorage` (default) or `localStorage` | until submit/abandon | API is stateless; no `GET` for a test. |
| `TestResult` | `localStorage` (keyed by `test_id`) | until cleared | No results endpoint — loss is unrecoverable. |
| Practice pagination `{filters, seed, page}` | component/hook state | session | Seed identity for stable paging. |
| `BankMeta` | React Query cache | ~10 min | Changes only when server bank files change. |
| API base URL / key | build-time env (or proxy) | build | Never in code; never a secret in the browser bundle (§14). |

---

## 6. Current UX/UI issues, each linked to evidence

*No UI exists, so these are **design risks derived from the backend**. Each
one is a concrete failure the product will exhibit if designed carelessly.*

### 6-1. Submission can silently break: `seed` must survive as an opaque object
**Evidence:** `src/qme/api/routes/testgen.py:146-153` raises
`SelectionError("submission request is missing the seed echoed by
POST /tests", ...)` → `422 INVALID_INPUT`.
**Impact:** A user finishes a 60-minute test and gets an error instead of a
score. Irrecoverable — the result cannot be produced without the seed.
**Design requirement:** persist the **raw request body object** verbatim;
never re-derive it from form state (§11.4). Add a P0 unit test asserting the
draft round-trips.

### 6-2. Answers and solutions ship in the creation response
**Evidence:** `docs/API_CONTRACTS.md` §1.7 — "Answers/solutions are
included in the response (the frontend decides when to reveal them)";
`GeneratedTest.questions[].correct_answer` / `.solution` / `answer_key[]`
(`src/qme/testgen/schemas.py:296-311`).
**Impact:** Cheating via devtools is trivial; also a UI bug risk — rendering
a `QuestionCard` in test mode with the answer prop set leaks it.
**Design requirement:** one `QuestionCard` component with an explicit
`reveal` prop; the test route renders `reveal={false}`. Tests assert the
runner DOM contains no correct-answer text.

### 6-3. There is no results endpoint — score loss is permanent
**Evidence:** route table `src/qme/api/routes/testgen.py:112-203` has no
`GET .../result`; `docs/API_CONTRACTS.md` §1.7 — "the client stores the
returned result (no GET results endpoint)".
**Impact:** Refresh after submit loses the report unless persisted.
**Design requirement:** write `TestResult` to `localStorage` keyed by
`test_id` *before* navigating to the report route; the report route reads
persisted data and offers an explicit "result not found" state.

### 6-4. No CORS middleware → the naive dev setup just fails
**Evidence:** `src/qme/main.py:30-49` — `create_app()` registers exception
handlers and the testgen router only; no `CORSMiddleware`.
**Impact:** `localhost:5173` → `localhost:8000` is blocked by the browser;
a developer misdiagnoses it as a backend bug.
**Design requirement:** Vite `server.proxy` in dev (§15 P0) and
same-origin production serving; documented in `README.md`.

### 6-5. Count rules are unforgiving and server-enforced
**Evidence:** `src/qme/testgen/spec.py:32-35` (`COUNT_MULTIPLE=5`,
`MIN_TEST_QUESTIONS=10`, `MIN_ALL_SCOPE_QUESTIONS=30`) and the feasibility
check `:233-259`.
**Impact:** Typing `12`, or an all-chapters test of `15`, yields a `422` the
user cannot interpret.
**Design requirement:** stepped numeric input + live inline validation
(§11.3); picker disables infeasible difficulty levels using
`difficulty_counts`.

### 6-6. Ambiguous chapter names are rejected, never merged
**Evidence:** `src/qme/testgen/bank.py:157-171` raises
`SelectionError(... "ambiguous across sources; qualify it as ...",
{"ambiguous": [...]})`.
**Impact:** Picking bare "Percentage" returns 422 unless the UI always
offers **qualified** keys (`Source › Chapter`) from
`/bank/meta → chapters`.
**Design requirement:** chapter `<select>` values are qualified keys only;
labels may be human-friendly, values are never hand-typed.

### 6-7. Practice pagination reshuffles without the echoed seed
**Evidence:** `src/qme/testgen/practice.py:111-127` (pool ordered from
`seed`, sliced into disjoint pages).
**Impact:** Duplicate/missing questions across pages; user loses trust.
**Design requirement:** treat `{filters, seed}` as immutable identity —
changing either resets to page 1 and clears the seed (§11.6).

### 6-8. Practice page out of range is an error, not a clamp
**Evidence:** `src/qme/testgen/practice.py:120-124` raises
`SelectionError("page N exceeds the pool", {page, total_pages, total})`.
**Impact:** Double-clicking "Next" at the end surfaces a raw error.
**Design requirement:** disable Next when `pagination.has_more === false`;
still handle the 422 by clamping to `details.total_pages` and refetching.

### 6-9. `503` reports bank corruption in operator language
**Evidence:** `src/qme/api/exceptions.py:64-72` → `details.issues` field
report; `src/qme/testgen/bank.py` hard-stops on any contract violation.
**Impact:** A raw technical dump is alarming and useless to a student.
**Design requirement:** full-page "Service unavailable", short explanation,
collapsible `details.issues`, `request_id`, manual Retry (no auto-loop).

### 6-10. Empty knowledge is a normal state, not an error
**Evidence:** `src/qme/api/routes/testgen.py:182-185` returns
`ChapterKnowledge` with empty lists when no entry exists; gaps are listed in
`knowledge_coverage.missing_chapters` (`src/qme/testgen/bank.py:111-117`).
**Impact:** Rendering empty lists as "error" or blank space confuses users.
**Design requirement:** explicit empty-state copy ("No formulas recorded for
this chapter yet").

### 6-11. Repo constraint: a frontend directory is not yet allowed
**Evidence:** `AGENTS.md` *Hard rules* — "No code outside `src/qme/` and
`tests/`"; `docs/SHIPPING_PLAN.md` Phase 0 proposes amending it.
**Impact:** The build agent may be blocked or may violate repo rules.
**Design requirement:** P0 starts with the Phase 0 amendment allowing
`frontend/` (recorded in §17.3).

---

## 7. Proposed information architecture and route map

### 7.1 Information architecture

```
Aptitude Engine UI
├── Overview            bank at a glance, entry points, connectivity
├── Test                setup → run → report        (journey A)
├── Practice            filters + paginated drill   (journey B)
├── Formulas            knowledge viewer            (journey C)
└── Admin (BLOCKED)     batches / review / metrics  (journey D)
```

Three primary tabs (Test, Practice, Formulas) plus Overview. Admin lives in a
**separate section** so blocked work never pollutes the student's primary
navigation.

### 7.2 Route map

| Route | Screen | Journey | Status | Data source |
|---|---|---|---|---|
| `/` | Overview / home | C | `AVAILABLE` | `GET /health`, `GET /bank/meta` |
| `/test/new` | Test setup | A 3–4 | `AVAILABLE` | `GET /bank/meta`, `POST /tests` |
| `/test/run` | Runner | A 5–7 | `AVAILABLE` | localStorage draft only |
| `/test/result` | Report + review | A 8 | `AVAILABLE` | persisted `TestResult` |
| `/practice` | Practice drill | B | `AVAILABLE` | `POST /practice` |
| `/formulas` | Knowledge index | C | `AVAILABLE` | `GET /bank/meta` |
| `/formulas/:chapterKey` | Knowledge detail | B 5 | `AVAILABLE` | `GET /chapters/{key}/knowledge` |
| `/admin` | Admin landing (blocked state) | D | `BLOCKED` | none — static explanation |
| `/admin/batches` | Batch list / upload / progress | D | `BLOCKED` | `POST/GET /batches` (404 today) |
| `/admin/batches/:id/results` | Batch results stream | D | `BLOCKED` | `GET /batches/{id}/results` (404) |
| `/admin/review` | Review queue | D | `BLOCKED` | `GET /batches/{id}/review` (404) |
| `/admin/metrics` | Cost & metrics | D | `BLOCKED` | `GET /metrics` (404) |
| `*` | Not found | — | — | — |

### 7.3 Navigation rules

- Global header: product name · nav tabs · **connection indicator**
  (`/health`) · nothing else. No search, no avatar, no user menu (there is
  no user system).
- `/test/run` and `/test/result` are **bare routes** — no nav, no tab bar:
  the user must not be able to click into Practice mid-test and lose the
  draft.
- Leaving `/test/run` with an unfinished draft raises a confirmation
  (§11.5).
- Deep-linking `/test/result` with no persisted result shows an explicit
  "No saved result" state with a route back to `/test/new` (§6-3).
- `/admin/*` renders a `BLOCKED` panel (§8.9), never a fake UI.

---

## 8. Page-by-page ideal layout

*Every screen below lists: purpose → layout hierarchy → required states.
Layouts are desktop-first with responsive rules in §13. Screens are formal:
structure from borders and spacing, not from cards-on-cards.*

### 8.1 Overview `/` — `AVAILABLE`

**Purpose:** one glance at what the bank contains + the three entry points.

```
┌───────────────────────────────────────────────────────────────┐
│ Header: Aptitude Engine | Test  Practice  Formulas | ● online │
├───────────────────────────────────────────────────────────────┤
│ Bank summary strip   (all counts live from GET /bank/meta)    │
│ [N questions] [N chapters] [N sources] [easy/med/hard bar]    │
├───────────────────────────────────────────────────────────────┤
│ Primary actions                                               │
│ [ Start a test → ]   [ Practice a chapter → ]   [ Formulas → ]│
├───────────────────────────────────────────────────────────────┤
│ Coverage by chapter (compact table)                           │
│ Chapter | Total | easy | medium | hard | formulas             │
│ ... rows sorted by question_count desc ...                    │
└───────────────────────────────────────────────────────────────┘
```

- Counts shown as `N` are placeholders — every value is read from
  `GET /bank/meta`, never hardcoded (§16.1).
- Content hierarchy: **what** (counts) → **do** (actions) → **detail**
  (coverage table).
- Coverage table rows link to `/practice?chapter=<qualified key>`.
- Knowledge gaps from `knowledge_coverage.missing_chapters` render as a
  quiet "formulas pending" tag — informational, not an alert.

**States:** `loading` (skeleton strip + 6 table rows) · `meta_error`
(inline banner, actions disabled) · `offline` (health failed: banner +
Retry).

### 8.2 Test setup `/test/new` — `AVAILABLE`

**Purpose:** compose a feasible test with zero `422`s.

```
┌───────────────────────────────────────────────────────────────┐
│ Header                                                        │
├───────────────────────────────────────────────────────────────┤
│ New test                                               [Reset]│
│                                                               │
│  SOURCE                   CHAPTER                             │
│  [ All sources        ▾ ]   [ Percentage, Profit & Loss ▾ ]   │
│                                 123 questions                 │
│                                                               │
│  DIFFICULTY                   LENGTH                          │
│  ● single                     [ 10 ▲▼ ]  step 5, min 10       │
│  ○ mixed                      12 hard questions available     │
│    counts: easy [5] medium [3] hard [2]   sum must equal 10   │
│                                                               │
│  Estimated time 14 min · Seed (auto)                          │
│  [                             Start test                    ]│
│  (inline validation / 422 banner region)                      │
└───────────────────────────────────────────────────────────────┘
```

**Field behaviour**

| Control | Source | Behaviour |
|---|---|---|
| Source | `meta.sources[].name` | `Omit` semantics: an "All sources" option must **not** send an empty array (§6-5/§6-6). |
| Chapter | `meta.sources[].chapters[].key` | Values are **qualified keys** only; option label = `label` + question count. |
| Difficulty single/mixed | user | `mixed` shows three numeric inputs; live sum indicator must equal `count`. |
| Count | user | `min=10`, `step=5`; when no chapter scope selected, min becomes 30. |
| Feasibility hint | `difficulty_counts` | Shows available vs requested; disables Start when insufficient. |
| Seed | auto | Displayed read-only for reproducibility; Start sends none (server mints one). |

**States:** `loading` (pickers disabled + skeleton) · `invalid` (Start
disabled, first error visible) · `submitting` (Start spinner, form locked) ·
`server_error` (422 banner with corrective copy; 503 → full-page
unavailable).

### 8.3 Runner `/test/run` — `AVAILABLE` (bare route)

**Purpose:** answer the test; nothing else competes for attention.

```
┌────────────────────────────────────────────────────────────────┐
│ Unit Test 3 · 20 questions   Answered 7/20      ⏱ 12:45        │
│ [■■■■■□□□□□□□□□□□□□□] progress bar                             │
├────────────────────────────────────────────────────────────────┤
│ 1  (hard)  A train travels at 54 km/hr…            [chapter]   │
│    ○ A   ○ B   ○ C   ○ D                                       │
│ ────────────────────────────────────────────────────────────── │
│ 2  (easy)  …                                                   │
├────────────────────────────────────────────────────────────────┤
│  Question navigator: [1][2][3]…[20]   [Submit test]            │
└────────────────────────────────────────────────────────────────┘
```

- **One question per block, vertically stacked** — faster than one-at-a-time
  pagination on desktop, and it lets the navigator jump/scroll smoothly.
- Header is the only chrome: title, answered counter, **timer** (monospace,
  tabular numerals), progress bar.
- Options are radio inputs (real `<input type="radio">`) — keyboard arrows
  work natively.
- Timer: seeded from `test.timing.estimated_total_sec`; at ≤60s it turns
  attention colour (§9.5) and announces via `aria-live="polite"`.
  At 0 → auto-submit with `elapsed_seconds`.
- **No answer, no solution, no `answer_key` access anywhere on this route**
  (§6-2). No copy-paste obstructing — the bank is not adversarial content.
- Navigator marks unanswered vs answered; unanswered are scored wrong, so a
  confirmation lists the unanswered count before submit.

**States:** `restoring_draft` (skeleton) · `running` · `submitting`
(disable all inputs) · `submit_error` (inline banner + Retry, values kept) ·
`submit_error_seed` (recovery panel) · `submitted` → redirect to report.

### 8.4 Report `/test/result` — `AVAILABLE`

**Purpose:** score first, then *why*.

```
┌────────────────────────────────────────────────────────────────┐
│ 70% · 14 of 20 correct            Time 9:00 · seed 42          │
│ By difficulty  easy 8/10 · medium 5/5 · hard 1/5               │
│ By chapter     Quantitative Aptitude EBook › Percentage… 14/20 │
│ [ Retake ] [ Practice weak chapter ]                           │
├────────────────────────────────────────────────────────────────┤
│ Filters: [All | Incorrect only]   Sort: [in test order ▾]      │
│ ▸ Q5 (hard)  ✗  You: B · Correct: A (24 seconds)               │
│     1. …  2. …  3. …              (revealed on expand)         │
└────────────────────────────────────────────────────────────────┘
```

- Hierarchy: **headline score** → breakups (charts/table) → review list.
- Review rows default **collapsed**, expanded for incorrect ones. Solutions
  render as ordered steps from `results[].solution_steps`.
- "Practice weak chapter" derives from the lowest `by_chapter`/`by_difficulty`
  bucket and deep-links `/practice` with those filters.
- Persisted-on-load requirement (§6-3); a hard refresh must still show this
  screen.

**States:** `loading` (skeleton) · `no_result` (deep link without data) ·
`persist_error` (result shown, warning that it won't survive refresh).

### 8.5 Practice `/practice` — `AVAILABLE`

**Purpose:** drill with instant reveal and stable paging.

```
┌────────────────────────────────────────────────────────────────┐
│ Filters [source][chapter][topic][difficulty][mode] [Apply]     │
├────────────────────────────────────────────────────────────────┤
│ Q1 (hard)  question text…                      [Show answer]   │
│   ✓ A  24 seconds                                              │
│   steps…                                                       │
│ ┌ Formulas ────────────────────────────────┐                   │
│ │ topic_knowledge for the current topics   │                   │
│ └──────────────────────────────────────────┘                   │
├────────────────────────────────────────────────────────────────┤
│ [◀ Prev]  Page 2 of 25 · 123 questions   [Next ▶]              │
└────────────────────────────────────────────────────────────────┘
```

- Filters live **above** the list and apply on explicit action (Apply) —
  avoids reshuffling on every keystroke (§6-7).
- Reveal is per-question (`<details>`-style), inline; answer + solution are
  already in the payload — no extra request.
- Pagination echoes the seed internally; the user never edits the seed.
- Formula side panel uses `topic_knowledge` / `chapter_formula_summary` from
  the same response.

**States:** `filters_loading` · `loading_page` (row skeletons, previous page
dimmed) · `empty_pool` ("No questions match these filters" + Reset) ·
`page_error` (clamp+refetch) · `last_page` (Next disabled).

### 8.6 Formulas index `/formulas` — `AVAILABLE`

Searchable list of chapters from `meta.chapters` (qualified), each row
showing formula availability (`knowledge_coverage`). Rows without knowledge
are shown, disabled, tagged "pending" — so users know it exists but is
empty rather than missing (§6-10). Search filters client-side (no API
search endpoint).

### 8.7 Formulas detail `/formulas/:chapterKey` — `AVAILABLE`

```
Header › Percentage, Profit & Loss            [topic ▾ All topics]
Chapter summary (formula_summary bullets)
Topics (accordion, one per key):
  ▸ Successive Percentages
     Formulas    ·  Short tricks
```

`encodeURIComponent` the key in links (§5.2). Loading skeleton → detail;
404 → back to index with message; empty → explicit empty state.

### 8.8 Recovery / utility screens

| Screen | Route | Content |
|---|---|---|
| Not found | `*` | Message + return action. |
| Service unavailable | in-place | 503 summary, `request_id`, collapsible `details.issues`, Retry. |
| Config error | in-place | 401 guidance (key missing/misconfigured). |
| Offline | in-place | Transport failure banner + Retry (health indicator red). |

### 8.9 Admin `/admin/*` — `BLOCKED` (shell only)

**Design intent:** document the intended experience without pretending it
works. Every `/admin/*` route renders:

1. **Status panel** — "Not available: this screen requires backend endpoints
   that are not implemented (HTTP 404 today)."
2. **Contract reference** — the exact missing endpoint and its specified
   request/response shape (from `docs/API_CONTRACTS.md` §1.2–§1.6).
3. **Typed stubs** — request/response TypeScript interfaces live in the code
   so wiring later is mechanical.

Intended layouts (for future implementation, documented here so the IA is
complete):
- **Batches:** file drop → `POST /batches` → status list with
  `progress {total, processed, successful, failed, needs_review}` → drill
  into results stream.
- **Review queue:** item list with `reason_codes`, inline approve/reject.
- **Metrics:** token/cost figures, failure rate.

**Rule:** no mock rows, no fake progress bars, no sample data. A `BLOCKED`
panel is honest and keeps reviewers from trusting invented numbers.

---

## 9. Visual design system

*Goal: one reusable system, no per-page styling. All values are tokens in
the Tailwind config.*

### 9.1 Design principles

1. **Structure over decoration** — hierarchy from spacing, rules and weight;
   not from shadows and gradients.
2. **Density where it informs** — results/coverage tables are compact;
   reading surfaces (question text) are generous.
3. **One accent, used sparingly** — colour signals state and primary action,
   never ornament.
4. **Calm under time pressure** — during a test, the screen has no
   decoration competing with the question.
5. **Honest states** — loading, empty and error look intentional, not
   broken.

### 9.2 Palette intent

| Token | Intent | Usage |
|---|---|---|
| `surface` / `surface-alt` | Neutral page background / subtle bands | page, table stripes, form groups |
| `content` / `content-muted` | Primary / secondary text | body text, labels, meta |
| `border` | Hairline structure | table rows, inputs, panel edges |
| `brand` | Product identity + primary action | primary button, active tab, focus ring |
| `success` / `danger` / `warning` | Correct · incorrect/forbidden · attention | answer states, validation errors, timer ≤60s |
| `info` | Neutral informational tag | "pending formulas", coverage notes |

Rules: body text ≥ 4.5:1 contrast (§13); colour is **never** the only
correctness signal — pair with icon/label (✓/✗ + text). No gradients. No
dark-mode requirement in P0 (design tokens make it a P1 add-on).

### 9.3 Typography roles

| Role | Spec | Usage |
|---|---|---|
| Display | 24–30px / 600 | page titles |
| Heading | 16–20px / 600 | section titles, card headings |
| Body | 15–16px / 400, line-height 1.6 | question text, solutions |
| UI label | 13–14px / 500 | buttons, tabs, form labels |
| Meta | 12–13px / 400, muted | counts, ids, timestamps |
| Numeric / timer | system or mono, **tabular numerals** | timer, scores, counters |

One sans-serif family (system stack or Inter). No all-caps sentences; no
font sizes below 12px.

### 9.4 Spacing rhythm

4px base grid: `4 / 8 / 12 / 16 / 24 / 32 / 48`. Page gutter `24px`
desktop, `16px` mobile. Panel padding `16–24px`. Vertical rhythm between
sections `24–32px`. Question blocks separated by `24px` + a hairline rule.

### 9.5 Borders & elevation

- Structure: `1px` `border` colour; **no rounded card stacks**. Radius `6px`
  on inputs/buttons, `8px` on panels.
- Elevation only for overlays (modal, toast): `0 4px 16px rgba(0,0,0,.12)`.
  Static content uses no shadow.
- Timer warning state: colour only (no pulsing).

### 9.6 Iconography & imagery

- Inline SVG icons (one set, 16/20px): chevrons, check, cross, timer,
  refresh, external. **No emoji.**
- No photography, no illustrations, no hero art. The question text and the
  data *are* the imagery.
- Charts: minimal horizontal bars / donut for score only; no chart library
  for P0 if a CSS bar suffices.

### 9.7 Motion

| Interaction | Motion | Budget |
|---|---|---|
| Reveal answer, expand review row | height/opacity ≤ 160ms | allowed |
| Button hover/press, focus | ≤ 120ms colour only | allowed |
| Page transitions, spinners for known latency | **none / skeleton only** | skeletons beat spinners |
| Timer, progress bar | width transition ≤ 300ms | allowed |
| Decorative entrance animation | **banned** | — |

Respect `prefers-reduced-motion`: disable everything above.

---

## 10. Reusable component specification

*Components own rendering + local interaction only; data comes from hooks
(§11.1). `reveal` is the single most important prop (§6-2).*

| Component | Responsibility | Key props |
|---|---|---|
| `AppShell` | Header, nav, connection indicator, outlet | `online: boolean` |
| `ConnectionIndicator` | `/health` status dot + tooltip | `status: 'ok'\|'down'\|'checking'` |
| `PageHeader` | Title, subtitle, right-side actions | `title`, `actions` |
| `Button` | Primary/secondary/ghost variants, busy state | `variant`, `loading`, `disabled` |
| `Select` | Labelled native select with optional hint/error | `label`, `options`, `error`, `hint` |
| `NumberStepper` | Count input with min/max/step validation | `min`, `max`, `step`, `value`, `onChange` |
| `FieldError` | Inline validation message | `message` |
| `ErrorBanner` | Envelope-aware error display | `error: ApiError`, `onRetry?` |
| `Skeleton` | Loading placeholder (rows/blocks) | `variant`, `rows` |
| `EmptyState` | Message + optional action | `title`, `body`, `action?` |
| `Tag` | Quiet label (difficulty, chapter, status) | `tone: 'neutral'\|'success'\|'danger'\|'info'\|'warning'` |
| `QuestionCard` | Renders one question + options | `question: BankQuestion`, **`reveal: boolean`**, `value?`, `onChange?` |
| `OptionList` | Radio group of options | `options`, `value`, `onChange`, `correct?` |
| `QuestionNavigator` | Jump-to-question grid + answered marks | `total`, `answered: Set<number>`, `onJump` |
| `Timer` | Countdown, warning threshold, expiry callback | `seconds`, `onExpire` |
| `ProgressBar` | Determinate bar (answered / timing) | `value`, `max`, `tone?` |
| `DifficultyPicker` | single/mixed difficulty spec control | `value: DifficultySpec`, `onChange`, `available` |
| `FilterBar` | Practice/test filters group | `value`, `onApply`, `onReset` |
| `Pagination` | Prev/Next + page info | `page`, `totalPages`, `hasMore`, `onPage` |
| `ScoreRing` / `ScoreBreakdown` | Headline score + breakups | `score: ScoreBreakup`, `breakdowns` |
| `ReviewRow` | Collapsible per-question review | `line: ResultLine`, `defaultOpen?` |
| `SolutionSteps` | Ordered solution steps | `steps: string[]` |
| `KnowledgePanel` | `topic_knowledge` list | `terms: KnowledgeTerms` |
| `CoverageTable` | Chapter × difficulty coverage | `meta: BankMeta`, `onRowClick` |
| `BlockedPanel` | `BLOCKED` explanation for admin | `endpoint`, `contractDoc` |

**Composition rules**

- Reuse `QuestionCard` in runner (reveal=false) and practice (reveal=true).
- Reuse `ErrorBanner` for **every** failure; no ad-hoc error markup.
- No page may style its own colors — tokens only.

---

## 11. Interaction and state specifications

### 11.1 Data layer

| Hook | Wraps | Contract |
|---|---|---|
| `useHealth()` | `GET /health` | Polls at 60s (paused when tab hidden); sets `ConnectionIndicator`. |
| `useBankMeta()` | `GET /bank/meta` | React Query, `staleTime` 10min; exposes `meta`, `loading`, `error`. |
| `useCreateTest()` | `POST /tests` | Mutates; returns `GeneratedTest`; error typed `ApiError`. |
| `useSubmitTest()` | `POST /tests/submit` | Mutates; **retries transport failures only** (idempotent by contract). |
| `usePractice()` | `POST /practice` | Keyed by `JSON.stringify({filters, seed, page})` — guarantees no cross-filter cache bleed. |
| `useKnowledge(chapterKey, topic?)` | `GET /chapters/{key}/knowledge` | Path `encodeURIComponent`-ed; `enabled: !!chapterKey`. |
| `useDraft()` | `localStorage` | Atomic read/write of `{body, test, answers, startedAt}`; returns `save`, `load`, `clear`. |

Server state lives in React Query; **drafts and results live in
`useDraft`/`useResultStore`** — never in React Query (they are not server
state).

### 11.2 Validation timing matrix

| Field | When validated | Behaviour |
|---|---|---|
| Count (multiple of 5, minimums) | On change + on blur | Inline error under input; Start disabled. |
| Mixed difficulty sum | On change | Live "sum 8 of 10" indicator; error when ≠ `count`. |
| Feasibility | On any scope change | From `difficulty_counts`; Start disabled + hint showing available. |
| Source/chapter empty vs. omitted | On change | "All sources"/"All chapters" = **omitted field**, never `[]` (§6-5). |
| Difficulty value present | On change | `single` requires a value; `mixed` requires counts. |
| Server 422 | On submit response | Banner with `violations[].rule` copy; form retains values; focus moves to banner. |
| Server 422 `VALIDATION_ERROR` | On submit response | Inline per `details.fields[].location`. |

Client validation **never** blocks a request the client cannot predict
(feasibility edge cases) — the server remains the authority; client checks
only remove avoidable failures.

### 11.3 Keyboard & focus

- All controls reachable by `Tab` in visual order; visible focus ring
  (2px `brand`, 2px offset) on **every** interactive element.
- Question options: real radio inputs ⇒ arrow keys move within the group,
  Space selects.
- Navigator numbers: `Enter`/Space scrolls to the question block and moves
  focus to its first option.
- Runner shortcuts (documented in a small help line, not a modal): `1–4`
  select option, `J`/`K` next/prev block. No shortcut may fire while an
  input has focus.
- Submit/Start are `<button>` elements (never clickable `div`s).
- On validation failure after submit attempt: focus the banner
  (`role="alert"`).
- On route change: move focus to the `<h1>`; announce via `aria-live`.

### 11.4 Draft persistence & round-trip (critical, §6-1)

```
on create success:
  draft = { body: <exact request object>, test: GeneratedTest,
            answers: {}, startedAt: Date.now() }
  save(draft)                      // atomic write BEFORE navigating to /test/run
on every answer change:
  save({ ...draft, answers })      // debounced ≤ 300ms
on submit:
  body = { test_id: draft.test.test_id, request: draft.body,   // verbatim, seed intact
           answers: draft.answers,
           elapsed_seconds: floor((now - draft.startedAt) / 1000) }
  → POST /tests/submit → persist TestResult by test_id → clear draft → navigate
```

- **Forbidden:** rebuilding `draft.body` from form state; cloning it with
  field-by-field mapping; omitting `seed`.
- On `422 seed_required` (bug): show recovery panel, keep the draft intact,
  log `request_id`; never auto-mint a seed.
- Draft expiry: discard drafts older than 24h on load (stale tests are
  unlikely to still match the bank).

### 11.5 Destructive actions & navigation guards

| Action | Confirmation | On confirm |
|---|---|---|
| Leave `/test/run` with a non-empty draft (tab nav, back button, link) | Modal: "Leave the test? Your answers stay saved on this device." | keep draft, allow navigation |
| Abandon test | Modal: "Delete this attempt? Answers are discarded." | clear draft → `/test/new` |
| Reset setup form | None if untouched; else confirm | clear form |
| Retake after report | None | new `POST /tests` (new seed by design) |
| Clear saved results | Confirm | remove all `TestResult` entries |

Browser back/forward on `/test/run` must be intercepted (`useBlocker`);
quitting the tab entirely relies on the persisted draft.

### 11.6 Practice seed & pagination rules

1. First request: `{filters, page: 1}` (no seed) → capture echoed `seed`.
2. Next/Prev: same filters + same `seed` + `page ± 1`.
3. Any filter change (or Apply) → clear `seed`, reset `page` to 1.
4. `has_more === false` ⇒ Next disabled (but keep the 422 clamp handler for
   the double-click race, §6-8).
5. Keep previous page rendered (dimmed) while the next loads — no layout
   jump.

### 11.7 Loading, empty, error, offline

| State | Presentation |
|---|---|
| First load | Skeleton matching the final layout (never a bare spinner). |
| Subsequent/partial load | Existing content stays; new content shows a local skeleton. |
| Empty (no matches) | `EmptyState` with a Reset action — never a blank region. |
| Empty (knowledge) | Explicit copy per chapter (§6-10). |
| Error | `ErrorBanner` (inline) or full-page for 503/offline — per §5.3. |
| Offline | Global banner + Retry; disable actions requiring the API. |
| Retry after failure | Manual button; exponential backoff only for transport/503 (max 3). |
| Idempotent submit failure | Retry button with reassurance ("safe to retry"). |

### 11.8 Feedback & microcopy rules

- Never surface a raw `message` as the only copy for a *handled* code —
  map code → sentence. Raw text may appear in a collapsible "Details".
- Always show `request_id` for 4xx/5xx (support hook).
- Confirmation copy states consequence, not mechanism ("answers discarded",
  not "localStorage cleared").
- Numbers: percentages to 1 decimal (as the API returns), durations as
  `M:SS`.

---

## 12. API-to-UI data mapping table

*Every UI element below consumes a **verified** field. No row references an
invented field.*

| # | UI element | Endpoint | Field(s) consumed |
|---|---|---|---|
| 1 | Connection indicator | `GET /health` | `status`, `version`, `environment` |
| 2 | Overview counters | `GET /bank/meta` | `question_count`, `sources[].question_count`, `sources[].length` |
| 3 | Overview/summary difficulty bar | `GET /bank/meta` | `sources[].chapters[].difficulty_counts.{easy,medium,hard}` aggregated |
| 4 | Coverage table rows | `GET /bank/meta` | `sources[].chapters[]` → `key`, `label`, `question_count`, `difficulty_counts` |
| 5 | "Formulas pending" tags | `GET /bank/meta` | `knowledge_coverage.missing_chapters` / `covered_chapters` |
| 6 | Source picker options | `GET /bank/meta` | `sources[].name`, `sources[].question_count` |
| 7 | Chapter picker options | `GET /bank/meta` | `sources[].chapters[].key` (**value**), `.label` (**label**) |
| 8 | Difficulty options | `GET /bank/meta` | `difficulties[]` |
| 9 | Topic picker (practice) | `GET /bank/meta` | `topics[]` |
| 10 | Feasibility hint / disabled levels | `GET /bank/meta` | `sources[].chapters[].difficulty_counts` |
| 11 | Contract tooltip (setup) | `GET /bank/meta` | `contract.selection_rules[]`, `contract.required_filters[]` |
| 12 | Test id, title | `POST /tests` | `test_id`, `title`, `generated_at` |
| 13 | Question list (runner) | `POST /tests` | `questions[].question_id`, `.question_text`, `.options`, `.classification.difficulty`, `.classification.chapter`, `.source.name` |
| 14 | Timer initial value | `POST /tests` | `timing.estimated_total_sec` (also `avg_per_question_sec`, `min_sec`, `max_sec` for meta display) |
| 15 | Answered/total counters | `POST /tests` | `questions.length` (total); answered = client state |
| 16 | Seeded filter summary | `POST /tests` | `selections_applied[]`, `selection_rules_applied[]` |
| 17 | Coverage note on setup | `POST /tests` | `coverage.by_difficulty`, `coverage.by_chapter` |
| 18 | Shortage warning (legacy shape only) | `POST /tests` | `shortages[]` → `requested`, `provided`, `shortfall`, `filters` |
| 19 | Overlap note | `POST /tests` | `notes.overlaps_dropped` |
| 20 | Debug/About panel | `POST /tests` | `contract_source.blueprint`, `.schema_version`, `.question_bank`, `.knowledge_bank` |
| 21 | Headline score | `POST /tests/submit` | `score.correct`, `score.total`, `score.percent` |
| 22 | Difficulty breakdown | `POST /tests/submit` | `by_difficulty.{easy,medium,hard}.{correct,total,percent}` |
| 23 | Chapter breakdown / "weak chapter" CTA | `POST /tests/submit` | `by_chapter[...]` (qualified keys) |
| 24 | Source breakdown | `POST /tests/submit` | `by_source[...]` |
| 25 | Time taken | `POST /tests/submit` | `elapsed_seconds` |
| 26 | Review rows | `POST /tests/submit` | `results[].question_id`, `.your_answer`, `.correct_answer`, `.answer_text`, `.is_correct`, `.solution_steps`, `.difficulty`, `.chapter`, `.source` |
| 27 | Practice question + reveal | `POST /practice` | `questions[].correct_answer`, `.answer_text`, `.solution.steps` |
| 28 | Practice pagination | `POST /practice` | `pagination.page`, `.count`, `.total`, `.total_pages`, `.has_more` |
| 29 | Practice seed (round-trip) | `POST /practice` | `seed` |
| 30 | Applied-filter subtitle | `POST /practice` | `filters_applied` (note: `chapter` stored as **raw label**) |
| 31 | Practice formula panel | `POST /practice` | `topic_knowledge[topic].formulas`, `.short_tricks`; `chapter_formula_summary[]` |
| 32 | Practice mode label | `POST /practice` | `mode`, `practice_id`, `generated_at` |
| 33 | Formulas index rows | `GET /bank/meta` | `chapters[]` + `knowledge_coverage` |
| 34 | Formula detail summary | `GET /chapters/{key}/knowledge` | `chapter`, `formula_summary[]`, `topic` |
| 35 | Formula detail topics | `GET /chapters/{key}/knowledge` | `topics[topic].formulas[]`, `.short_tricks[]` |
| 36 | Error banner / unavailable screen | all (4xx/5xx) | `error.code`, `error.message`, `error.details`, `error.request_id` |
| 37 | Feasibility correction offer | `POST /tests` 422 | `details.available_by_difficulty`, `details.violations[].rule/actual/expected` |
| 38 | Chapter correction offer | any 422 | `details.available.chapters[]`, `details.available.sources[]`, `details.ambiguous[]` |
| 39 | Practice page clamp | `POST /practice` 422 | `details.page`, `details.total_pages`, `details.total` |
| 40 | Admin (blocked) | `GET /bank/meta` only | (admin endpoints unimplemented — see §8.9) |

---

## 13. Responsive and accessibility requirements

### 13.1 Breakpoints

| Token | Width | Target |
|---|---|---|
| `sm` | ≥ 640px | Phone landscape |
| `md` | ≥ 768px | Tablet portrait |
| `lg` | ≥ 1024px | Desktop (design reference) |

### 13.2 Responsive behaviour per screen

| Screen | ≤767px | 768–1023px | ≥1024px |
|---|---|---|---|
| Overview | Counters stack 2×2; coverage table → 2-line rows (chapter + total, difficulty as chips) | Table columns restored | Full table |
| Test setup | Single column, fields full width; difficulty block below length | 2-column field grid | 3-column field grid |
| Runner | Same stacked-list model (no carousel); timer sticky top; navigator collapses to a compact jump `<select>` | Timer + navigator in sticky bar | Full sticky bar per §8.3 |
| Report | Headline → breakdowns → review; breakups as list not chart | Breakups as 2-up | Breakups row |
| Practice | Filters collapse into a disclosure; reveal full width; pagination full width | Filters row wraps | Per §8.5 |
| Formulas | Accordion, one topic at a time | Same | Same |

Touch targets ≥ 44×44px on `sm`. Horizontal scrolling of the **page** is
never allowed; tables may scroll within their own container with a visible
edge cue.

### 13.3 Accessibility (WCAG 2.1 AA — required for P0)

- **Contrast:** body text ≥ 4.5:1; large text/UI borders ≥ 3:1.
- **Semantics:** real `<button>`, `<input type="radio">`, `<label for>`,
  one `<h1>` per route, landmarks (`header`/`main`/`nav`).
- **Focus:** visible ring everywhere; focus never trapped except inside a
  modal (then it *is* trapped and returns to the trigger on close).
- **Announcements:**
  - Timer ≤60s and expiry: `aria-live="polite"`.
  - Route change → focus `<h1>`; announce the new page name.
  - Submit result arrival: `aria-live="polite"` with the score.
  - Validation errors: `role="alert"`.
- **Labels:** option groups use `fieldset`/`legend` per question (question
  text is the legend) so screen readers announce context per choice.
- **Timer is not the only cue:** the countdown must never be the sole
  warning — pair with colour + text label ("Under one minute").
- **Reduced motion:** `prefers-reduced-motion: reduce` disables all
  transitions (§9.7).
- **No color-only meaning:** correct/incorrect pairs colour with ✓/✗ +
  "Correct"/"Incorrect" text.
- **Zoom:** usable at 200% browser zoom without loss of function.

---

## 14. Security and privacy considerations (frontend)

| # | Consideration | Requirement |
|---|---|---|
| 1 | **API key exposure** | Prefer server-side/dev-proxy injection (`README.md`). If a `VITE_QME_API_KEY`-style env var is used, it is by definition **public** — use a key scoped for client use, never a production operator secret; document the trade-off. |
| 2 | **No secrets in the repo** | `.env.local` gitignored; `.env.example` lists key **names** only. Never print key values in logs, errors or screenshots. |
| 3 | **XSS on question content** | Render all bank text as **text nodes** — no `dangerouslySetInnerHTML`, no Markdown-to-HTML for solutions (bank content is external). |
| 4 | **Answer integrity is cosmetic only** | Answers/solutions arrive in the creation payload (§6-2): do not claim anti-cheat. Keep answer state out of the DOM (JS memory) where practical, but assume a determined user can read it. |
| 5 | **localStorage scope** | Store only test drafts/results and preferences. No tokens, no PII, no bank dumps. Clear on abandon/expiry; key names namespaced (`qme.*`). |
| 6 | **Result tampering** | A user can edit their stored `TestResult`. Acceptable: results are personal study data with no server authority. Do not build features implying verified/attested scores. |
| 7 | **Proxy discipline** | Any dev/proxy route must target a configured API origin only (no open-relay pattern), and must not forward arbitrary absolute URLs. |
| 8 | **No third-party scripts** | No analytics/CDN fonts without an explicit decision — offline-after-load is a product goal. |
| 9 | **Error details** | `details.issues` may expose internal file paths — show it collapsed, intended for support, not as primary copy (§6-9). |
| 10 | **Rate/abuse** | The UI makes low-volume read-only calls; avoid unbounded polling (health ≤ 1/min, paused when hidden). |

---

## 15. Prioritized implementation plan

*Backend work is excluded — this plan is frontend-only, one phase per
session consistent with `AGENTS.md`.*

### P0 — Core student flows (build first; everything else depends on it)

| # | Task | Depends on | Acceptance |
|---|---|---|---|
| P0-0 | Scaffold `frontend/`: Vite + React + TS (strict) + react-router + Tailwind tokens; Vite `server.proxy` → API origin; Vitest wired; `AGENTS.md` Phase 0 amendment allowing `frontend/`. | repo rule amendment | `npm run dev` renders a shell; `/health` reachable through proxy. |
| P0-1 | API layer: `qmeClient` + `ApiError` (from `API_INTEGRATION.md` §8), hooks per §11.1, typed models per `API_INTEGRATION.md` §4. | P0-0 | Unit tests: envelope parsing, transport vs HTTP classification, `request_id` capture. |
| P0-2 | App shell + Overview (`/`): header, nav, connection indicator, coverage table, entry points. | P0-1 | §8.1 states all render; meta cached 10 min. |
| P0-3 | Test setup (`/test/new`): pickers from meta, friendly-shape builder, client validation per §11.2. | P0-2 | Zero 422s for all client-valid combinations tested; qualified chapter values only. |
| P0-4 | Runner (`/test/run`): draft persistence, timer, navigator, submit. | P0-3 | Draft survives refresh; correct-answer text absent from DOM; auto-submit on expiry; idempotent retry. |
| P0-5 | Report (`/test/result`): persisted result, breakups, review with solutions. | P0-4 | Refresh after submit still shows report; deep-link without result shows explicit empty state. |
| P0-6 | Practice (`/practice`): filters, reveal, seed-stable pagination. | P0-2 | Pages disjoint with echoed seed; filter change resets seed/page; empty-pool and clamp states work. |
| P0-7 | Error & state system: `ErrorBanner`, skeletons, empty states, offline banner, 503 screen. | P0-1 | Every code in §5.3 has a designed presentation; all errors expose `request_id`. |
| P0-8 | A11y + responsive pass: §13 checklist. | P0-3..P0-6 | Keyboard-only walkthrough of A→F journeys; no horizontal page scroll at 360px. |

### P1 — Knowledge & polish

| # | Task | Acceptance |
|---|---|---|
| P1-1 | Formulas index + detail (`/formulas`, `/formulas/:chapterKey`) with lazy knowledge fetch & cache. | 404/empty states correct; `encodeURIComponent` used; empty chapters tagged "pending". |
| P1-2 | Report analytics extras: weak-chapter → practice deep link; coverage-driven "next test" suggestion. | Deep link lands with correct filters. |
| P1-3 | Draft expiry (24h), result store management, "clear results". | Orphaned drafts removed; confirmations per §11.5. |
| P1-4 | Performance: code-split routes, bundle budget, meta prefetch. | Route-level lazy chunks; no layout shift on skeleton→content. |
| P1-5 | Keyboard shortcuts + `prefers-reduced-motion` + polish pass. | §11.3 + §9.7 verified. |

### P2 — Blocked / requires backend

| # | Task | Blocker |
|---|---|---|
| P2-1 | Admin shell (`/admin/*`) with `BLOCKED` panels + typed contract stubs. | None for shell; **data requires** `/batches`, `/review`, `/metrics` (§17.1, gap 1). |
| P2-2 | Batch upload → progress → results screens. | `POST/GET /api/v1/batches*` |
| P2-3 | Review queue screens. | `GET /batches/{id}/review` |
| P2-4 | Metrics/cost screens. | `GET /api/v1/metrics` |
| P2-5 | Activation gate + desktop packaging (pywebview). | License API (§17.1, gap 2), `docs/SHIPPING_PLAN.md` Phase 1–2 |

**Definition of done for P0:** all §16 P0 acceptance criteria pass, `npm run
build` is clean under TS strict, and no route calls an endpoint listed as
`BLOCKED`.

---

## 16. Acceptance criteria and verification checklist

### 16.1 P0 criteria (must all pass before P1)

**Setup (`/test/new`)**
- [ ] Pickers populated exclusively from `GET /bank/meta` (no hardcoded
      source/chapter/difficulty/topic values anywhere in the codebase).
- [ ] Chapter `<option>` values are qualified `Source › Chapter` keys.
- [ ] "All sources"/"All chapters" omit the field — an empty array is never
      sent.
- [ ] Count input enforces multiple of 5; min 10 with a chapter scope, min
      30 without.
- [ ] Mixed difficulty `sum(counts) === count` enforced live.
- [ ] Feasibility pre-checked via `difficulty_counts`; Start disabled when
      insufficient, with the available count shown.
- [ ] A server 422 keeps all form values and shows corrective copy.

**Runner (`/test/run`)**
- [ ] Draft `{body, test, answers, startedAt}` written to storage **before**
      navigation to `/test/run`.
- [ ] Refresh mid-test restores answers without issuing `POST /tests`.
- [ ] **No correct-answer or solution text is present in the runner DOM**
      (automated assertion).
- [ ] Timer seeds from `test.timing.estimated_total_sec`; auto-submits at 0
      with `elapsed_seconds`.
- [ ] Submit sends the stored request body **verbatim** (unit test: the
      stored body includes `seed` and deep-equals the creation request).
- [ ] Transport failure on submit offers Retry; retry succeeds without
      duplicating anything (idempotent).
- [ ] Leaving with answers raises the confirmation (§11.5).

**Report (`/test/result`)**
- [ ] `TestResult` persisted before navigation; a browser refresh still
      renders the report.
- [ ] Deep link with no stored result shows the explicit empty state.
- [ ] `score.percent`, breakups and per-question `solution_steps` render;
      correct/incorrect indicated by colour **and** icon/text.

**Practice (`/practice`)**
- [ ] Page 2+ reuses the echoed `seed`; no question repeats across pages in
      an automated check.
- [ ] Changing any filter resets `seed` and `page` to 1.
- [ ] `has_more === false` disables Next; the 422 clamp path also works.
- [ ] Empty pool shows `EmptyState` with Reset.

**Cross-cutting**
- [ ] Every request goes through the single client; `error.code` drives all
      error UI; every surfaced error shows `request_id`.
- [ ] No code path calls a `BLOCKED` endpoint (automated lint/grep check).
- [ ] `/health` powers the connection indicator; offline state disables API
      actions.
- [ ] Tailwind tokens only — no hard-coded hex values in components.

### 16.2 Verification checklist (run before reporting done)

| Check | How |
|---|---|
| Types & lint | `tsc --noEmit` clean under strict; lint clean |
| Unit | `vitest` — validation rules, seed round-trip, envelope parsing, pagination identity |
| Component | RTL — `QuestionCard` reveal/no-reveal, `ErrorBanner` per code, `Pagination` states |
| E2E (local, dev API) | Journeys A–C end-to-end; forced 422/404/503/network failure paths |
| Keyboard-only | Full A→B→C walkthrough without a mouse |
| Screen reader spot-check | Timer announcements, radio group context, route-change focus |
| Responsive | 360px / 768px / 1280px; no horizontal page scroll; tap targets ≥44px on phone |
| Security | No secrets in bundle or `dist/`; no `dangerouslySetInnerHTML`; `.env.local` gitignored |
| Docs | `README.md` run instructions verified by following them literally |

### 16.3 Explicit non-criteria (do not chase)

- Pixel-perfect parity with any external product.
- Anti-cheat guarantees (impossible per §6-2).
- Offline **operation** (bank data is served, not bundled in P0).
- Browser support beyond current Chrome/Edge/Firefox/Safari.

---

## 17. Open questions, assumptions, and unresolved API-contract gaps

### 17.1 Gaps that block work

| # | Gap | Evidence | Impact | Proposed resolution |
|---|---|---|---|---|
| 1 | **No batch/review/metrics endpoints.** `docs/API_CONTRACTS.md` §1.2–§1.6 specify them; `src/qme/main.py:39` mounts only the testgen router. | returns 404 today | Admin journey (D) unbuildable | Ship `BLOCKED` shells (§8.9); P2 until the backend delivers. |
| 2 | **No license/activation endpoints.** | `docs/SHIPPING_PLAN.md` §3 describes intent only | Activation gate unbuildable | P2/`FUTURE`; excluded from P0–P1. |
| 3 | **`AGENTS.md` forbids a `frontend/` directory.** | `AGENTS.md` Hard rules; `docs/SHIPPING_PLAN.md` Phase 0 | Build may violate repo rules | **P0-0 first task:** amend `AGENTS.md` to allow `frontend/`. |
| 4 | **No CORS middleware.** | `src/qme/main.py:30-49` | Cross-origin dev impossible without proxy | Vite proxy (dev) + same-origin serving (prod); optional server CORS later. |
| 5 | **No server-side results/history endpoint.** | No `GET` for results (`testgen.py:112-203`) | No cross-device history | Client-persisted only; never promise "past tests". |
| 6 | **No bank search endpoint.** | Only `GET /bank/meta` | Overview/formulas search must be client-side | Acceptable at ~1,300 questions; revisit at 10× growth. |

### 17.2 Open design/product questions

| # | Question | Default assumed | Needs owner decision? |
|---|---|---|---|
| Q1 | One-question-at-a-time (wizard) vs. stacked list in the runner? | Stacked list (§8.3) — better for scanning; a wizard needs extra navigation state. | Yes, if preferred. |
| Q2 | Session vs. local storage for the draft? | `sessionStorage` default, `localStorage` behind a "continue where I left off" preference. | Minor. |
| Q3 | Show the seed to users? | Yes, read-only on setup — matches the API's reproducibility contract. | No. |
| Q4 | Dark mode? | Not P0; tokens are structured so it becomes a P1 token swap. | Optional. |
| Q5 | Chart library vs CSS bars? | CSS bars for P0 (§9.6). | Only if richer charts are wanted. |
| Q6 | Ever send `include_solutions: false`? | No — the friendly shape has no such field and hiding is client-side (§6-2). | No. |
| Q7 | Keep the admin section given FE-007/009/010 have no backend? | Build **shell only** with an honest `BLOCKED` state (§8.9). | Yes — confirm admin stays in scope. |
| Q8 | Topic filtering beyond one chapter on `/formulas`? | Index = chapter; topic dropdown inside detail (§8.7). | No. |

### 17.3 Assumptions carried forward (verify at P0 start)

1. The bank remains the three git-tracked contract files in `data/input/`
   (blueprint, question bank, knowledge) and `/bank/meta` stays small.
2. `X-API-Key` remains the only API auth; the UI has no login surface.
3. `docs/SHIPPING_PLAN.md` stays parked — P0 targets web only: no pywebview
   or packaging work in this spec.
4. The engine stays deterministic; no LLM call is reachable from these
   routes (verified: no LLM import in `src/qme/api/` or `src/qme/testgen/`).
5. Endpoint shapes in `API_INTEGRATION.md` match the deployed backend; any
   drift is corrected there first, then here.

---

*End of specification. Implementation begins at §15 P0-0.*



