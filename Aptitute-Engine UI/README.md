# Aptitude Engine UI

Frontend work for the Aptitude Engine (QME) Test & Practice API — design
spec, API reference, and (to be built) the Vite + React + TypeScript app.

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

## Planned stack

- **Vite + React 18 + TypeScript (strict)**
- **react-router v6**
- **Tailwind CSS** with design tokens (spec §9)
- **React Query** for server state; `localStorage` for drafts/results
- **Vitest + React Testing Library**

No frontend exists in the repository yet — the app will be scaffolded at
spec §15 **P0-0**, which also requires amending `AGENTS.md` to permit a
`frontend/` directory (currently: no code outside `src/qme/` and `tests/`).

## Running it (after scaffold)

```bash
# backend (terminal 1)
make run-api          # uvicorn qme.main:app --reload  → http://localhost:8000

# frontend (terminal 2)
cd frontend
npm install
npm run dev           # http://localhost:5173, dev proxy → API origin
```

Vite must proxy `/api/*` to the API origin: **the backend ships no CORS
middleware**, so cross-origin calls fail without it (spec §6-4).

API health check:

```bash
curl http://localhost:8000/api/v1/health
```

If `QME_API_KEY` is set, requests (except `/health`) require the
`X-API-Key` header — handled by the dev proxy, never hardcoded in source.

## Layout

```
Aptitute-Engine UI/
├── README.md              ← this file (index)
├── UI_DESIGN_SPEC.md      ← build specification (17 sections)
└── API_INTEGRATION.md     ← API reference + TS types + client
```

> Folder name matches the owner's requested spelling (`Aptitute-Engine UI`).
> Creating files here is a deliberate, owner-approved exception to the
> `AGENTS.md` rule that docs live in `docs/`.

## Verification before reporting done

Spec §16.2: `tsc --noEmit` clean, tests green, keyboard-only walkthrough,
360/768/1280px check, no secrets in `dist/`, no `BLOCKED` endpoint calls.
