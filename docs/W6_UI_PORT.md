# W6 reference + UI parity backlog

Detailed legacy UI surface is tracked in `docs/UI_LEGACY_PARITY_AUDIT.md`. Treat that file as the acceptance
matrix for pages, transitions, controls, states, and backend links. This backlog only defines implementation
slices; it is not sufficient by itself for "last button/setting" parity.

## Scope rules

- Curriculum panel is already implemented by T2.6/T2.7/T2.8. W6 builds or upgrades **4 panels**: reference,
  generator, checker, translator. U7 still verifies **5/5 tiles** because curriculum participates in e2e.
- Reference does not own catalog SQL. Catalog storage belongs to `app/modules/curriculum/repo.py`; reference is
  viewer/API/panel over the shared tables.
- `legacy/Content_generator/static/vendor/mermaid/mermaid.min.js` and `legacy/Content_generator/static/land.png`
  are not ported and are not line-budget inputs. Mermaid is a dependency/CDN decision; `land.png` is a binary asset.
- Static UI budget uses `line_budget.yaml`: `static_ui.max_lines = 12000` with `budget_override: true`.
- Every panel task must hit a real endpoint. A rendered `panel.html` without a working backend call is not done.

## Current State

- Done: R1 reference backend over shared repo; R3-R7 reference admin parity screens are wired through `/reference/*`.
- Done: U1-U7 UI parity path. `tests/test_ui_final_e2e.py` verifies 5/5 dashboard tiles, real panel routes,
  curriculum edit/export, generator from DB УП, checker evaluation, reference edit/review, and translator readme/document/video.
- Done: curriculum panel from T2.6/T2.7/T2.8 participates in U7 e2e.
- In current `main`, G5 and C1-C4 code exist. Treat them as parity/e2e verification targets, not as absent modules.

## R1 — reference service over shared repo

```
PORT reference service (R1). ONE task. Do not take the next one.
STEP 0 — GUARD: verify `legacy/Spravochnik/viewer/app.py` exists and is non-empty; `wc -l` it.
Also verify catalog SQL already lives in `app/modules/curriculum/repo.py`; grep for catalog methods
(`list_reference_competencies`, `list_skills`, `list_review_queue`, or existing equivalents).
If repo methods are missing, add them to `curriculum/repo.py`, not to `reference`.
STEP 1 — read relevant viewer routes/templates for competencies, profiles, reviews, catalog skill detail.
STEP 2 — implement/finish `app/modules/reference/{service.py,router.py}` as thin adapter over
`CurriculumCatalogRepo`. No raw SQL, no SQLAlchemy imports in `app/modules/reference`.
STEP 3 — tests: reference lists competencies, opens detail with skills/indicators, edits competency/skill,
resolves review queue item. Use in-memory SQLite schema via `create_catalog_schema`.
STEP 4 — `wc -l app/modules/reference/*.py`; grep SQL absence; test output.
DoD: reference reads/edits shared DB catalog; no second catalog layer; reference <=1500.
```

## U1 — design system / CSS consolidation

```
PORT UI design system (U1). ONE task. Do not take the next one.
STEP 0 — GUARD: verify `legacy/Content_generator/static/css/` exists; `wc -l` CSS files excluding generated/vendor.
Do not port minified vendor or image assets.
STEP 1 — read current `app/static/styles.css`, legacy `s21-{tokens,base,buttons,forms,dashboard,markdown}.css`.
STEP 2 — consolidate tokens/layout/buttons/forms/dashboard/markdown primitives into `app/static/styles.css`
or small `app/static/ui/*.css` files if needed. Keep controls dense and workbench-oriented.
STEP 3 — tests: all current panel pages render; visual smoke via static HTML assertions for shared classes.
STEP 4 — line count static total; document what CSS was intentionally not ported.
DoD: shared design primitives exist for all panels; no one-off per-panel CSS for common controls; no empty aesthetic shell.
```

## U2 — shell + markdown renderer

```
PORT UI shell and markdown rendering (U2). ONE task. Do not take the next one.
STEP 0 — GUARD: verify `legacy/Content_generator/static/js/modules/markdownRendering.js` exists and is non-empty;
`wc -l` it and `legacy/Content_generator/static/js/main.js`.
STEP 1 — read `markdownRendering.js`, `main.js` navigation/init parts, and current dashboard shell.
STEP 2 — move reusable shell/markdown behavior to `app/static/shared/` or a small module used by generator/checker/translator.
Use CDN/dependency for Mermaid; do not copy `vendor/mermaid.min.js`.
STEP 3 — tests: markdown preview renders sanitized markdown; Mermaid block is preserved/initialized without vendored bundle;
dashboard tile navigation still uses manifest `ui_panel`.
STEP 4 — line count and excluded vendor note.
DoD: generator/checker/translator can share markdown rendering; dashboard stays manifest-driven.
```

## U3 — generator panel

```
PORT generator panel (U3). ONE task. Do not take the next one.
STEP 0 — GUARD: verify legacy modules exist and are non-empty:
`generationFormState.js`, `generationRunView.js`, `generationResultTabs.js`, `generationPersistence.js`,
`generationPolling.js`, `methodologyPanel.js`, `metricsView.js`.
`wc -l` them.
STEP 1 — read only the modules needed for current endpoints (`/curriculum/plans`, `/generator/runs/from-curriculum`).
STEP 2 — upgrade `app/static/generator/panel.{html,js}` from thin shell to real DB-backed generation workflow:
select plan/project, run generator, render README/tabs/metadata/issues, expose methodology/gate state where endpoint provides it.
Do not reintroduce legacy polling if current backend is sync; keep adapter thin.
STEP 3 — tests: panel renders; JS references real `/generator/runs/from-curriculum`; router e2e creates plan then generates README.
STEP 4 — line count and list deferred legacy UI pieces.
DoD: generator panel runs real generation from DB-backed UP and displays output.
```

## U4 — checker panel

```
PORT checker panel (U4). ONE task. Do not take the next one.
STEP 0 — GUARD: verify legacy checker modules exist and are non-empty:
`checkerPage.js`, `checkerReadmePreview.js`, `checkerMetricsSwitch.js`, `checkerDiffView.js`,
`checkerImprovementModal.js`, `checkerImprovementRun.js`, `checkerCurriculumState.js`.
`wc -l` them.
STEP 1 — read current `app/modules/checker/{router.py,service.py,structural.py,didactic/}` and relevant legacy modules.
STEP 2 — upgrade `app/static/checker/panel.{html,js}` to real checker workflow:
README input/upload, deterministic structural/content endpoint, markdown preview, issue table, structural vs didactic separation.
Do not call didactic jury by default unless endpoint/config exists for a controlled LLM run.
STEP 3 — tests: bad README hits `/checker/evaluate` and displays real issue codes; no mock JSON.
STEP 4 — line count and deferred legacy improvement-loop pieces.
DoD: checker panel exercises W5 real endpoint and shows actionable defects.
```

## U5 — translator panel + backend

```
PORT translator panel/backend (U5). ONE task. Do not take the next one.
STEP 0 — GUARD: verify translator sources exist and are non-empty:
`legacy/Content_generator/content_gen/agents/translator.py`,
`legacy/Content_generator/content_gen/agents/translation_refiner.py`,
translator static module `translationPage.js`, and any subtitles/video helpers.
`wc -l` them.
STEP 1 — read translator agent/refiner/router/static module. Prompts go to `core/llm/prompts/translator/`.
STEP 2 — implement `app/modules/translator/{service.py,router.py}` and upgrade
`app/static/translator/panel.{html,js}` for doc translation and video/subtitle workflow supported by the port.
STEP 3 — tests: mock LLM doc translation; subtitle/video path uses deterministic parser/mux adapter where possible;
panel hits real translator endpoint.
STEP 4 — line count against translator <=2500; list video pieces deferred only if no source adapter exists.
DoD: translation doc+video works through module endpoint and panel.
```

## U6 — reference panel parity

```
PORT reference panel parity (U6). ONE task. Do not take the next one.
STEP 0 — GUARD: verify `legacy/Spravochnik/viewer/templates/{competencies.html,competency_detail.html,profiles.html,reviews.html}`
exist and are non-empty; `wc -l` them plus `viewer/static/styles.css`.
STEP 1 — read those templates and current `app/static/reference/panel.{html,js}`.
STEP 2 — upgrade reference panel to cover competencies, profiles, skills, indicators, aliases, review queue decisions.
Keep API calls on `/reference/*`; no direct DB access from frontend.
STEP 3 — tests: panel renders; API test edits competency/skill and resolves review; frontend static assertions cover controls.
STEP 4 — line count and list legacy admin pages intentionally deferred.
DoD: reference panel is a usable viewer/editor over shared catalog, not a list-only shell.
```

## U7 — UI final e2e

```
FINALIZE W6 UI e2e (U7). ONE task. Do not take the next one.
STEP 0 — GUARD: verify 5 module manifests have `ui_panel`: generator, checker, translator, curriculum, reference.
STEP 1 — run route/static tests for `/`, `/api/modules`, and each `/static/<module>/panel.html`.
STEP 2 — add e2e tests:
curriculum import/edit/export; generator from DB plan; checker evaluates bad README; reference edits shared catalog;
translator translates via mock LLM or deterministic fixture.
STEP 3 — optional Playwright/browser smoke if available; otherwise FastAPI TestClient + static contract tests.
STEP 4 — total static line count vs 12000 and reference line count vs 1500.
DoD: all 5 tiles navigate to live panels that hit real endpoints; no panel is a pure placeholder.
```
