# Shipping Plan: Desktop Product (.exe) + React Web UI

> **Status: PARKED (2026-10-05) — not active work.**
> Owner decision: update the present QME before shipping. Active work remains
> per `AGENTS.md`. This document is a reference for when shipping resumes.

## 1. Goal

Distribute the test/practice engine as a Windows desktop product:

- Ship as an **installer `.exe`** with **product-key activation**.
- After activation, run as a **web application** (React frontend for UI/UX)
  inside a **native window (pywebview)** over a local FastAPI server.

Scope decisions (owner, 2026-10-05):

| Decision | Choice |
|---|---|
| Feature scope | **Test/practice engine only** — deterministic, offline after activation. The LLM pipeline (M3/M4) stays server-side. |
| Licensing | **Online activation** — phone home to your server; keys revocable, seat control. |
| Runtime UX | **Native window (pywebview)** over `127.0.0.1:<free port>`. |
| Frontend scope | **Student-facing only** — take test, practice, results, formulas. |

Why not bundle LLM features: a Gemini key inside a distributed `.exe` can be
extracted by anyone. LLM features in a shipped product would require a server
proxy (internet required, usage limits) or user-supplied keys — out of scope.

Note: the existing `X-API-Key` protects the *server*; the **product key** is a
separate licensing concern.

## 2. Architecture

```
QME-Setup-x.y.z.exe  (Inno Setup)
└── app/
    ├── qme.exe              ← PyInstaller (FastAPI + uvicorn + pywebview + license)
    ├── frontend/dist/       ← React build (static, served same-origin)
    └── data/input/          ← 3 contract files (~1.7 MB, git-tracked)

First run → native pywebview window → localhost:<free port>
  ├── /activate   (React, gated until product key verified online)
  └── /           (test / practice / formulas, licensed)

Railway (your server) adds:
  POST /api/v1/license/activate   ← public, phones home, SQLite on a Volume
  GET  /api/v1/license/status     ← re-validation / seat checks
```

**Auth split:**

- Railway keeps `X-API-Key` auth for testgen (internal use — rotate the weak
  `12345` key before shipping).
- Desktop mode (`QME_MODE=desktop`) swaps the API-key dependency
  (`src/qme/api/routes/testgen.py` `_require_api_key`) for a local license
  token check on testgen routes.
- Health stays open. Activation endpoints are public + rate-limited.

**Bank data:** the three contract files
(`aptitude_test_blueprint.json`, `book_questions_agent_ready.jsonl`,
`aptitude_agent_knowledge.json`) ship inside the installer. PyInstaller must
bundle only these — `data/input/` also holds gitignored junk.

## 3. License flow

1. **Local format check** — product keys like `QME-XXXX-XXXX-XXXX-XXXX` carry
   a check digit / HMAC so malformed keys fail instantly (good UX, no round
   trip).
2. **Online activation** — desktop POSTs key + stable **machine-ID hash**
   (hostname + user + machine GUID, hashed) to the server.
3. **Server records** — key → machine binding, seat limit (e.g. 1 machine),
   key state (active/used/revoked) in SQLite (Railway Volume — see §7).
4. **Signed token** — returned to the client, stored at
   `%APPDATA%/QME/license.dat` (key id, machine id, expiry, signature).
5. **Enforcement** — desktop gate validates the token signature locally;
   re-phones-home on launch. Server unreachable ≠ invalid key (bounded retry
   window); revoked/used key ⇒ deactivate + show activation screen again.

## 4. Phases

### Phase 0 — Decisions & docs (small)

- Amend `AGENTS.md`: allow `frontend/` and `packaging/` (current rule: "no
  code outside `src/qme/` and `tests/`"); add shipping milestone entry.
- `docs/API_CONTRACTS.md` §1.8: license endpoint models + error codes
  (`KEY_INVALID`, `KEY_REVOKED`, `SEAT_LIMIT`, ...).

### Phase 1 — License system (backend)

New `src/qme/license/`:

- `machine_id.py` — stable hashed machine identity.
- `keys.py` — key format + HMAC validation.
- `store.py` — SQLite store (server side).
- `token.py` — signed local tokens.
- `client.py` — activation client.

Also: routes `src/qme/api/routes/license.py` (public, simple rate limit),
key-generation tool `python -m qme.tools.gen_keys`, desktop gating dependency
wired into the testgen router.

**Tests:** pure unit + TestClient integration, no network (client mocked) —
the offline suite stays green.

### Phase 2 — Static serving + desktop runtime

- `src/qme/main.py`: mount `frontend/dist` + SPA fallback (API routes
  untouched); CORS only in dev (prefer frontend dev-server proxy).
- New command `qme desktop`: pick free port → uvicorn on a worker thread →
  `webview.create_window()` on the main thread (standard pattern).
- Settings additions: `qme_mode`, `qme_activation_url` (baked at build),
  license path.

### Phase 3 — React frontend (`frontend/`, largest workstream)

- **Stack:** Vite + React + TypeScript, react-router, Tailwind (TBD — plain
  CSS an option), vitest for logic tests.
- **Screens:**
  1. Activation gate (enter product key)
  2. Test setup — friendly shape driven by `GET /bank/meta` discovery
  3. Runner — client-enforced timer, answer hiding, localStorage draft
  4. Submit → Results — score, breakups, review with solutions
  5. Practice — filters + seed/page pagination, client-side reveals
  6. Formulas/shortcuts viewer — `GET /chapters/{key}/knowledge`
- Results stored **client-side (localStorage)** per the API v2 contract — no
  server persistence.
- Dev: `npm run dev` proxying to local or deployed API.

### Phase 4 — Packaging (`packaging/`)

- `qme_desktop.spec` — PyInstaller **onedir** (faster startup, fewer AV false
  positives than onefile); data files = 3 bank files + frontend dist; known
  uvicorn/asyncio hidden-import boilerplate.
- `installer.iss` — Inno Setup: files, Start-menu shortcut, uninstaller.
  **No key entry in the installer** — activation happens in-app so
  re-activation/transfer works.
- `build.ps1` — one command:
  `npm ci && npm run build → pyinstaller → ISCC → QME-Setup-<version>.exe`.

### Phase 5 — Ship checklist

- Fresh-Windows E2E: install → activate → take test → results.
- Generate a key batch (`qme.tools.gen_keys`) + load into the Railway store.
- Attach the Railway **Volume** for the SQLite license DB.
- Rotate the `12345` API key.
- README shipping section.

## 5. Prerequisites (dev machine)

- **Node.js / npm** — frontend build.
- **Inno Setup** (`ISCC.exe`) — installer compile.
- **pyinstaller**, **pywebview** (pip) — code stays under allowed dirs;
  spec/scripts live in `packaging/` per the Phase 0 AGENTS.md amendment.

## 6. Suggested session order

One phase per session (repo rule: one step per session):
Phase 0 → 1 → 2 → 3 (likely 2–3 sessions: setup/activation, test flow,
practice+formulas) → 4 → 5.

## 7. Open items / risks

| # | Item | Notes |
|---|---|---|
| 1 | **Railway Volume = paid plan** (~$5/mo Hobby) | License DB must persist across deploys. Alternatives: tiny Postgres (also paid) or external KV — volume + SQLite is simplest. |
| 2 | **WebView2 runtime** | Bundled with Win11 / most Win10; installer detects & prompts if missing. |
| 3 | **AV false positives** | Unsigned PyInstaller exe — common; code-signing cert (~$100s/yr) optional for v1. |
| 4 | **No auto-update in v1** | Updates = re-ship installer; activation response can later hint the latest version. |
| 5 | **Styling** | Tailwind proposed — decide vs plain CSS at Phase 3 start. |
