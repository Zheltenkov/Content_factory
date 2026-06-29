# UI legacy parity audit

Статус: рабочий контракт переноса UI. Этот документ фиксирует полный surface legacy-экранов, переходов,
кнопок, состояний и backend-связок. W6 нельзя считать закрытой, пока каждая строка ниже не перенесена,
не покрыта тестом или явно не помечена как сознательно исключенная.

> **РЕВИЗИЯ ДОКТРИНЫ (см. `docs/REFACTOR_FIX_PLAN.md`, ADR-1).** Прежняя версия требовала
> **двух раздельных оболочек** (`s21-product` + «Рабочий контур методолога»). Это **отменено**.
> Решение владельца: **единая оболочка + полный функциональный паритет** — один S21-стиль на все
> пять модулей, но каждая legacy-кнопка/функция переносится без потерь. Инвентарь фич ниже
> (матрицы по страницам) остаётся в силе как чеклист функционала; меняется только доктрина оболочки.

## Принцип переноса

- **Один визуальный стиль для всех модулей** — S21-контур (`s21-product`). Справочник и УП
  переезжают с темы «Рабочий контур методолога» на ту же S21 дизайн-систему (миграция ~87
  `.methodologist-product` CSS-правил → `s21-product`; отдельный проверяемый срез со скриншотами).
- Методолог-навигация (Skills/Компетенции/Профили/Reviews/intake/УП/catalog-admin) сохраняется
  **как in-panel разделы** внутри единой оболочки, а не как второй top-shell.
- Верхняя навигация едина и ведёт ко всем 5 модулям: Главная · Генерация · Аудитор · Перевод ·
  Учебный план · Справочник · Документация.
- Каждый видимый legacy control должен быть либо живым, либо скрыт до готовности backend. Мертвые кнопки запрещены.
- Vendor/minified assets не портируются как код: `vendor/mermaid`, `vendor/mathjax`, `vendor/marked`, `land.png`.
- UI parity проверяется не скриншотом “похоже”, а матрицей: маршрут -> controls -> events -> endpoint -> state,
  плюс скриншот-проверкой единого стиля для перенесённых панелей.

## Legacy sources

### Content Generator

- Shell/pages:
  - `legacy/Content_generator/static/login.html`
  - `legacy/Content_generator/static/register.html`
  - `legacy/Content_generator/static/forgot-password.html`
  - `legacy/Content_generator/static/reset-password.html`
  - `legacy/Content_generator/static/app.html`
  - `legacy/Content_generator/static/index.html`
  - `legacy/Content_generator/static/checker.html`
  - `legacy/Content_generator/static/translator.html`
  - `legacy/Content_generator/static/instruction.html`
- Shared JS:
  - `legacy/Content_generator/static/js/main.js`
  - `legacy/Content_generator/static/js/modules/modelSelector.js`
  - `legacy/Content_generator/static/js/modules/stateStores.js`
  - `legacy/Content_generator/static/js/modules/markdownRendering.js`
  - `legacy/Content_generator/static/js/modules/curriculumForm.js`
- Generator JS:
  - `generationFormState.js`
  - `generationRunView.js`
  - `generationResultTabs.js`
  - `generationPersistence.js`
  - `generationPolling.js`
  - `metricsView.js`
  - `methodologyPanel.js`
  - `methodologyAssistantChat.js`
- Checker JS:
  - `checkerPage.js`
  - `checkerReadmePreview.js`
  - `checkerMetricsSwitch.js`
  - `checkerDiffView.js`
  - `checkerImprovementModal.js`
  - `checkerImprovementRun.js`
  - `checkerCurriculumState.js`
- Translator JS:
  - `translationPage.js`

### Spravochnik

- Shell/navigation:
  - `legacy/Spravochnik/viewer/templates/base.html`
  - `legacy/Spravochnik/viewer/route_zones.py`
  - `legacy/Spravochnik/viewer/static/styles.css`
- Workspace/templates:
  - `intake.html`
  - `up_index.html`
  - `up_detail.html`
  - `up_row_edit.html`
  - `up_template_proposals.html`
  - `competencies.html`
  - `competency_detail.html`
  - `profiles.html`
  - `profile_detail.html`
  - `reviews.html`
  - `catalog_admin_groups.html`
  - `catalog_admin_group_detail.html`
  - `catalog_admin_skill_detail.html`
  - `catalog_admin_skillsets.html`
  - `catalog_admin_skillset_detail.html`
  - `catalog_admin_candidate_competencies.html`
  - `catalog_admin_artifact_templates.html`
  - `catalog_admin_archive.html`

## Shell parity

### Content Generator shell

Source: `legacy/Content_generator/static/app.html`, `index.html`, `checker.html`, `translator.html`.

Must keep:

- Top nav labels and order: `Главная`, `Генерация`, `Проверка`, `Перевод`, `Инструкция`.
- Model picker: `openrouter`, `deepseek`, `gigachat`.
- User chip with initials/name and logout action.
- Page-specific brand marker:
  - generator: `ФОРМА ПАРАМЕТРОВ`, `учебных проектов · v 2.4`
  - checker: `ПРОВЕРКА`, `39 критериев · v 2.4`
  - translator: `ПЕРЕВОД ДОКУМЕНТА · RU → EN`
- Subbar with back link, active page title, status badge and right-side state.
- Auth/session behavior if auth is in scope: missing token redirects to login; logout clears local storage.

Current gap:

- Current app shell is a unified module dashboard, not the original CG shell.
- Dashboard lacks full `recent runs` behavior: open, download, cancel, active tasks, last run.
- Instruction page is not represented as a first-class UI route.

### Spravochnik shell

Source: `legacy/Spravochnik/viewer/templates/base.html`, `route_zones.py`.

Must keep:

- Wordmark: logo + `Рабочий контур методолога`.
- Primary nav:
  - `Рабочий стол` -> `/intake`, active for `/intake` and `/reviews`
  - `Справочник` -> `/catalog-admin/groups`, active for `/catalog-admin`, `/competencies`, `/profiles`
  - `УП` -> `/up`, active for `/up`
- Secondary catalog nav:
  - `Skills и индикаторы`
  - `Компетенции`
  - `Кандидатные компетенции`
  - `Профили`
  - `Шаблоны УП`
  - `Архив`
- Left summary panel:
  - `Профили`
  - `Компетенции`
  - `Skills`
  - `Индикаторы`
  - `Open review`
- Wide workspace mode for `/intake`, `/up`, `/reviews`.

Current gap:

- Current reference panel collapses Spravochnik into one S21-style tabbed panel.
- `intake`, `/up`, `catalog-admin`, archive and template proposals are not represented as original pages.

## Content Generator page matrix

### `/app`

Source: `legacy/Content_generator/static/app.html`.

Must keep:

- Hero title: `Генератор учебных проектов`.
- Service meta row: service available, last run, active tasks.
- Three mode cards:
  - Generation README -> `/app/generate`
  - README checker -> `/app/check`
  - Translation -> `/app/translate`
- Recent runs list:
  - load more via `Все запуски`
  - open result
  - download result if available
  - cancel running task
  - disabled state for failed/no-result run

Backend links:

- Legacy: `GET /api/v1/dashboard/recent`, `POST /api/v1/generate/cancel/{request_id}`.
- Current missing/partial: no equivalent recent-runs endpoint for generator/checker/translator history.

### `/app/generate`

Source: `legacy/Content_generator/static/index.html`, generator JS modules.

Must keep controls:

- CSV upload: `curriculumFile`.
- Methodology toggle: `methodologyHumanReview`.
- Program context:
  - `direction`
  - `curriculumBlock`
  - `thematicBlock`
  - add direction expander: `newBlockName`, `newBlockCode`, add button
  - `curriculumProject`
- Project params:
  - `projectType`
  - `groupSize`
  - `audienceLevel`
- Content:
  - `titleSeed`
  - `projectDescription`
  - `requiredTools`
  - `requiredSoftware`
  - `storytellingTypeHelpTrigger`
  - `storytellingType`
  - `storytelling`
  - `learningOutcomes`
  - `skills`
- Advanced:
  - `includeDiagrams`
  - `includeTables`
  - `includeFormulas`
  - `generateBonus`
  - `bonusWish`
  - `platformName`
  - `workloadHours`
  - `additionalMaterials`
  - `projectContentType`
  - `repoBaseUrl`
  - `repoPathTemplate`
- Actions:
  - clear form
  - generate
  - cancel generation
- Run view:
  - logs
  - timer/current agent
  - 8-stage timeline
  - checkpoint state
  - methodology review workspace
- Result:
  - score ring
  - words/tasks/assets summary
  - warnings
  - regeneration panel
  - tabs: README, Practice, Generated data, Metrics, Report, Regeneration
  - README mode: markdown, preview, compare
  - metrics/report version switcher original vs regenerated
  - download archive
  - download regenerated archive
- Methodology assistant:
  - chat
  - actions: continue, edit, accept, compare
  - target picker
  - suggestions
  - comment send

Backend links:

- Legacy async flow:
  - `POST /api/v1/upload`
  - `POST /api/v1/build-context`
  - `POST /api/v1/generate`
  - `GET /api/v1/generate/status/{request_id}`
  - `POST /api/v1/generate/cancel/{request_id}`
  - `GET /api/v1/download/{request_id}`
  - methodology review endpoints under `/api/v1/generate/review/{request_id}/*`
  - `POST /api/v1/regenerate`
- Current compact flow:
  - `POST /curriculum/plans/import-csv`
  - `GET /curriculum/plans`
  - `GET /curriculum/plans/{plan_id}/cascade`
  - `GET /curriculum/projects/{project_id}`
  - `POST /generator/runs/from-curriculum`

Current status:

- Generator controls are mostly present after latest pass.
- Missing parity: async status polling, persisted recent runs, real cancel endpoint, archive download,
  full methodology review action loop, real scoped regeneration endpoint and original route naming.

### `/app/check`

Source: `legacy/Content_generator/static/checker.html`, checker JS modules.

Must keep controls:

- README upload: `readmeFile`, remove file button.
- Learning outcomes expander: `learningOutcomes`.
- Curriculum context expander:
  - `checkerCurriculumFile`
  - `checkerCurriculumBlock`
  - `checkerCurriculumProject`
- Actions:
  - clear result
  - check README
- Result:
  - score ring
  - threshold badge
  - warnings area
  - improve README action
  - report-only action
  - tabs:
    - Criteria `39`
    - Text statistics
    - Source README
    - Improved README beta
  - metrics original/improved switcher
  - improved README download
- Improvement modal:
  - 4-step stepper
  - title, description, language
  - thematic block + add block expander
  - audience level
  - project type/group size
  - methodology toggle
  - learning outcomes
  - skills
  - required tools
  - tasks count
  - ZUN/context
  - bonus toggle/wish
  - repo base/path template
  - cancel/submit
- Improvement run view:
  - progress ring
  - stage index
  - timer/remaining
  - timeline

Backend links:

- Legacy:
  - `POST /api/v1/readme/check`
  - `POST /api/v1/readme/improve/extract`
  - `POST /api/v1/readme/improve/generate`
  - `GET /api/v1/readme/improve/status/{generation_request_id}`
  - `GET /api/v1/readme/improve/diff/{request_id}`
  - `GET /api/v1/readme/improve/download/{generation_request_id}`
- Current:
  - `POST /checker/evaluate`
  - `POST /checker/reverse-extract`

Current gap:

- Current checker panel is a thin evaluator, not the legacy checker/improvement workflow.
- Need decide whether improvement flow calls generator/refine or gets a checker-specific adapter.

### `/app/translate`

Source: `legacy/Content_generator/static/translator.html`, `translationPage.js`.

Must keep controls:

- Source switch:
  - document
  - video
- Document mode:
  - `translationFile`
  - manual textarea `translationInput`
  - `translationMode`
  - `translationLanguage`
  - clear
  - translate
  - original/translated compare panes
  - download, copy, compare
- Video mode:
  - `translationVideoFile`
  - video preview card
  - upload progress
  - video processing progress
  - `translationWantVideo`
  - `translationWantSubtitles`
  - `translationWantTranscript`
  - `translationOutputMode`
  - `translationLanguageMirror`
  - translate video
  - result panel
  - inline download links
- Status/progress:
  - `translationStatus`
  - phase label
  - progress bar

Backend links:

- Legacy/current close match:
  - `POST /translate/readme`
  - `POST /translate/document`
  - `POST /translate/video`
  - `GET /translate/status/{request_id}`
  - `GET /translate/subtitles/{request_id}`
  - `GET /translate/download/{request_id}`

Current gap:

- Current translator panel is functional but simplified; video source switch, upload progress, output toggles,
  split compare layout and inline artifact actions must be restored.

### `/app/instruction`

Source: `legacy/Content_generator/static/instruction.html`.

Must keep:

- Page route and nav item.
- Same shell/header/model/user controls.
- Instruction content and internal anchors.

Current gap:

- No first-class instruction page in current module registry/dashboard.

## Spravochnik page matrix

### `/intake`

Source: `legacy/Spravochnik/viewer/templates/intake.html`.

Must keep:

- Brief upload/paste workspace.
- Recent intake jobs.
- Stage/workflow cards.
- Status polling:
  - `GET /intake/jobs/{id}/status`
  - `POST /intake/jobs/{id}/next-step`
- Candidate skill decisions:
  - accept
  - reject
  - merge/review variants
  - note/comment
  - expand/collapse candidate cards
- Catalog apply and DAG actions:
  - apply catalog
  - build DAG
  - next-step
- DAG workspace:
  - columns/groups
  - edge layers
  - tooltip
  - expand all
  - collapse all
  - export SVG/PNG/PDF
- Curriculum result actions:
  - open UP
  - open template proposals
  - download CSV
- Clear workspace.

Backend links:

- Legacy:
  - `POST /intake`
  - `GET /intake/jobs/{id}`
  - `GET /intake/jobs/{id}/status`
  - `POST /intake/jobs/{id}/next-step`
  - `POST /intake/jobs/{id}/build-dag`
  - `POST /intake/jobs/{id}/apply-catalog`
  - `POST /intake/jobs/{id}/candidate-decision`
  - `GET /intake/jobs/{id}/plan.csv`
  - `POST /intake/jobs/clear`
- Current gap:
  - Intake UI is not present as a Spravochnik workspace.

### `/up`

Source: `up_index.html`, `up_detail.html`, `up_row_edit.html`, `up_template_proposals.html`.

Must keep:

- Plan list:
  - cleanup empty drafts
  - open UP
  - open related brief
  - CSV
  - delete
- Plan detail:
  - open brief
  - download CSV
  - add row
  - rebuild template proposals
  - open template proposals
  - delete plan
  - row table
  - edit row
  - delete row
- Row edit:
  - block index
  - row number
  - project index in block
  - block title
  - audience level
  - block goal
  - project name
  - effort hours
  - project summary
  - outcomes know/can/skills
  - skills list
  - required tools
  - materials
  - storytelling
  - validation criteria
  - delivery format
  - group size
  - save/cancel
- Template proposals:
  - regenerate
  - open working templates
  - workflow steps
  - edit title/family/confidence/scope/description/patterns/materials/storytelling/criteria/rationale
  - save
  - accept and rebuild UP
  - reject

Current gap:

- Current curriculum panel covers import/edit/export, but not the original Spravochnik `/up` page hierarchy,
  row edit screen, template proposals and related brief links.

### `/competencies` and `/competencies/{id}`

Source: `competencies.html`, `competency_detail.html`.

Must keep:

- Search/filter list.
- Competency detail with linked skills/indicators.
- Back link to directory.
- Same Spravochnik summary panel.

Current gap:

- Current reference panel has competency list/detail but not original layout/shell.

### `/profiles` and `/profiles/{id}`

Source: `profiles.html`, `profile_detail.html`.

Must keep:

- Toggle show/hide service profiles.
- Profile cards.
- Profile tree/detail.
- Back link to skillsets.

Current gap:

- Current reference panel has profile tabs but not the legacy page model.

### `/reviews`

Source: `reviews.html`.

Must keep:

- Filters:
  - severity
  - reason
  - entity type
- Apply catalog to skillset action.
- Build DAG action.
- Per-review form:
  - resolution note
  - confirm
  - ignore
  - return to queue

Current gap:

- Current reference review tab is simplified and does not expose all pipeline actions.

### `/catalog-admin/groups` and `/catalog-admin/groups/{id}`

Source: `catalog_admin_groups.html`, `catalog_admin_group_detail.html`.

Must keep:

- Create group.
- Edit group name/sort/status.
- Open group.
- Remove/archive group.
- In group detail:
  - add skill
  - edit group
  - remove/archive group
  - list skills

Current gap:

- No catalog-admin groups screen in current UI.

### `/catalog-admin/skills/{id}`

Source: `catalog_admin_skill_detail.html`.

Must keep:

- Edit skill canonical fields.
- Resolution/status controls.
- Alias list add/remove.
- Indicator list create/edit/delete.
- Merge/archive/restore actions if exposed by source.

Current gap:

- Current reference panel edits only a subset of skill fields.

### `/catalog-admin/skillsets` and `/catalog-admin/skillsets/{id}`

Source: `catalog_admin_skillsets.html`, `catalog_admin_skillset_detail.html`.

Must keep:

- Skillset list.
- Skillset detail tree/items.
- Navigation back to catalog.

Current gap:

- Not present in current UI.

### `/catalog-admin/candidate-competencies`

Source: `catalog_admin_candidate_competencies.html`.

Must keep:

- Similarity candidates.
- Move skill to existing competency.
- Rename candidate.
- Merge into existing competency.
- Accept new.
- Return to review.
- Reject.
- Resolution note.

Current gap:

- Not present in current UI.

### `/catalog-admin/artifact-templates`

Source: `catalog_admin_artifact_templates.html`.

Must keep:

- Create/edit template.
- Fields:
  - code
  - title
  - artifact family
  - status
  - priority
  - scope weight
  - artifact description
  - project name pattern
  - materials pattern
  - storytelling pattern
  - validation criteria
  - scope type
  - scope names
- Actions:
  - save
  - edit
  - activate
  - deprecate

Current gap:

- Not present in current UI.

### `/catalog-admin/archive`

Source: `catalog_admin_archive.html`.

Must keep:

- Search query.
- Scope filter.
- Restore group.
- Restore skill.
- Restore indicator.
- Open restored skill/card links.

Current gap:

- Not present in current UI.

## Required implementation order

1. Restore shell split:
   - CG pages use S21 shell and route labels.
   - Spravochnik pages use methodologist shell and summary panel.
2. Dashboard parity:
   - CG dashboard `/app` equivalent.
   - Product root can remain portal, but must not replace module-native shells.
3. Generator parity completion:
   - Add missing async/status/download/review/regeneration adapters or mark backend tasks.
4. Checker parity:
   - Restore checker full surface and improvement workflow.
5. Translator parity:
   - Restore document/video source switch, progress, output toggles, downloads.
6. Spravochnik parity:
   - Implement `intake`, `up`, `catalog-admin`, `competencies`, `profiles`, `reviews` as methodologist workspace screens.
7. Final parity e2e:
   - Every visible button performs a real endpoint call or deterministic frontend state transition.
   - Every original route has a current route mapping.
   - Every current panel has a static parity test and one real endpoint e2e test.

## Test contract

For each page:

- Static test asserts required IDs/buttons/tabs exist.
- JS test or browser smoke asserts transitions:
  - tab switch
  - expander open/close
  - mode switch
  - file select state
  - disabled/loading/success/error state
- API test asserts each submit/action hits a real endpoint.
- GitNexus route/flow check runs before commit for changed UI/backend routes.

## Current conclusion

The current app is functionally advanced, but UI parity is incomplete because the migration compressed multiple
legacy screens into single modern panels. That loses original navigation and methodologist workflows even when the
backend capability exists. The fix is not more styling; it is route/page parity with compact shared primitives.
