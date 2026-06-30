const $ = (id) => document.getElementById(id);

const el = {
  form: $("generatorForm"),
  plan: $("planSelect"),
  direction: $("direction"),
  block: $("blockSelect"),
  project: $("projectSelect"),
  profile: $("profileSelect"),
  programType: $("programType"),
  csv: $("curriculumFile"),
  status: $("generatorStatus"),
  summary: $("projectSummary"),
  progress: $("generatorProgress"),
  timeline: $("generatorTimeline"),
  metrics: $("generatorMetrics"),
  output: $("generatorOutput"),
  metadata: $("generatorMetadataView"),
  issues: $("generatorIssuesView"),
  artifacts: $("generatorArtifactsView"),
  practice: $("practicePlanDetails"),
  critic: $("practiceCriticIssues"),
  noResults: $("noResults"),
  results: $("resultsArea"),
  runView: $("generationRunView"),
  logs: $("generationLogs"),
  generateBtn: $("generateBtn"),
  cancelBtn: $("cancelGenerationBtn"),
  assistant: $("methodologyAssistantChat"),
  reviewWorkspace: $("methodologyReviewWorkspace"),
  reviewActions: $("methodologyReviewActions"),
  recentRuns: $("recentGeneratorRunItems"),
  archiveBtn: $("downloadArchiveBtn"),
};

const state = {
  plans: [],
  cascade: null,
  currentProject: null,
  currentResult: null,
  currentReview: null,
  currentRunId: null,
  currentPayload: null,
  controller: null,
  pollTimer: null,
  startedAt: 0,
  readmeMode: "preview",
};

const RUN_STEPS = [
  ["context", "Анализ контекста", "учебный план, результаты обучения, соседние проекты"],
  ["planning", "Планирование практики", "количество задач, сложность, артефакты"],
  ["skeleton", "Каркас README", "структура, содержание, навигация"],
  ["theory", "Генерация теории", "разделы, примеры, визуальные блоки"],
  ["practice", "Генерация практики", "задачи, p2p-критерии, материалы"],
  ["quality", "Проверка качества", "структура, связность, полнота"],
  ["evaluation", "Оценка по критериям", "rubric, замечания, score"],
  ["assembly", "Сборка результата", "README, отчёты, архив"],
];

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

async function loadPlans(selectPlanId = null) {
  setStatus("Загрузка учебных планов...");
  state.plans = await request("/curriculum/plans");
  el.plan.innerHTML = state.plans
    .map((plan) => `<option value="${plan.plan_id}">${escapeHtml(plan.direction || "Без направления")} · ${escapeHtml(plan.title)}</option>`)
    .join("");
  if (selectPlanId) el.plan.value = String(selectPlanId);
  if (!state.plans.length) {
    el.generateBtn.disabled = true;
    el.summary.textContent = "Нет сохраненных учебных планов. Создайте или импортируйте УП в модуле Учебные планы.";
    setStatus("Нет учебных планов", "error");
    renderTimeline();
    return;
  }
  el.generateBtn.disabled = false;
  await loadPlan(Number(el.plan.value));
}

async function loadPlan(planId) {
  if (!planId) return;
  setProgress(10);
  renderTimeline("context");
  state.cascade = await request(`/curriculum/plans/${planId}/cascade`);
  el.direction.value = directionCode(state.cascade.direction);
  renderBlocks();
  await loadSelectedProject();
  setStatus(`${state.cascade.direction || "Направление"} · ${state.cascade.blocks.length} блоков`);
}

function renderBlocks() {
  el.block.innerHTML = (state.cascade?.blocks || [])
    .map((block) => `<option value="${escapeHtml(block.name)}">${escapeHtml(block.name)}</option>`)
    .join("");
  renderProjects();
}

function renderProjects() {
  const block = selectedBlock();
  el.project.innerHTML = (block?.projects || [])
    .map((project) => `<option value="${project.project_id}">${project.order}. ${escapeHtml(project.title)}</option>`)
    .join("");
}

async function loadSelectedProject() {
  const projectId = Number(el.project.value);
  if (!projectId) {
    state.currentProject = null;
    el.summary.textContent = "В выбранном блоке нет проектов.";
    return;
  }
  state.currentProject = await request(`/curriculum/projects/${projectId}`);
  hydrateFormFromProject();
  renderProjectSummary();
}

function selectedBlock() {
  return (state.cascade?.blocks || []).find((block) => block.name === el.block.value);
}

function hydrateFormFromProject() {
  const project = state.currentProject?.project;
  if (!project) return;
  setValue("titleSeed", project.title);
  setValue("projectDescription", project.description);
  setValue("requiredTools", asLine(project.required_tools));
  setValue("requiredSoftware", asLine(project.required_software));
  setValue("storytelling", project.storytelling);
  setValue("learningOutcomes", asLine([...(project.outcomes_know || []), ...(project.outcomes_can || []), ...(project.outcomes_skills || [])]));
  setValue("skills", asLine((project.competency_refs || []).map((item) => item.canonical_name || item.competency_id)));
  setValue("projectType", project.format || "individual");
  setValue("groupSize", project.group_size || 1);
  setValue("workloadHours", project.hours_astro || "");
  setValue("platformName", project.metadata?.platform_name || "");
  setValue("repoBaseUrl", project.metadata?.gitlab_link || "");
  setValue("additionalMaterials", project.materials || "");
  setValue("storytellingType", project.metadata?.storytelling_type || "sjm");
  setValue("audienceLevel", project.metadata?.audience_level || "beginner_plus");
  toggleGroupSize();
}

function renderProjectSummary() {
  const project = state.currentProject?.project;
  if (!project) return;
  el.summary.innerHTML = `
    <strong>${escapeHtml(project.order)}. ${escapeHtml(project.title)}</strong>
    <span>${escapeHtml(project.block || "Без блока")} · ${escapeHtml(project.format || "individual")} · ${escapeHtml(project.hours_astro || 0)} ч.</span>
    <span>${escapeHtml(project.description || "Описание не заполнено")}</span>
  `;
}

async function handleCsvImport() {
  const file = el.csv.files?.[0];
  if (!file) return;
  setStatus("Импорт CSV в учебные планы...");
  $("curriculumFileName").textContent = file.name;
  const csvText = await file.text();
  const created = await request("/curriculum/plans/import-csv", {
    method: "POST",
    body: JSON.stringify({ csv_text: csvText, title: file.name.replace(/\.[^.]+$/, ""), source_policy: "ui_import" }),
  });
  await loadPlans(created.plan_id);
  setStatus(`CSV импортирован: ${created.project_count} проектов`, "success");
}

async function runGeneration(event) {
  event.preventDefault();
  if (!state.currentProject) {
    setStatus("Выберите проект из учебного плана.", "error");
    return;
  }
  clearResult();
  startRunChrome();
  const payload = {
    plan_id: Number(el.plan.value),
    project_order: Number(state.currentProject.project.order),
    profile_id: el.profile.value || "_base",
    overrides: collectOverrides(),
  };
  if (el.programType.value.trim()) payload.program_type = el.programType.value.trim();
  state.controller = new AbortController();
  try {
    state.currentPayload = payload;
    setProgress(12);
    renderTimeline("context");
    const started = await request("/generator/runs/from-curriculum/async", {
      method: "POST",
      body: JSON.stringify(payload),
      signal: state.controller.signal,
    });
    state.currentRunId = started.run_id || started.request_id;
    setStatus(`Запуск ${state.currentRunId.slice(0, 8)} создан. Отслеживаю статус...`);
    await pollGenerationStatus(state.currentRunId);
  } catch (error) {
    if (error.name === "AbortError") {
      setStatus("Генерация остановлена локально.", "warning");
    } else {
      showError(error);
    }
    stopRunChrome();
  }
}

function collectOverrides() {
  return {
    title: value("titleSeed"),
    description: value("projectDescription"),
    learning_outcomes: lines("learningOutcomes"),
    skills: lines("skills"),
    audience_level: value("audienceLevel"),
    required_tools: splitList(value("requiredTools")),
    required_software: splitList(value("requiredSoftware")),
    project_format: value("projectType"),
    group_size: Number(value("groupSize") || 1),
    workload_hours: Number(value("workloadHours") || 0),
    platform_name: value("platformName"),
    gitlab_link: value("repoBaseUrl"),
    repo_path_template: value("repoPathTemplate"),
    storytelling_type: value("storytellingType"),
    storytelling: value("storytelling"),
    additional_materials: value("additionalMaterials"),
    include_diagrams: $("includeDiagrams").checked,
    include_tables: $("includeTables").checked,
    include_formulas: $("includeFormulas").checked,
    generate_bonus: $("generateBonus").checked,
    bonus_wish: value("bonusWish"),
    project_content_type: value("projectContentType"),
    methodology_human_review: $("methodologyHumanReview").checked,
    regeneration_comment: value("regenerationComments") || value("regenerationGlobalComment"),
  };
}

async function renderResult(result) {
  const markdown = result.document?.markdown || "";
  state.currentResult = result;
  state.currentRunId = result.run_id || result.request_id || state.currentRunId;
  el.noResults.hidden = true;
  el.results.hidden = false;
  document.body.classList.add("generation-completed");
  el.archiveBtn.disabled = !state.currentRunId;
  updateSummary(result, markdown);
  renderPractice(result);
  renderMetadata(result);
  renderIssues(result);
  renderArtifacts(result);
  renderRegenerationSelector(markdown);
  renderReviewWorkspace({ result, methodology: state.currentReview });
  await renderReadme(markdown);
  activateTab("generatorReadme");
}

function updateSummary(result, markdown) {
  const metadata = result.document?.metadata || {};
  const rubric = result.rubric_json || {};
  const score = rubric.passed ? 100 : Math.max(0, 100 - Number(rubric.hard_count || 0) * 25 - Number(rubric.soft_count || 0) * 8);
  setText("generationScorePercent", `${score}%`);
  setText("generationScoreValue", rubric.passed ? "Пройдено" : "Нужна правка");
  setText("generationScoreMeta", result.gate_review?.status || "Gate");
  setText("generationWordsValue", wordCount(markdown).toLocaleString("ru-RU"));
  setText("generationTasksValue", count(metadata.practice_tasks) + count(metadata.bonus_tasks));
  setText("generationTasksMeta", count(metadata.bonus_tasks) ? "Основные + бонус" : "Основные задачи");
  setText("generationAssetsValue", count(result.document?.artifacts) + count(metadata.dataset_files) + count(metadata.code_examples));
  $("generationScoreRing").style.setProperty("--score", `${score}%`);
}

async function renderReadme(markdown) {
  renderToc("readmeToc", markdown);
  if (state.readmeMode === "markdown") {
    el.output.innerHTML = `<pre>${escapeHtml(markdown || "README не вернулся из генератора.")}</pre>`;
    return;
  }
  await renderMarkdownPreview(el.output, markdown, "README не вернулся из генератора.");
}

function renderPractice(result) {
  const metadata = result.document?.metadata || {};
  const tasks = asList(metadata.practice_tasks);
  const bonus = asList(metadata.bonus_tasks);
  el.practice.innerHTML = tasks.length || bonus.length
    ? [...tasks, ...bonus].map((task, index) => `<article class="list-item"><strong>${index + 1}. ${escapeHtml(task.title || task.goal || "Задача")}</strong><span>${escapeHtml(task.goal || task.situation || "")}</span></article>`).join("")
    : '<div class="empty-inline">Практические задачи не вернулись.</div>';
  const critic = asList(metadata.practice_critic_issues);
  el.critic.innerHTML = critic.length
    ? critic.map((issue) => `<article class="issue-card"><strong>${escapeHtml(issue.kind || "issue")}</strong><span>${escapeHtml(issue.message || "")}</span></article>`).join("")
    : '<div class="empty-inline">CriticAgent не нашел дефектов.</div>';
}

function renderMetadata(result) {
  const context = result.context || {};
  const metadata = result.document?.metadata || {};
  el.metadata.innerHTML = `
    <div class="metrics-grid">
      ${metricCard("План", context.plan_title || context.plan_id || "n/a")}
      ${metricCard("Направление", context.direction || "n/a")}
      ${metricCard("Блок", context.block_name || "n/a")}
      ${metricCard("Проект", context.current_project_title || "n/a")}
      ${metricCard("Предыдущие", count(context.previous_projects))}
      ${metricCard("Следующие", count(context.next_block_projects || context.next_projects))}
    </div>
    <details open><summary>Document metadata</summary><pre>${escapeHtml(JSON.stringify(metadata, null, 2))}</pre></details>
    <details><summary>Curriculum context</summary><pre>${escapeHtml(JSON.stringify(context, null, 2))}</pre></details>
  `;
}

function renderIssues(result) {
  const rubric = result.rubric_json || {};
  const issues = [
    ...asList(result.rule_issues).map((issue) => ({ ...issue, source: issue.skill_id || "rule" })),
    ...asList(result.gate_review?.issues).map((issue) => ({ ...issue, source: result.gate_review?.stage || "gate" })),
  ];
  el.metrics.innerHTML = [
    metricCard("Rubric", rubric.passed ? "passed" : "needs review"),
    metricCard("Hard", rubric.hard_count ?? 0),
    metricCard("Soft", rubric.soft_count ?? 0),
    metricCard("Gate", result.gate_review?.status || "n/a"),
  ].join("");
  el.issues.innerHTML = issues.length ? issues.map(renderIssue).join("") : '<div class="empty-inline">Дефекты не найдены.</div>';
}

function renderArtifacts(result) {
  const metadata = result.document?.metadata || {};
  const artifacts = [
    ...asList(result.document?.artifacts).map((item) => artifactItem(item.kind || item.family || "artifact", item.path || item.uri || item.target || item.artifact_id)),
    ...asList(metadata.dataset_files).map((item) => artifactItem("dataset", item.path || item.filename || item.title || item.id)),
    ...asList(metadata.code_examples).map((item) => artifactItem("code", item.path || item.filename || item.title || item.language)),
    ...asList(metadata.formula_assets?.formulas).map((item) => artifactItem("formula", item.label || item.id)),
    ...asList(metadata.formula_assets?.tables).map((item) => artifactItem("table", item.label || item.id)),
  ].filter((item) => item.value);
  el.artifacts.innerHTML = artifacts.length
    ? `<div class="reference-list compact">${artifacts.map((item) => `<div class="list-item"><strong>${escapeHtml(item.kind)}</strong><span class="path-token">${escapeHtml(item.value)}</span></div>`).join("")}</div>`
    : '<div class="empty-inline">Артефакты не вернулись.</div>';
}

function renderRegenerationSelector(markdown) {
  const headings = regenerationHeadings(markdown).slice(0, 24);
  $("regenerationSectionSelector").innerHTML = headings.length
    ? headings.map((heading, index) => {
        return `<label class="regeneration-section-option level-${heading.level}"><span class="regeneration-section-row"><input type="checkbox" value="${index}" data-title="${escapeAttr(heading.title)}" data-start-line="${heading.startLine}" data-end-line="${heading.endLine}" /><strong>${escapeHtml(heading.title)}</strong></span><small>Строки ${heading.startLine}-${heading.endLine}</small></label>`;
      }).join("")
    : '<div class="regeneration-empty-note">В README не найдены заголовки для точечной перегенерации.</div>';
  renderToc("regenToc", markdown);
}

function regenerationHeadings(markdown) {
  const lines = String(markdown || "").split("\n");
  const headings = [];
  lines.forEach((line, index) => {
    const match = line.match(/^(#{1,3})\s+(.+?)\s*$/);
    if (match) {
      headings.push({ title: match[2], level: match[1].length, startLine: index + 1, endLine: lines.length });
    }
  });
  headings.forEach((heading, index) => {
    const next = headings.find((candidate, candidateIndex) => candidateIndex > index && candidate.level <= heading.level);
    heading.endLine = next ? next.startLine - 1 : lines.length;
  });
  return headings;
}

function startRunChrome() {
  state.startedAt = Date.now();
  document.body.classList.add("generation-running");
  el.runView.hidden = false;
  el.logs.hidden = false;
  el.cancelBtn.hidden = false;
  el.generateBtn.disabled = true;
  $("generationRunSnapshot").hidden = false;
  $("generationRunStartedAt").textContent = new Date().toLocaleString("ru-RU");
  updateRunSnapshot();
  renderTimeline("context");
  updateTimer();
  toggleAssistant();
}

function stopRunChrome() {
  document.body.classList.remove("generation-running");
  if (state.pollTimer) {
    clearTimeout(state.pollTimer);
    state.pollTimer = null;
  }
  el.cancelBtn.hidden = true;
  el.generateBtn.disabled = false;
  updateTimer();
}

function updateRunSnapshot() {
  const project = state.currentProject?.project || {};
  setText("runParamCurriculum", selectedText(el.plan));
  setText("runParamDirection", selectedText(el.direction));
  setText("runParamBlock", selectedText(el.block));
  setText("runParamProject", selectedText(el.project));
  setText("runParamTitle", value("titleSeed") || project.title || "—");
  setText("runParamType", selectedText($("projectType")));
  setText("runParamTasks", "auto");
  setText("runParamMethodology", $("methodologyHumanReview").checked ? "Методологический режим" : "Обычный режим");
}

function renderTimeline(activeId = null, done = false) {
  const activeIndex = RUN_STEPS.findIndex(([id]) => id === activeId);
  const rows = RUN_STEPS.map(([id, label, hint], index) => {
    const isDone = done || (activeIndex > index);
    const isNow = activeId === id && !done;
    return `<li class="generation-pipeline-step ${isDone ? "done" : ""} ${isNow ? "now" : "pending"}" data-run-stage="${id}"><span>${String(index + 1).padStart(2, "0")}</span><div><strong>${label}</strong><small>${hint}</small></div><em>${isDone ? "готово" : isNow ? "в работе" : "ожидает"}</em></li>`;
  }).join("");
  el.timeline.innerHTML = rows;
  $("generationTimeline").innerHTML = rows.replaceAll("generation-pipeline-step", "s21-tl-row");
  const step = RUN_STEPS[Math.max(0, activeIndex)] || RUN_STEPS[0];
  setText("generationRunStageIndex", activeIndex >= 0 ? activeIndex + 1 : RUN_STEPS.length);
  setText("generationRunStageTotal", RUN_STEPS.length);
  setText("generationRunTitle", done ? "Сборка результата завершена" : step[1]);
  setText("generationRunSubtitle", done ? "README, метрики и артефакты готовы к проверке." : step[2]);
  setText("currentAgent", done ? "Готово" : step[1]);
}

function setProgress(value) {
  const clamped = Math.max(0, Math.min(100, value));
  el.progress.style.setProperty("--progress", `${clamped}%`);
  $("generationRunRing").style.setProperty("--run-progress", `${clamped}%`);
  setText("generationRunPercent", `${clamped}%`);
}

function updateTimer() {
  if (!state.startedAt) return;
  const seconds = Math.floor((Date.now() - state.startedAt) / 1000);
  const label = `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
  setText("generationTimer", label);
  setText("generationRunTimer", label);
}

function toggleAssistant() {
  el.assistant.hidden = !$("methodologyHumanReview").checked;
}

function addAssistantMessage(role, text) {
  $("assistantChatMessages").insertAdjacentHTML("beforeend", `<div class="assistant-message ${role}"><span>${role === "assistant" ? "М" : "Вы"}</span><div>${escapeHtml(text)}</div></div>`);
  $("assistantChatMessages").scrollTop = $("assistantChatMessages").scrollHeight;
}

function activateTab(targetId) {
  document.querySelectorAll("[data-tab-target]").forEach((button) => {
    const active = button.dataset.tabTarget === targetId;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
  });
  document.querySelectorAll(".tab-content").forEach((panel) => {
    const active = panel.id === targetId;
    panel.classList.toggle("active", active);
    panel.hidden = !active;
  });
}

function clearResult() {
  el.output.innerHTML = "";
  el.metadata.innerHTML = "";
  el.issues.innerHTML = "";
  el.artifacts.innerHTML = "";
  el.metrics.innerHTML = "";
  el.practice.innerHTML = "";
  el.critic.innerHTML = "";
  el.noResults.hidden = false;
  el.results.hidden = true;
  document.body.classList.remove("generation-completed");
}

function setStatus(message, kind = "") {
  el.status.textContent = message;
  el.status.className = `status-line ${kind}`.trim();
  $("generatorSubbarStatus").textContent = kind === "success" ? "ГОТОВО" : kind === "error" ? "ОШИБКА" : kind === "warning" ? "ТРЕБУЕТ ВНИМАНИЯ" : "ЧЕРНОВИК";
}

function showError(error) {
  setStatus(error.message || String(error), "error");
}

async function renderMarkdownPreview(target, markdown, emptyMessage) {
  if (window.ContentFactoryMarkdown) {
    await window.ContentFactoryMarkdown.renderMarkdown(target, markdown, { emptyMessage });
    return;
  }
  target.textContent = markdown || emptyMessage || "";
}

function renderToc(containerId, markdown) {
  const items = String(markdown || "").split("\n").filter((line) => /^#{1,3}\s+/.test(line)).slice(0, 32);
  $(containerId).innerHTML = items.length
    ? `<div class="readme-toc-title">Содержание</div>${items.map((line) => {
        const level = line.match(/^#+/)[0].length;
        return `<button type="button" class="readme-toc-link level-${level}">${escapeHtml(line.replace(/^#+\s+/, ""))}</button>`;
      }).join("")}`
    : '<div class="readme-toc-empty">Заголовки появятся после генерации.</div>';
}

async function pollGenerationStatus(runId) {
  if (!runId) return;
  if (state.pollTimer) {
    clearTimeout(state.pollTimer);
    state.pollTimer = null;
  }
  try {
    const data = await request(`/generator/runs/${runId}/status`);
    state.currentRunId = data.run_id || data.request_id || runId;
    state.currentReview = data.methodology || null;
    renderPollingState(data);
    if (data.status === "completed" || data.status === "needs_review") {
      if (data.result) await renderResult(data.result);
      stopRunChrome();
      renderTimeline(null, true);
      setProgress(100);
      renderReviewWorkspace(data);
      setStatus(data.status === "needs_review" ? "Готово. Нужна проверка методолога." : "Готово", data.status === "needs_review" ? "warning" : "success");
      await loadRecentRuns();
      return;
    }
    if (data.status === "failed" || data.status === "cancelled") {
      stopRunChrome();
      setStatus(data.error || (data.status === "cancelled" ? "Генерация остановлена." : "Генерация завершилась ошибкой."), data.status === "cancelled" ? "warning" : "error");
      await loadRecentRuns();
      return;
    }
    state.pollTimer = setTimeout(() => pollGenerationStatus(runId), 1500);
  } catch (error) {
    setStatus(`Ошибка polling: ${error.message}`, "error");
    state.pollTimer = setTimeout(() => pollGenerationStatus(runId), 2500);
  }
}

function renderPollingState(data) {
  const workflow = data.workflow || {};
  const active = stageFromWorkflow(workflow);
  setProgress(data.progress || 8);
  renderTimeline(active);
  const stageLabel = RUN_STEPS.find(([id]) => id === active)?.[1] || workflow.current_node || "Генерация проекта";
  setText("currentAgent", stageLabel);
  setText("generationRunLogContent", `${statusLabel(data.status)} · ${stageLabel}`);
  if (data.methodology) {
    renderMethodologyLive(data.methodology);
  }
}

function renderMethodologyLive(methodology) {
  const actions = asList(methodology.review_actions);
  el.reviewActions.hidden = false;
  el.reviewActions.innerHTML = actions.length
    ? actions.slice(-4).map((item) => `<div class="review-item"><strong>${escapeHtml(item.action)}</strong><span>${escapeHtml(item.details?.instruction || item.details?.comment || item.created_at || "")}</span></div>`).join("")
    : '<div class="empty-inline">Методологические действия появятся здесь.</div>';
  $("methodologyLiveStatus").hidden = false;
  $("methodologyLiveStatus").innerHTML = `
    <div class="methodology-context-row"><strong>Review state</strong><span>${escapeHtml(methodology.review_state || "running")}</span></div>
    <div class="methodology-context-row"><strong>Targets</strong><span>${count(methodology.target_registry?.targets)}</span></div>
    <div class="methodology-context-row"><strong>Pending</strong><span>${count(methodology.pending_change_ids)}</span></div>
  `;
}

function stageFromWorkflow(workflow) {
  const node = String(workflow?.current_node || workflow?.last_completed_node || "").toLowerCase();
  if (node.includes("theory")) return "theory";
  if (node.includes("practice")) return "practice";
  if (node.includes("quality") || node.includes("evaluation")) return "quality";
  if (node.includes("final")) return "assembly";
  if (node.includes("skeleton") || node.includes("head")) return "skeleton";
  if (node.includes("planner") || node.includes("planning")) return "planning";
  return "context";
}

function statusLabel(status) {
  return {
    created: "создан",
    running: "в работе",
    completed: "готово",
    needs_review: "ожидает методолога",
    failed: "ошибка",
    cancelled: "остановлен",
  }[status] || status || "в работе";
}

async function cancelCurrentRun() {
  if (!state.currentRunId) {
    state.controller?.abort();
    stopRunChrome();
    setStatus("Генерация остановлена локально.", "warning");
    return;
  }
  const data = await request(`/generator/runs/${state.currentRunId}/cancel`, {
    method: "POST",
    body: JSON.stringify({ comment: "Остановлено из UI генератора" }),
  });
  state.currentReview = data.methodology || state.currentReview;
  stopRunChrome();
  setStatus("Генерация остановлена пользователем.", "warning");
  await loadRecentRuns();
}

async function loadRecentRuns() {
  if (!el.recentRuns) return;
  const payload = await request("/generator/runs/recent");
  const items = asList(payload.items);
  el.recentRuns.innerHTML = items.length
    ? items.map((item) => `
        <button type="button" class="recent-run-row" data-run-id="${escapeHtml(item.run_id)}">
          <span>${escapeHtml(item.status)}</span>
          <strong>${escapeHtml(item.title || "README project")}</strong>
          <small>${escapeHtml(item.updated_at || "")}</small>
        </button>
      `).join("")
    : '<div class="empty-inline">Запусков пока нет.</div>';
  el.recentRuns.querySelectorAll("[data-run-id]").forEach((button) => {
    button.addEventListener("click", () => pollGenerationStatus(button.dataset.runId));
  });
}

function renderReviewWorkspace(data) {
  const review = data?.methodology || state.currentReview;
  const runId = data?.run_id || data?.request_id || data?.result?.run_id || state.currentRunId;
  if (!runId || !el.reviewWorkspace) return;
  const targets = asList(review?.target_registry?.targets).slice(0, 40);
  $("assistantChatActions").hidden = false;
  $("assistantTargetPicker").hidden = !targets.length;
  $("assistantChangeTarget").innerHTML = ['<option value="">Текущий блок</option>', ...targets.map((target) => `<option value="${escapeHtml(target.id)}">${escapeHtml(target.label || target.id)}</option>`)].join("");
  $("assistantTargetChips").innerHTML = targets.slice(0, 12).map((target) => `<button type="button" data-target-id="${escapeHtml(target.id)}">${escapeHtml(target.label || target.id)}</button>`).join("");
  $("assistantTargetChips").querySelectorAll("[data-target-id]").forEach((button) => button.addEventListener("click", () => setValue("assistantChangeTarget", button.dataset.targetId)));
  el.reviewWorkspace.hidden = false;
  el.reviewWorkspace.innerHTML = `
    <div class="methodology-review-card">
      <div><strong>Контур методолога</strong><span>${escapeHtml(review?.review_state || "готов")}</span></div>
      <div><strong>Правок</strong><span>${count(review?.review_actions)}</span></div>
      <div><strong>Targets</strong><span>${targets.length}</span></div>
    </div>
    <div class="btn-group">
      <button class="btn btn-secondary btn-sm" type="button" data-review-action="preview">Предпросмотр правок</button>
      <button class="btn btn-secondary btn-sm" type="button" data-review-action="approve">Принять diff</button>
      <button class="btn btn-secondary btn-sm" type="button" data-review-action="continue">Продолжить</button>
    </div>
  `;
  el.reviewWorkspace.querySelector("[data-review-action='preview']").addEventListener("click", previewReviewChanges);
  el.reviewWorkspace.querySelector("[data-review-action='approve']").addEventListener("click", approveReviewDiff);
  el.reviewWorkspace.querySelector("[data-review-action='continue']").addEventListener("click", () => sendReviewAction("continue"));
}

async function requestReviewChangesFromChat() {
  const instruction = value("assistantChatInput") || value("regenerationGlobalComment") || value("regenerationComments");
  if (!instruction) {
    addAssistantMessage("assistant", "Опишите правку в чате или поле перегенерации.");
    return;
  }
  const data = await request(`/generator/runs/${state.currentRunId}/review/request-changes`, {
    method: "POST",
    body: JSON.stringify({
      target_stage: "final",
      target_selector: value("assistantChangeTarget"),
      scope: "local_section_only",
      instruction,
      forbidden_changes: ["не менять соседние разделы"],
      expected_outcome: "README исправлен точечно без нарушения структуры.",
    }),
  });
  state.currentReview = data.methodology || null;
  renderReviewWorkspace(data);
  addAssistantMessage("assistant", "Запрос правки сохранён. Можно сделать предпросмотр.");
}

async function previewReviewChanges() {
  if (!state.currentRunId) return;
  const data = await request(`/generator/runs/${state.currentRunId}/review/preview-changes`, { method: "POST", body: JSON.stringify({}) });
  state.currentReview = data.methodology || null;
  renderReviewWorkspace(data);
  compareCurrentResult();
  addAssistantMessage("assistant", "Предпросмотр готов. Проверьте diff и примите изменения.");
}

async function approveReviewDiff() {
  if (!state.currentRunId) return;
  const data = await request(`/generator/runs/${state.currentRunId}/review/approve-diff`, { method: "POST", body: JSON.stringify({ comment: value("assistantChatInput") }) });
  state.currentReview = data.methodology || null;
  if (data.result) await renderResult(data.result);
  renderReviewWorkspace(data);
  addAssistantMessage("assistant", "Diff принят и применён к текущему README.");
}

async function sendReviewAction(action) {
  if (!state.currentRunId) return;
  const data = await request(`/generator/runs/${state.currentRunId}/review/actions`, {
    method: "POST",
    body: JSON.stringify({ action, comment: value("assistantChatInput") }),
  });
  state.currentReview = data.methodology || null;
  renderReviewWorkspace(data);
  addAssistantMessage("assistant", `Действие ${action} сохранено.`);
}

function downloadCurrentArchive() {
  if (!state.currentRunId) return;
  window.location.href = `/generator/runs/${state.currentRunId}/archive`;
}

function renderIssue(issue) {
  const hard = issue.severity === "hard" || issue.severity === "critical";
  return `<article class="issue-card ${hard ? "hard" : ""}"><strong>${escapeHtml(issue.code || issue.kind || "issue")}</strong><span>${escapeHtml(issue.message || "")}</span><span class="badge ${hard ? "error" : "warning"}">${escapeHtml(issue.source || "rule")} · ${escapeHtml(issue.severity || "info")}</span></article>`;
}

function metricCard(label, value) {
  return `<div class="metric-card"><strong>${escapeHtml(value)}</strong><span>${escapeHtml(label)}</span></div>`;
}

function artifactItem(kind, value) {
  return { kind: String(kind || "artifact"), value: String(value || "") };
}

function bindEvents() {
  el.form.addEventListener("submit", runGeneration);
  el.generateBtn.addEventListener("click", (event) => {
    event.preventDefault();
    runGeneration(event);
  });
  el.plan.addEventListener("change", () => loadPlan(Number(el.plan.value)).catch(showError));
  el.block.addEventListener("change", () => {
    renderProjects();
    loadSelectedProject().catch(showError);
  });
  el.project.addEventListener("change", () => loadSelectedProject().catch(showError));
  el.csv.addEventListener("change", () => handleCsvImport().catch(showError));
  $("clearFormBtn").addEventListener("click", hydrateFormFromProject);
  el.cancelBtn.addEventListener("click", cancelCurrentRun);
  $("projectType").addEventListener("change", toggleGroupSize);
  $("generateBonus").addEventListener("change", toggleBonusWish);
  $("methodologyHumanReview").addEventListener("change", toggleAssistant);
  document.querySelectorAll("[data-tab-target]").forEach((button) => button.addEventListener("click", () => activateTab(button.dataset.tabTarget)));
  document.querySelectorAll("[data-action='toggle-expander']").forEach((button) => button.addEventListener("click", () => $(button.dataset.target)?.classList.toggle("collapsed")));
  document.querySelector("[data-action='upload-curriculum']").addEventListener("click", (event) => {
    if (event.target.tagName !== "INPUT") el.csv.click();
  });
  $("insertRegenTemplateBtn").addEventListener("click", () => setValue("regenerationComments", "Что исправить:\nКак должно стать:\nЧто не трогать:"));
  $("clearRegenerationBtn").addEventListener("click", () => {
    setValue("regenerationComments", "");
    setValue("regenerationGlobalComment", "");
  });
  $("fillFailedCriteriaBtn").addEventListener("click", fillCommentsFromFailedCriteria);
  $("regenerateBtn").addEventListener("click", regenerateCurrentRun);
  $("readmeModeMarkdown").addEventListener("click", () => setReadmeMode("markdown"));
  $("readmeModePreview").addEventListener("click", () => setReadmeMode("preview"));
  $("readmeModeCompare").addEventListener("click", compareCurrentResult);
  el.archiveBtn.addEventListener("click", downloadCurrentArchive);
  $("assistantChatClose").addEventListener("click", () => { el.assistant.hidden = true; });
  $("assistantChatSend").addEventListener("click", sendAssistantComment);
  $("assistantActionContinue").addEventListener("click", () => sendReviewAction("continue"));
  $("assistantActionAccept").addEventListener("click", approveReviewDiff);
  $("assistantActionEdit").addEventListener("click", requestReviewChangesFromChat);
  $("assistantActionCompare").addEventListener("click", previewReviewChanges);
  document.querySelectorAll("[data-assistant-suggestion]").forEach((button) => button.addEventListener("click", () => setValue("assistantChatInput", button.dataset.assistantSuggestion)));
  bindModelMenu();
}

function bindModelMenu() {
  const button = $("modelMenuButton");
  const menu = $("modelMenu");
  if (!button || !menu) return;
  button.addEventListener("click", () => {
    menu.hidden = !menu.hidden;
    button.setAttribute("aria-expanded", String(!menu.hidden));
  });
  menu.querySelectorAll("[data-model]").forEach((item) => item.addEventListener("click", () => {
    menu.querySelectorAll("[data-model]").forEach((option) => option.setAttribute("aria-selected", "false"));
    item.setAttribute("aria-selected", "true");
    button.textContent = item.dataset.model === "polza" ? "ИИ" : item.dataset.model.slice(0, 2).toUpperCase();
    menu.hidden = true;
    button.setAttribute("aria-expanded", "false");
  }));
}

function setReadmeMode(mode) {
  state.readmeMode = mode;
  $("readmeModeMarkdown").classList.toggle("active", mode === "markdown");
  $("readmeModePreview").classList.toggle("active", mode === "preview");
  renderReadme(state.currentResult?.document?.markdown || "");
}

function compareCurrentResult() {
  const markdown = state.currentResult?.document?.markdown || "";
  const preview = state.currentReview?.preview_markdown || "";
  el.output.innerHTML = `<div class="regeneration-compare-view"><div class="regeneration-compare-summary"><strong>Сравнение</strong><span>${preview ? "Предпросмотр методологических правок" : "Перегенерированная версия появится после повторного запуска."}</span></div><pre>${escapeHtml(preview || markdown)}</pre></div>`;
}

function fillCommentsFromFailedCriteria() {
  const issues = asList(state.currentResult?.rule_issues).concat(asList(state.currentResult?.gate_review?.issues));
  setValue("regenerationComments", issues.length ? issues.map((issue) => `- ${issue.code || issue.kind}: ${issue.message}`).join("\n") : "Непройденных критериев нет. Уточните желаемую правку вручную.");
}

function selectedRegenerationScopes() {
  return Array.from(document.querySelectorAll("#regenerationSectionSelector input:checked")).map((input) => ({
    title: input.dataset.title || "README section",
    start_line: Number(input.dataset.startLine || 1),
    end_line: Number(input.dataset.endLine || input.dataset.startLine || 1),
  }));
}

async function regenerateCurrentRun(event) {
  event?.preventDefault();
  if (!state.currentRunId || !state.currentResult) {
    await runGeneration(event);
    return;
  }
  const instruction = value("regenerationComments") || value("regenerationGlobalComment");
  if (!instruction.trim()) {
    setStatus("Опишите правку для перегенерации.", "warning");
    activateTab("generatorRegen");
    return;
  }
  setStatus("Перегенерирую выбранные части README...", "running");
  const data = await request(`/generator/runs/${state.currentRunId}/regenerate`, {
    method: "POST",
    body: JSON.stringify({ instruction, scopes: selectedRegenerationScopes() }),
  });
  state.currentReview = data.methodology || null;
  if (data.result) await renderResult(data.result);
  renderPollingState(data);
  renderReviewWorkspace(data);
  activateTab("generatorRegen");
  setStatus("Перегенерация применена", "success");
}

async function sendAssistantComment() {
  const input = $("assistantChatInput");
  const text = input.value.trim();
  if (!text) return;
  addAssistantMessage("user", text);
  setValue("regenerationGlobalComment", text);
  if (state.currentRunId) {
    try {
      const data = await request(`/generator/runs/${state.currentRunId}/review/assistant`, {
        method: "POST",
        body: JSON.stringify({ message: text, selected_target_id: value("assistantChangeTarget") }),
      });
      state.currentReview = data.methodology || null;
      renderReviewWorkspace(data);
      addAssistantMessage("assistant", "Команда сохранена в контуре методолога. Можно сделать предпросмотр или принять изменения.");
    } catch (error) {
      addAssistantMessage("assistant", `Не удалось отправить команду: ${error.message}`);
    }
  } else {
    addAssistantMessage("assistant", "Комментарий сохранён как общая правка для следующей перегенерации.");
  }
  input.value = "";
}

function toggleGroupSize() {
  $("groupSizeGroup").hidden = value("projectType") !== "group";
}

function toggleBonusWish() {
  $("bonusWishGroup").hidden = !$("generateBonus").checked;
}

function value(id) {
  return ($(id)?.value || "").trim();
}

function setValue(id, next) {
  const node = $(id);
  if (node) node.value = next ?? "";
}

function setText(id, next) {
  const node = $(id);
  if (node) node.textContent = String(next ?? "");
}

function selectedText(select) {
  return select?.selectedOptions?.[0]?.textContent?.trim() || "—";
}

function lines(id) {
  return value(id).split(/\r?\n|;/).map((item) => item.trim()).filter(Boolean);
}

function splitList(text) {
  return String(text || "").split(/\r?\n|,|;/).map((item) => item.trim()).filter(Boolean);
}

function asLine(value) {
  return Array.isArray(value) ? value.filter(Boolean).join("\n") : String(value || "");
}

function asList(value) {
  return Array.isArray(value) ? value : [];
}

function count(value) {
  return Array.isArray(value) ? value.length : Number(value || 0);
}

function wordCount(markdown) {
  return (String(markdown || "").match(/[A-Za-zА-Яа-яЁё0-9][A-Za-zА-Яа-яЁё0-9_/-]*/g) || []).length;
}

function directionCode(value) {
  const text = String(value || "").toLowerCase();
  if (text.includes("кибер")) return "Cb";
  if (text.includes("devops")) return "DO";
  if (text.includes("тест")) return "QA";
  if (text.includes("машин") || text.includes("data")) return "DS";
  return "BSA";
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
}

function escapeAttr(value) {
  return escapeHtml(value).replace(/`/g, "&#96;");
}

bindEvents();
renderTimeline();
loadPlans().catch(showError);
loadRecentRuns().catch(() => {});
