# Aptitude Engine UI

Frontend for the Aptitude Engine (QME) Test & Practice API — design spec, API
reference, and the Vite + React + TypeScript app.

## Read in this order

| # | File | What it is | When |
|---|---|---|---|
| 1 | [`UI_DESIGN_SPEC.md`](./UI_DESIGN_SPEC.md) | **Build contract.** Product understanding, journeys, route map, page layouts, design system, components, state rules, API→UI mapping, roadmap, acceptance criteria. | First, before writing code. |
| 2 | [`API_INTEGRATION.md`](./API_INTEGRATION.md) | **API reference.** Endpoint-by-endpoint schemas, error envelope, full TypeScript types, typed fetch client, React/Next examples. | During implementation, as reference. |

Rules of the road:

- The spec is the design authority; `API_INTEGRATION.md` is the
  field-level authority. **The backend and `docs/API_CONTRACTS.md` win over
  both** — raise drift as a doc bug.
- Build **P0 first** (spec §15). Do not start P1 until spec §16 P0 criteria
  pass.
- Anything marked `BLOCKED` in the spec must ship as a status panel only —
  never fake data. The endpoints do not exist (HTTP 404).

## Scope status

| Area | Status |
|---|---|
| Test setup → timed runner → report | `AVAILABLE` |
| Practice (paginated, seed-stable) | `AVAILABLE` |
| Formulas / knowledge viewer | `AVAILABLE` |
| Bank overview & coverage | `AVAILABLE` |
| Admin (batches / review / metrics) | `BLOCKED` — no backend endpoints |
| Activation gate, desktop packaging | `FUTURE` — see `docs/SHIPPING_PLAN.md` |

## Stack (built)

- **Vite 4 + React 18 + TypeScript (strict)** — `npx tsc --noEmit` clean
- **react-router v6** (`BrowserRouter`; all routes declared in `src/App.tsx`)
- **Tailwind CSS** with design tokens (spec §9)
- **Hand-rolled typed client** (`src/lib/qme-client.ts`) — no React Query;
  `localStorage` holds drafts and submitted results
- **Vitest** — 41 tests over the API layer, the rule table, and answer leakage

> `AI_RULES.md` specifies shadcn/ui, lucide-react, react-hook-form, zod,
> Zustand, React Testing Library and a default page `src/pages/Index.tsx`.
> None of those are installed and none is reachable from `App.tsx` — the file
> **drifts from the design spec's own route map (§8.4)**. Built to the design
> spec; `AI_RULES.md` needs reconciling. Flagged as a doc bug, not silently
> followed.

## Running it

Two terminals, both from `Aptitute-Engine UI/aptitute-engine-ui/`.

```bash
# terminal 1 — backend, from the repository root D:\Projects\Aptitude-Engine
python -m uvicorn qme.main:app --host 127.0.0.1 --port 8000

# terminal 2 — frontend
cd "Aptitute-Engine UI\aptitute-engine-ui"
npm install
npm run dev           # http://127.0.0.1:5173
```

`make run-api` needs GNU make, and the repo `env\` venv has no FastAPI — use
the command above (system Python 3.11 with `fastapi`/`uvicorn` installed).

### Proxy

The backend ships **no CORS middleware**, so the browser must only ever talk
to our own origin. `vite.config.ts` rewrites:

```
browser  /api/qme/<path>   →   http://localhost:8000/api/v1/<path>
```

`qme-client.ts` keeps its default `baseUrl` of `/api/qme`, so neither the API
version nor the key is ever bundled. Set `QME_BASE_URL` to point the proxy
elsewhere; set `QME_API_KEY` and the proxy injects `X-API-Key` itself (unset
⇒ the API is open). Vite needs no `@types/node`: config reads env through
`loadEnv`.

### Gates

```bash
npx tsc --noEmit      # strict, no errors
npx vitest run        # 41 tests
npm run build         # vite build, clean
curl http://127.0.0.1:8000/api/v1/health
```

## Layout

```
Aptitute-Engine UI/
├── README.md                  ← index (owner-facing)
├── UI_DESIGN_SPEC.md          ← build specification (17 sections)
├── API_INTEGRATION.md         ← API reference + TS types + client
└── aptitute-engine-ui/        ← the app
    ├── README.md              ← this file
    ├── vite.config.ts         ← /api/qme → /api/v1 proxy rewrite
    ├── postcss.config.js
    └── src/
        ├── App.tsx            ← all route declarations
        ├── pages/             ← 11 pages per spec §8
        ├── components/        ← 16 presentational components + ErrorBanner/EmptyState
        ├── hooks/             ← useBankMeta, useHealth, usePractice, useCreateTest,
        │                        useSubmitTest, useKnowledge, useDraft
        ├── lib/               ← qme-client (ApiError), test-rules, practice-rules
        └── types/             ← qme.ts (contract), admin.ts (BLOCKED stubs)
```

> Folder name matches the owner's requested spelling (`Aptitute-Engine UI`).
> Creating files here is a deliberate, owner-approved exception to the
> `AGENTS.md` rule that docs live in `docs/`.

## Verification before reporting done

Spec §16.2: `tsc --noEmit` clean, tests green, keyboard-only walkthrough,
360/768/1280px check, no secrets in `dist/`, no `BLOCKED` endpoint calls.
