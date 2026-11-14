# CLAUDE.md — data_nebula

Operating guide for Claude Code in this repo. **This file is the single source of truth.**
Any other agent/rule file (`AGENTS.md`, `.cursorrules`, `GEMINI.md`, `docs/*`) is a thin
pointer back here with no rules of its own. If two files disagree, this one wins, and the
other gets fixed in the same change. Stale companion docs are a bug, not background noise.

## What we are building

Our entry for the **2026 NASA Space Apps Challenge — "Dancing with the SARs"**
(https://www.spaceappschallenge.org/2026/challenges/dancing-with-the-sars/ · Earth Science ·
Intermediate/Advanced).

- **Brief:** an interactive application that uses radar data from the **NASA-ISRO Synthetic
  Aperture Radar (NISAR)** mission to track and visualise one or more types of Earth-surface
  change (wetlands/floods, deforestation/wildfire, crops, soil moisture, glaciers/sea ice,
  earthquakes/subsidence) at locations around the world.
- **Outcome NASA wants:** open-source, user-friendly; turns complex radar observations into
  insights for scientists, resource managers, educators, decision-makers and the public.
  Typical forms: interactive change-detection maps, time-series animations, dashboards,
  image sliders, story maps.
- **Flow:** pick a study area → download NISAR data (plus optical/GIS layers for context) →
  present it interactively → explain the physical drivers behind what the SAR shows (or
  doesn't), which polarisations reveal it, and future NISAR uses.
- **Optional extras the brief suggests:** several polarisations/frequencies (other sensors),
  multi-date time series, ancillary data (population, vegetation type), human drivers
  (agriculture, industry), strong storytelling, personal context for a familiar study area.
- **SAR basics that shape the product:** works day/night and through clouds; backscatter
  depends on surface roughness and the dielectric constant (water shows up strongly →
  floods, soil moisture); InSAR measures centimetre-scale ground movement.

**Data sources (from the challenge Resources tab):**

| Source | Use |
|---|---|
| ASF Data Search Vertex — https://search.asf.alaska.edu/ | Main NISAR download |
| NISAR Data User Guide — https://nisar-docs.asf.alaska.edu/ | Product formats, levels, polarisations |
| NASA Earthdata Search — https://search.earthdata.nasa.gov/search | NISAR + optical/ancillary layers (needs Earthdata login) |
| Earthdata SAR intro — https://www.earthdata.nasa.gov/learn/earth-observation-data-basics/sar | Background |
| NASA ARSET trainings — https://appliedsciences.nasa.gov/get-involved/training | Processing tutorials |
| NISAR StoryMaps / applications — https://nisar.jpl.nasa.gov/applications/arcgis-storymaps/ | Presentation inspiration, use cases |
| CSA SAR Python tutorial — https://github.com/asc-csa/Synthetic_Aperture_Radar_Tutorial | Processing examples |
| RADARSAT-1 / RCM (CSA), SAOCOM (CONAE) catalogues | Extra frequencies / longer history |

**Domain rules that follow from this:**
- **Heavy raster work happens offline, never in a request.** A pipeline step downloads and
  preprocesses granules into web-ready outputs (Cloud-Optimised GeoTIFFs / map tiles /
  small JSON time series). The API serves those results. The web app never parses raw HDF5.
- **Record provenance for every derived layer:** granule/product ID, acquisition date (UTC),
  frequency band, polarisation, processing step and version. The UI shows date and
  polarisation next to every image. A change map without its two dates means nothing.
- **Pipelines are reproducible:** one script/command rebuilds every derived layer from the
  source IDs in a committed manifest. Raw downloads are gitignored and cached locally.
- **Earthdata/ASF credentials are secrets** (env only, §7). Respect each source's licence and
  attribute it in the app.
- **Hackathon time-box:** build one study area and one change type end to end first (data →
  layer → map → explanation), then widen. A working thin slice beats a half-built platform.
- The repo must be **open source**: keep a licence file and a README that lets judges run it.

## Response protocol (required)

Reply in a formal, minimal structure. Use only the sections that apply, in this order, as
short bullets — no filler prose:

- **Goal** — what the user wants, one line.
- **Catches** — constraints, hidden assumptions, things that will bite.
- **Problems** — what is actually wrong / root cause.
- **Suggestions** — options considered, with trade-offs.
- **Solution** — the chosen approach, one line.
- **Fixed** — what changed (file:line) and the verification result.

---

## 1. Project shape

Two deliverables in one repo: a **backend API** and a **web application**, joined by a
generated contract.

```
data_nebula/
├── CLAUDE.md                  # this file (source of truth)
├── backend/                   # API service (+ pipeline/ for offline NISAR preprocessing)
├── web/                       # web client (interactive map, time series, story)
├── data/                      # manifest.json + ext/ committed; raw/, derived/ gitignored;
│                              #   web/ = website data from the export (served by web/ at /data)
├── contracts/                 # openapi.json (generated from backend, committed)
├── docs/
│   ├── architecture.md        # how it fits together (pointer-only for rules)
│   ├── decisions/             # ADRs: YYYY-MM-DD-<topic>.md, one decision each
│   └── wiring-notes.md        # what is wired / stubbed / local-only today
└── .github/workflows/         # CI (one gate workflow)
```

### Stack — fill in when decided (update this table, not a side doc)

| Layer | Default unless decided otherwise | Decided |
|---|---|---|
| Backend | Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, uv, ruff, pyright, pytest | Python 3.12, FastAPI, Pydantic v2 + pydantic-settings, numpy, Pillow, uv, ruff, pyright, pytest. Read-only API, no SQLAlchemy/Alembic |
| Database | PostgreSQL; Redis only for cache/queues | None: the API serves files the pipeline wrote to `data/derived/` |
| Web | TypeScript (strict), React (Vite or Next.js), TanStack Query, generated API client, Vitest + Testing Library, Playwright for e2e | React 19 + Vite + TS strict, oxlint; small `useJson` hook instead of TanStack Query; no tests yet (hackathon) |
| Geo pipeline | Python: rasterio/GDAL, xarray + h5py (NISAR HDF5), asf_search / earthaccess for downloads; outputs COGs | `backend/pipeline/`: h5py, rasterio, scipy (uv group `pipeline`). Every source ends in `pipeline/writer.py:write_site` → PNG layers + `stack.npz`, no COGs |
| Tile serving | TiTiler (COG → XYZ tiles) or pre-rendered static tiles | One pre-rendered transparent PNG per layer and date, placed by the site's four corners (EPSG:3857 grid) |
| Web map | MapLibre GL JS (or Leaflet); time slider + swipe compare; charts for time series | MapLibre GL 6, CARTO dark basemap, own swipe compare and SVG chart (no extra deps) |
| Auth | One identity provider; backend verifies tokens; web never trusts its own role checks | TBD |

Commands live in §8 — keep them exact and runnable once the stack is set.

---

## 2. Architecture rules

### 2.1 Feature-first, both sides
Group by feature, not by technical layer. Shared code goes in `core/` only when two or more
features actually use it.

```
backend/app/
├── main.py                    # composition root: app, middleware, router registration
├── core/                      # config, security, errors, logging, db session — no features
└── features/<feature>/
    ├── routes.py              # HTTP only: parse, call service, map result → response
    ├── dependencies.py        # auth, db session, injected services
    ├── service.py             # business rules (pure where possible)
    ├── repository.py          # DB access only
    ├── models.py  schemas.py  # ORM models / request-response DTOs
    └── tests/                 # unit (fast) + integration (marked)

web/src/
├── main.tsx  app/             # composition root: providers, router, error boundary
├── core/                      # api client wrapper, auth, ui kit, theme tokens, utils
└── features/<feature>/
    ├── pages/  components/  hooks/  api/  model/
```

### 2.2 Dependency direction (enforced, never reversed)
- Backend: `routes → dependencies → service → repository → models`. Routes hold no
  business logic; services never import routes or FastAPI request objects;
  repositories never call other services.
- Web: `pages → components/hooks → feature api → core`. Components never call `fetch`
  directly; data access goes through the feature's `api/` hooks.
- `core/` imports **nothing** from `features/`. Check before merging:
  `grep -r "features/" backend/app/core web/src/core` must return nothing.
- No feature imports another feature's UI components. Shared state/identity
  (current user, session) lives in `core/`.
- Composition (wiring concrete implementations) happens only in the root
  (`main.py`, `app/`).

### 2.3 The contract is generated, never hand-mirrored
- Backend Pydantic schemas → `contracts/openapi.json` → generated TS client in `web/`.
- Never hand-write a TS type that copies a backend DTO. Drift then shows up as a compile
  error, not a 422 in production.
- Changing an endpoint = regenerate the contract + client in the **same change**, and CI
  fails if the committed `openapi.json` differs from what the backend renders.
- Every route declares `summary`, `description`, response model, and its error responses
  (401/403/404/409/422). URLs kebab-case (`/api/v1/user-profile`), JSON snake_case.
- A committed or vendored spec goes stale. When in doubt, read the backend source, not the
  snapshot.

### 2.4 The server is the authority
- Every rule that protects fairness, money, permissions or data integrity is enforced
  **on the backend**. A UI that only hides a button enforces nothing. Client checks are UX only.
- The server owns the clock: deadlines, expiries and countdown ends come from server
  timestamps (UTC, ISO-8601). The web only displays them.
- Payloads carry **explicit state** (`status: "pending" | "active" | "ended" | ...`). The client
  must not infer state from which endpoint or list a record came from.
- **One ID space per entity.** Never compare IDs from different systems (auth uid vs DB id).
  If two exist, name them distinctly (`user_id`, `auth_uid`) and derive relationships from
  explicit fields (`actor_role`, `owner_id`), not from guessing an ID match.
- Writes that may be retried (payments, submissions) take an idempotency key.

### 2.5 Data, migrations, caching
- Schema changes only via migrations. Never edit an applied migration. Use
  expand → migrate data → contract for anything live.
- Every cache names its **owner, TTL, and invalidation trigger** in a code comment. A write
  that changes cached data must invalidate it in the same code path. "Stale for 10 minutes"
  is a product decision, so record it in `docs/decisions/`.
- Web server-state lives in the query cache (TanStack Query or equivalent), not copied into
  global UI state. Anything loaded while signed out **must refetch when auth changes**
  (sign-in, sign-out, role switch). Otherwise it shows another identity's data.

### 2.6 Errors and logging
- Backend raises typed domain errors → one handler maps them to
  `{ "error": { "code": "auth.invalid_token", "message": "...", "details": {...} } }`.
  Codes are stable and catalogued in `docs/api/error-codes.md`. No raw stack traces to clients.
- Web shows the server's `message` for validation errors. Never swallow an error into an
  empty state.
- One logger wrapper per side. No `print` / stray `console.log`. Every request carries a
  request ID from web → backend → logs, so one action can be traced end to end.
- Never log secrets, tokens, or full personal data.

### 2.7 Unwired, stubbed, local-only
When a surface is not backed by a real endpoint yet:
- Mark it `TODO(<area>-api)` at the call site and list it in `docs/wiring-notes.md`.
- Never render defaults (0, empty list, "No reviews") as if they were real data. Show an
  explicit "not available yet" state.
- When wiring it: grep every reader of that data, confirm each now shows live data, remove
  the TODO and stub, and update `wiring-notes.md`.

### 2.8 Parallel flows move together
When two flows share shape (create/edit, list/detail, role A/role B signup, web admin/web
user), a change to one is audited on the other **in the same change**, or they are unified.
Most "works for X, broken for Y" bugs come from migrating only one branch.

---

## 3. Code health (Boy Scout rule)

Every change leaves the touched area better, never worse.

- **File size:** a file over ~400 lines is a smell; over 600 lines it must not grow. Extract
  a cohesive block when you touch it.
- **Functions:** over ~50 lines or nesting depth over 4 → extract helpers, return early.
- **Reuse first:** before adding a component/hook/service/schema/endpoint, search `core/`
  and the feature. Prefer extending an existing endpoint or schema over adding a parallel one.
- **Deletion over addition:** before deleting anything an audit calls "dead", grep every
  caller (including dynamic/string references, routes, tests, templates).
- **DRY on contact:** if the code you edit has an obvious duplicate, consolidate it in the
  same change.
- **DI for testability:** services take their collaborators (db session, HTTP client,
  clock) as constructor/function parameters, never `SomeService()` at a call site.
  Tests pass fakes.
- **Styling (web):** use design tokens / theme variables; no raw hex or magic spacing unless
  matching an existing pattern. Interactive elements are real `<button>`/`<a>` with
  accessible labels.
- **No rule-level lint ignores** without asking. Fix the cause.
- Match surrounding style; minimal, targeted diffs; comments in English and explain *why*,
  not *what*.

---

## 4. Building: how to approach a task

1. **Clarify first** for anything new or ambiguous: purpose, constraints, success criteria.
   Propose 2–3 approaches with trade-offs and a recommendation before writing code.
2. **Plan multi-step work** before touching code: files to create/modify (exact paths),
   interfaces between steps, and the tests that prove each step. List unit and integration
   cases in the plan. Plans go in `docs/plans/YYYY-MM-DD-<feature>.md` only when asked;
   otherwise keep them in chat.
3. **Test first (TDD).** Write the failing test, run it and see it fail for the right reason,
   write the minimal code to pass, run it green, then refactor while staying green.
   For bug fixes the failing test reproduces the bug.
4. **Contract changes go backend-first:** schema + route + tests → regenerate contract →
   web client + UI → tests.
5. **Small vertical slices** that are each shippable and testable on their own, instead of one
   large change across all layers.
6. **Two-speed testing:** while iterating, run only the fast lane scoped to the touched
   feature. Before calling work done, run the **full** gate (§8). CI is the authoritative gate.

---

## 5. Debugging: find the root cause, then fix

**Iron law: no fix without root-cause investigation first.** Symptom patches are failure.

1. **Read the error completely:** full stack trace, file:line, error code, the request ID.
2. **Reproduce reliably.** Write down exact steps. If you can't reproduce it, gather more
   data. Don't guess.
3. **Check what changed:** `git diff`, recent commits, dependency bumps, env/config, data.
4. **Instrument the boundaries** in multi-layer paths (browser → API → service → DB →
   cache → external): log what enters and leaves each layer once, find *where* it breaks,
   then dig into that layer only. Look at the network tab and the server log for the same
   request ID together.
5. **Trace bad values backward** to their origin and fix them at the source, not where they surface.
6. **Compare with a working example** in the codebase (the parallel flow, the sibling
   endpoint) and list every difference.
7. **One hypothesis at a time:** state it, make the smallest change that tests it, observe.
   Don't stack fixes.
8. **Lock it in:** write a failing regression test, then fix. Verify red→green: revert the fix,
   the test must fail; restore it, the test must pass.
9. **Three failed fixes = stop.** The architecture or your mental model is wrong. Step back
   and reassess with the user instead of trying a fourth patch.

Common traps to check early: stale cache or query cache not invalidated; signed-out data
kept after sign-in; client/server clock or timezone mismatch; ID from the wrong ID space;
contract drift (stale generated client); env var missing in one environment; a parallel
flow left on old behaviour.

---

## 6. Verification before saying "done"

**Evidence before claims.** Don't say "fixed", "passing", or "works" unless a command run in
this turn shows it.

| Claim | Requires |
|---|---|
| Tests pass | Fresh test output with 0 failures |
| Lint/types clean | Fresh lint + typecheck output with 0 errors and 0 warnings |
| Builds | Build command exited 0 (lint passing is not a build) |
| Bug fixed | Original symptom re-tested + regression test red→green |
| UI works | Ran the page in a browser and exercised the flow. If not, say "not checked in the browser" |
| Subagent finished | Read the diff yourself. Don't trust the report |

- Never claim a UI flow is tested unless an automated test covers it.
- If a test that your change broke was guarding something real, name what it guarded and
  **ask** before rewriting or deleting it.
- Report partial status honestly: what passed, what failed (with output), what was not run.

---

## 7. Security and secrets

- Secrets only in gitignored env files (`backend/.env`, `web/.env.local`) and CI secrets.
  Never hardcode, commit, print, or echo them.
- Commit `.env.example` files with placeholder values. **Adding an env var = add it to
  `.env.example` + CI placeholders + config validation in the same change.**
- Backend: validate all input with schemas; authorize per resource (check ownership, not
  just being logged in); parameterized queries only; CORS allowlist; rate-limit auth and write
  endpoints.
- Web: never put tokens or personal data in URLs or `localStorage` when a cookie or memory
  will do; escape/sanitize any rendered HTML.

---

## 8. Commands and CI (fill in exact commands once the stack is set)

```bash
# backend/
uv sync                                   # deps (add --group pipeline to process real NISAR)
uv run ruff check . && uv run ruff format --check .
uv run pyright                            # types
uv run pytest -m "not slow"               # fast lane (scope to touched feature path)
uv run --group pipeline pytest            # full suite — required before done (the plain `uv run pytest` skips the pipeline tests)
uv run python -m app.export_openapi       # regenerate contracts/openapi.json after any API change
uv run python -m pipeline.make_demo_site  # synthetic demo site → data/derived/demo-reservoir/
uv run python -m pipeline.prepare_nisar   # real NISAR → same files
uv run --group pipeline python -m pipeline.rain --site <id>  # IMERG daily rain → data/ext/<id>/rain.json
uv run --group pipeline python -m pipeline.exposure --site <id>  # OSM buildings/roads → data/ext/<id>/
uv run --group pipeline python -m pipeline.optical --site <id>   # NASA HLS camera pictures → data/ext/<id>/
uv run --group pipeline python -m pipeline.catalog --site <id>   # NASA COOLR reports nearby → data/ext/<id>/
uv run python -m pipeline.export_static   # prepared sites → data/web/ (website data; web serves it at /data)
uv run uvicorn app.main:app --reload      # run on :8000; docs at /docs

# repo root: server image (API + data/derived/toguz-bulak baked in; see backend/Dockerfile)
docker build --platform linux/amd64 -f backend/Dockerfile -t data-nebula-api .
docker run -p 8080:8080 -e NEBULA_CORS_ORIGINS='["https://<web-domain>"]' data-nebula-api

# web/
npm ci
npm run lint && npm run typecheck         # oxlint + tsc -b
npm run build                             # tsc -b && vite build
npm run fake-data                         # regenerate FAKE public/data/ (until the backend export exists)
npm run dev                               # http://localhost:5173
# not set up yet: npm test, npm run test:e2e, npm run gen:api
```

- **Web deploy:** `.github/workflows/pages.yml` builds `web/` with `--base=/<repo>/` on push to
  `main` and publishes it to GitHub Pages (Settings → Pages → Source: GitHub Actions). The site
  data is the committed `data/web/`, so re-run `export_static` and commit it to update the site.
  Asset/data URLs must go through `import.meta.env.BASE_URL`, never a hardcoded `/`.
- **CI gate (one workflow):** lint + format check + typecheck + full tests with coverage +
  contract-drift check, for both apps, on PRs and the main branch. Warnings fail the build.
- **Coverage ratchet:** the stored minimum only goes up. Never lower it to make CI pass.
- Tag tests `slow` only if they really need a full DB/API lifecycle. Untagged runs in the fast
  lane by default, so a missing tag costs speed, never coverage.

---

## 9. Working agreement

- Branch before committing. **Never commit, push, or open a PR unless asked.** Don't offer to.
- Don't create new CI workflows, jobs, or extra config files unless asked. Edit the existing
  gate.
- Don't add dependencies or new state/HTTP/UI libraries without asking.
- Write findings in chat. Create `.md` files only when asked (ADRs and wiring notes are the
  standing exceptions above).
- Keep docs true: when behaviour changes, update `docs/wiring-notes.md`, the relevant ADR,
  and this file in the same change.
