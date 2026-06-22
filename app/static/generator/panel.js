const form = document.getElementById("generatorForm");
const planSelect = document.getElementById("planSelect");
const blockSelect = document.getElementById("blockSelect");
const projectSelect = document.getElementById("projectSelect");
const profileSelect = document.getElementById("profileSelect");
const programType = document.getElementById("programType");
const statusLine = document.getElementById("generatorStatus");
const projectSummary = document.getElementById("projectSummary");
const progress = document.getElementById("generatorProgress");
const timeline = document.getElementById("generatorTimeline");
const metrics = document.getElementById("generatorMetrics");
const output = document.getElementById("generatorOutput");
const metadataView = document.getElementById("generatorMetadataView");
const issuesView = document.getElementById("generatorIssuesView");
const artifactsView = document.getElementById("generatorArtifactsView");

const state = {
  plans: [],
  cascade: null,
  currentProject: null,
  currentResult: null,
};

const RUN_STEPS = [
  ["context", "Контекст УП"],
  ["generate", "Генерация"],
  ["gate", "Gate"],
  ["render", "Рендер"],
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

async function loadPlans() {
  setStatus("Загрузка учебных планов...");
  state.plans = await request("/curriculum/plans");
  renderPlanOptions();
  if (!state.plans.length) {
    form.querySelector("button[type='submit']").disabled = true;
    projectSummary.textContent = "Нет сохраненных учебных планов. Создайте или импортируйте УП в модуле Учебные планы.";
    setStatus("Нет учебных планов", "error");
    renderTimeline();
    return;
  }
  await loadPlan(Number(planSelect.value));
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.currentProject) {
    setStatus("Выберите проект из учебного плана.", "error");
    return;
  }
  clearResult();
  setStatus("Генерация README из БД-УП...");
  setProgress(45);
  renderTimeline("generate");
  const payload = {
    plan_id: Number(planSelect.value),
    project_order: Number(state.currentProject.project.order),
    profile_id: profileSelect.value || "_base",
  };
  if (programType.value.trim()) payload.program_type = programType.value.trim();
  const result = await request("/generator/runs/from-curriculum", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  state.currentResult = result;
  setProgress(90);
  renderTimeline("render");
  await renderResult(result);
  setProgress(100);
  renderTimeline(null, true);
  setStatus(result.gate_review?.human_review_required ? "Готово. Нужна проверка методолога." : "Готово", result.gate_review?.human_review_required ? "warning" : "success");
});

planSelect.addEventListener("change", () => loadPlan(Number(planSelect.value)).catch(showError));
blockSelect.addEventListener("change", () => {
  renderProjects();
  loadSelectedProject().catch(showError);
});
projectSelect.addEventListener("change", () => loadSelectedProject().catch(showError));

function renderPlanOptions() {
  planSelect.innerHTML = state.plans
    .map((plan) => `<option value="${plan.plan_id}">${escapeHtml(plan.direction || "Без направления")} · ${escapeHtml(plan.title)}</option>`)
    .join("");
}

async function loadPlan(planId) {
  if (!planId) return;
  setProgress(10);
  renderTimeline("context");
  const cascade = await request(`/curriculum/plans/${planId}/cascade`);
  state.cascade = cascade;
  renderBlocks();
  await loadSelectedProject();
  setProgress(20);
  setStatus(`${cascade.direction || "Направление"} · ${cascade.blocks.length} блоков`);
}

function renderBlocks() {
  blockSelect.innerHTML = (state.cascade?.blocks || [])
    .map((block) => `<option value="${escapeHtml(block.name)}">${escapeHtml(block.name)}</option>`)
    .join("");
  renderProjects();
}

function renderProjects() {
  const block = selectedBlock();
  projectSelect.innerHTML = (block?.projects || [])
    .map((project) => `<option value="${project.project_id}">${project.order}. ${escapeHtml(project.title)}</option>`)
    .join("");
}

async function loadSelectedProject() {
  const projectId = Number(projectSelect.value);
  if (!projectId) {
    state.currentProject = null;
    projectSummary.textContent = "В выбранном блоке нет проектов.";
    return;
  }
  state.currentProject = await request(`/curriculum/projects/${projectId}`);
  renderProjectSummary();
}

function selectedBlock() {
  return (state.cascade?.blocks || []).find((block) => block.name === blockSelect.value);
}

function renderProjectSummary() {
  const project = state.currentProject?.project;
  if (!project) return;
  projectSummary.innerHTML = `
    <strong>${escapeHtml(project.order)}. ${escapeHtml(project.title)}</strong>
    <span>${escapeHtml(project.block || "Без блока")} · ${escapeHtml(project.format || "individual")} · ${escapeHtml(project.hours_astro || 0)} ч.</span>
    <span>${escapeHtml(project.description || "Описание не заполнено")}</span>
  `;
}

async function renderResult(result) {
  await renderMarkdownPreview(output, result.document?.markdown || "", "README не вернулся из генератора.");
  renderRunMetrics(result);
  renderMetadata(result);
  renderIssues(result);
  renderArtifacts(result);
  activateTab("generatorReadme");
}

function renderRunMetrics(result) {
  const metadata = result.document?.metadata || {};
  const gate = result.gate_review || {};
  const cards = [
    ["Проект", result.document?.project_id || result.context?.current_project_title || "n/a"],
    ["Теория", count(metadata.theory_parts)],
    ["Практика", count(metadata.practice_tasks)],
    ["Артефакты", count(result.document?.artifacts)],
    ["Gate", gate.status || "n/a"],
    ["Human review", gate.human_review_required ? "yes" : "no"],
  ];
  metrics.innerHTML = cards.map(([label, value]) => metricCard(label, value)).join("");
}

function renderMetadata(result) {
  const context = result.context || {};
  const metadata = result.document?.metadata || {};
  metadataView.innerHTML = `
    <div class="metrics-grid">
      ${metricCard("План", context.plan_title || context.plan_id || "n/a")}
      ${metricCard("Направление", context.direction || "n/a")}
      ${metricCard("Блок", context.block_name || "n/a")}
      ${metricCard("Текущий проект", context.current_project_title || "n/a")}
      ${metricCard("Предыдущие", count(context.previous_projects))}
      ${metricCard("Следующие", count(context.next_block_projects || context.next_projects))}
    </div>
    <details class="generated-data-preview">
      <summary>Document metadata</summary>
      <pre>${escapeHtml(JSON.stringify(metadata, null, 2))}</pre>
    </details>
    <details class="generated-data-preview">
      <summary>Curriculum context</summary>
      <pre>${escapeHtml(JSON.stringify(context, null, 2))}</pre>
    </details>
  `;
}

function renderIssues(result) {
  const rubric = result.rubric_json || {};
  const ruleIssues = (result.rule_issues || []).map((issue) => ({
    code: issue.code,
    message: issue.message,
    severity: issue.severity,
    source: issue.skill_id || "rule",
  }));
  const gateIssues = (result.gate_review?.issues || []).map((issue) => ({
    code: issue.code,
    message: issue.message,
    severity: issue.severity,
    source: result.gate_review.stage || "gate",
  }));
  const issues = [...ruleIssues, ...gateIssues];
  issuesView.innerHTML = `
    <div class="metrics-grid">
      ${metricCard("Rubric", rubric.passed ? "passed" : "needs review")}
      ${metricCard("Hard", rubric.hard_count ?? 0)}
      ${metricCard("Soft", rubric.soft_count ?? 0)}
      ${metricCard("Gate status", result.gate_review?.status || "n/a")}
    </div>
    <div class="issue-list">
      ${
        issues.length
          ? issues.map(renderIssue).join("")
          : '<div class="empty-inline">Дефекты не найдены.</div>'
      }
    </div>
  `;
}

function renderArtifacts(result) {
  const metadata = result.document?.metadata || {};
  const artifacts = [
    ...(result.document?.artifacts || []).map((item) => artifactItem(item.kind || item.family || "artifact", item.path || item.uri || item.target || item.artifact_id)),
    ...asList(metadata.practice_tasks).map((item) => artifactItem("practice", item.artifact_location || item.title)),
    ...asList(metadata.dataset_files).map((item) => artifactItem("dataset", item.path || item.filename || item.title || item.id)),
    ...asList(metadata.code_examples).map((item) => artifactItem("code", item.path || item.filename || item.title || item.language)),
    ...asList(metadata.formula_assets?.tables).map((item) => artifactItem("formula", item.path || item.title || item.id)),
  ].filter((item) => item.value);

  artifactsView.innerHTML = artifacts.length
    ? `<div class="reference-list compact">${artifacts.map((item) => `
        <div class="list-item">
          <strong>${escapeHtml(item.kind)}</strong>
          <span class="path-token">${escapeHtml(item.value)}</span>
        </div>
      `).join("")}</div>`
    : '<div class="empty-inline">Артефакты не вернулись.</div>';
}

function renderIssue(issue) {
  const hard = issue.severity === "hard" || issue.severity === "critical";
  return `
    <article class="issue-card ${hard ? "hard" : ""}">
      <strong>${escapeHtml(issue.code)}</strong>
      <span>${escapeHtml(issue.message)}</span>
      <span class="badge ${hard ? "error" : "warning"}">${escapeHtml(issue.source)} · ${escapeHtml(issue.severity)}</span>
    </article>
  `;
}

function metricCard(label, value) {
  return `<div class="metric-card"><strong>${escapeHtml(value)}</strong><span>${escapeHtml(label)}</span></div>`;
}

function artifactItem(kind, value) {
  return { kind: String(kind || "artifact"), value: String(value || "") };
}

function asList(value) {
  return Array.isArray(value) ? value : [];
}

function count(value) {
  return Array.isArray(value) ? value.length : Number(value || 0);
}

function setProgress(value) {
  progress.style.setProperty("--progress", `${Math.max(0, Math.min(100, value))}%`);
}

function renderTimeline(activeId = null, done = false) {
  timeline.innerHTML = RUN_STEPS.map(([id, label], index) => {
    const isDone = done || RUN_STEPS.findIndex(([stepId]) => stepId === activeId) > index;
    const isNow = activeId === id && !done;
    return `
      <div class="timeline-row ${isDone ? "done" : ""} ${isNow ? "now" : ""}">
        <span class="timeline-dot">${index + 1}</span>
        <strong>${label}</strong>
        <span class="timeline-time">${isDone ? "done" : isNow ? "now" : "wait"}</span>
      </div>
    `;
  }).join("");
}

function activateTab(targetId) {
  const button = document.querySelector(`[data-tab-target="${targetId}"]`);
  button?.click();
}

function clearResult() {
  output.innerHTML = "";
  metadataView.innerHTML = "";
  issuesView.innerHTML = "";
  artifactsView.innerHTML = "";
  metrics.innerHTML = "";
}

function setStatus(message, kind = "") {
  statusLine.textContent = message;
  statusLine.classList.toggle("error", kind === "error");
  statusLine.classList.toggle("success", kind === "success");
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

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
}

renderTimeline();
loadPlans().catch((error) => {
  showError(error);
});
