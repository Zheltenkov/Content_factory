const form = document.getElementById("checkerForm");
const markdownInput = document.getElementById("markdownInput");
const statusLine = document.getElementById("checkerStatus");
const summary = document.getElementById("checkerSummary");
const output = document.getElementById("checkerOutput");
const preview = document.getElementById("checkerPreview");
const warningsArea = document.getElementById("warningsArea");
const scorePercent = document.getElementById("checkerScorePercent");
const scoreValue = document.getElementById("checkerScoreValue");
const scoreStatus = document.getElementById("checkerScoreStatus");
const improveWarning = document.getElementById("improveReadmeWarning");
const improveButton = document.getElementById("checkerImproveTopBtn");
const modal = document.getElementById("improvementModal");
const loading = document.getElementById("improvementLoading");
const improvedTab = document.getElementById("improvedReadmeTab");
const diffTab = document.getElementById("checkerDiffTab");
const improvedPreview = document.getElementById("improvedReadmePreview");
const diffOutput = document.getElementById("checkerDiffOutput");
const textStats = document.getElementById("checkerTextStats");
const runView = document.getElementById("checkerImprovementRunView");
const runProgress = document.getElementById("checkerRunProgress");
const metricsSwitcher = document.getElementById("checkerMetricsVersionSwitcher");
const metricsOriginal = document.getElementById("checkerMetricsOriginal");
const metricsImproved = document.getElementById("checkerMetricsImproved");
const diffStats = document.getElementById("checkerDiffStats");
const diffTable = document.getElementById("checkerDiffTable");
const runRing = document.getElementById("checkerRunRing");
const runPercent = document.getElementById("checkerRunPercent");

let originalReadme = "";
let improvedReadme = "";
let originalIssues = [];
let improvedIssues = [];
let improvementRequestId = null;
let improvementGenerationRequestId = null;
let diffRows = [];
let diffStatsPayload = {};
let diffFilter = "changes";
let diffIndex = -1;
let runTimer = null;
let runStartedAt = 0;
let checkerCurriculumRows = [];

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  await checkReadme(markdownInput.value);
});

document.getElementById("readmeFile").addEventListener("change", handleReadmeFileSelect);
document.getElementById("checkerRemoveFileBtn").addEventListener("click", clearCheckerFile);
document.getElementById("checkerClearBtn").addEventListener("click", clearCheckerResults);
document.getElementById("checkerReportOnlyBtn").addEventListener("click", () => activateTab("checkerStatsTab"));
document.getElementById("checkerImproveTopBtn").addEventListener("click", startImprovement);
document.getElementById("closeImprovementModalBtn").addEventListener("click", closeImprovementModal);
document.getElementById("cancelImprovementBtn").addEventListener("click", closeImprovementModal);
document.getElementById("improvementForm").addEventListener("submit", generateImprovedReadme);
document.getElementById("downloadImprovedReadmeBtn").addEventListener("click", downloadImprovedReadme);
document.getElementById("showAllDiffBtn").addEventListener("click", () => setDiffFilter("all"));
document.getElementById("showChangedDiffBtn").addEventListener("click", () => setDiffFilter("changes"));
document.getElementById("prevDiffBtn").addEventListener("click", () => navigateDiff(-1));
document.getElementById("nextDiffBtn").addEventListener("click", () => navigateDiff(1));
document.getElementById("checkerCurriculumFile").addEventListener("change", handleCheckerCurriculumUpload);
document.getElementById("checkerCurriculumBlock").addEventListener("change", populateCurriculumProjects);
document.getElementById("checkerMetricsTabOriginal").addEventListener("click", () => switchCheckerMetricsVersion("original"));
document.getElementById("checkerMetricsTabImproved").addEventListener("click", () => switchCheckerMetricsVersion("improved"));
document.getElementById("improveThematicBlock").addEventListener("change", toggleImproveAddBlock);
document.getElementById("addImproveBlockBtn").addEventListener("click", addImprovementThematicBlock);
document.getElementById("improveProjectType").addEventListener("change", toggleImproveGroupSize);
document.getElementById("improveGenerateBonus").addEventListener("change", toggleImproveBonusWish);

document.querySelectorAll(".tab-button[data-tab-target]").forEach((button) => {
  button.addEventListener("click", () => activateTab(button.dataset.tabTarget));
});

async function checkReadme(markdown) {
  originalReadme = markdown.trim();
  statusLine.textContent = "Проверка...";
  output.textContent = "";
  warningsArea.innerHTML = "";
  await renderMarkdownPreview(preview, originalReadme, "README пуст.");
  renderTextStats(originalReadme);
  const response = await fetch("/checker/evaluate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      markdown: originalReadme,
      learning_outcomes: lines("learningOutcomes"),
    }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    statusLine.textContent = body.detail || `HTTP ${response.status}`;
    return;
  }
  const result = await response.json();
  const issues = result.rubric_json?.issues || [];
  originalIssues = issues;
  renderScore(result, issues);
  renderIssues(issues);
  renderMetricsVersion("original", result.rubric_json || {}, result.didactic || null);
  output.textContent = JSON.stringify(issues, null, 2);
  statusLine.textContent = "Готово";
  improveButton.disabled = !originalReadme;
  activateTab("checkerCriteriaTab");
}

async function startImprovement() {
  if (!originalReadme && markdownInput.value.trim()) {
    await checkReadme(markdownInput.value);
  }
  if (!originalReadme) {
    statusLine.textContent = "Сначала загрузите или вставьте README.";
    return;
  }
  modal.hidden = false;
  loading.hidden = false;
  document.getElementById("improvementWarnings").textContent = "";
  try {
    const response = await fetch("/checker/improve/extract", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        readme_text: originalReadme,
        curriculum_context: collectCurriculumContext(),
      }),
    });
    if (!response.ok) throw new Error(await response.text());
    const data = await response.json();
    improvementRequestId = data.request_id;
    fillImprovementForm(data.partial_seed || {}, data.classification || {});
    const warnings = data.metadata?.warnings || [];
    document.getElementById("improvementWarnings").innerHTML = warnings.map((item) => `<div>${escapeHtml(item)}</div>`).join("");
  } catch (error) {
    document.getElementById("improvementWarnings").textContent = `Ошибка извлечения: ${error.message}`;
  } finally {
    loading.hidden = true;
  }
}

async function generateImprovedReadme(event) {
  event.preventDefault();
  if (!improvementRequestId) return;
  closeImprovementModal();
  startRunView();
  const response = await fetch("/checker/improve/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ request_id: improvementRequestId, seed: buildImprovementSeed() }),
  });
  if (!response.ok) {
    finishRunView("failed");
    statusLine.textContent = await response.text();
    return;
  }
  const started = await response.json();
  improvementGenerationRequestId = started.generation_request_id;
  await pollImprovementStatus(improvementGenerationRequestId);
}

async function pollImprovementStatus(generationRequestId) {
  const response = await fetch(`/checker/improve/status/${generationRequestId}`);
  if (!response.ok) {
    finishRunView("failed");
    statusLine.textContent = await response.text();
    return;
  }
  const data = await response.json();
  setRunProgress(data.progress || 100, data.phase || "completed");
  if (data.status !== "completed") {
    setTimeout(() => pollImprovementStatus(generationRequestId), 1200);
    return;
  }
  improvedReadme = data.result?.markdown || "";
  improvedIssues = data.result?.rubric?.issues || [];
  renderMetricsVersion("improved", data.result?.rubric || {}, data.result?.didactic || null);
  metricsSwitcher.hidden = false;
  switchCheckerMetricsVersion("improved");
  finishRunView("completed");
  await renderMarkdownPreview(improvedPreview, improvedReadme, "Улучшенный README пуст.");
  improvedTab.hidden = false;
  diffTab.hidden = false;
  await loadReadmeDiff(improvementRequestId);
  activateTab("checkerImprovedTab");
  statusLine.textContent = "Улучшенный README готов";
}

async function loadReadmeDiff(requestId) {
  const response = await fetch(`/checker/improve/diff/${requestId}`);
  if (!response.ok) return;
  const data = await response.json();
  diffRows = data.side_by_side || [];
  diffStatsPayload = data.stats || {};
  renderDiff();
}

function renderScore(result, issues) {
  const hard = issues.filter((issue) => issue.severity === "hard").length;
  const soft = issues.length - hard;
  const score = Math.max(0, Math.round(100 - hard * 18 - soft * 7));
  const passed = result.passed && !result.gate_review?.human_review_required;
  scorePercent.textContent = `${score}%`;
  document.getElementById("checkerScoreRing").style.setProperty("--score", `${score}%`);
  scoreValue.textContent = passed ? "passed" : "needs review";
  scoreStatus.textContent = passed ? "Критических дефектов нет" : "Нужна правка README";
  improveWarning.hidden = passed;
  summary.innerHTML = `
    <span>${passed ? "passed" : "needs review"}</span>
    <span>${issues.length} issues</span>
    <span>${hard} hard</span>
    <span>${result.gate_review?.human_review_required ? "human review" : "auto"}</span>
  `;
}

function renderIssues(issues) {
  warningsArea.innerHTML = issues.slice(0, 8).map((issue) => `
    <article class="issue-card ${issue.severity === "hard" ? "hard" : ""}">
      <strong>${escapeHtml(issue.code || issue.skill_id || "issue")}</strong>
      <span>${escapeHtml(issue.message || issue.detail || "")}</span>
    </article>
  `).join("");
}

function renderTextStats(markdown) {
  const words = markdown.trim() ? markdown.trim().split(/\s+/).length : 0;
  const headings = (markdown.match(/^#{1,6}\s+/gm) || []).length;
  const fences = (markdown.match(/```/g) || []).length;
  textStats.innerHTML = [
    metricCard("Слов", words),
    metricCard("Заголовков", headings),
    metricCard("Code fence", fences),
    metricCard("Строк", markdown.splitlines?.length || markdown.split("\n").length),
  ].join("");
}

function renderMetricsVersion(version, rubric, didactic) {
  const issues = rubric.issues || [];
  const didacticScore = didactic?.overall_raw != null ? `${Number(didactic.overall_raw).toFixed(1)}/5` : "—";
  const target = version === "improved" ? metricsImproved : metricsOriginal;
  target.innerHTML = [
    metricCard("Passed", rubric.passed ? "Да" : "Нет"),
    metricCard("Issues", issues.length),
    metricCard("Hard", issues.filter((issue) => issue.severity === "hard").length),
    metricCard("Soft", issues.filter((issue) => issue.severity !== "hard").length),
    metricCard("Didactic", didacticScore),
    metricCard("Didactic review", didactic?.needs_human_review ? "Да" : "Нет"),
  ].join("");
}

function switchCheckerMetricsVersion(version) {
  const improved = version === "improved";
  metricsOriginal.hidden = improved;
  metricsImproved.hidden = !improved;
  document.getElementById("checkerMetricsTabOriginal").classList.toggle("active", !improved);
  document.getElementById("checkerMetricsTabImproved").classList.toggle("active", improved);
  output.textContent = JSON.stringify(improved ? improvedIssues : originalIssues, null, 2);
}

function fillImprovementForm(seed, classification) {
  setValue("improveTitleSeed", seed.title_seed);
  setValue("improveDescription", seed.project_description);
  setValue("improveLanguage", classification.language || "ru");
  const thematicCode = classification.thematic_block || classification.thematic_block_suggested || "";
  ensureThematicOption(thematicCode, classification.thematic_block_name);
  setValue("improveThematicBlock", thematicCode);
  setValue("improveAudienceLevel", classification.audience_level || "base");
  setValue("improveProjectType", classification.project_type || "individual");
  setValue("improveGroupSize", classification.group_size || 2);
  setValue("improveTasksCount", seed.tasks_count || "");
  setValue("improveLearningOutcomes", (seed.learning_outcomes || []).join("\n"));
  setValue("improveSkills", (seed.skills || []).join(", "));
  setValue("improveRequiredTools", (seed.required_tools || []).join(", "));
  toggleImproveGroupSize();
  toggleImproveBonusWish();
  toggleImproveAddBlock();
}

function buildImprovementSeed() {
  return {
    language: value("improveLanguage"),
    project_type: value("improveProjectType"),
    thematic_block: selectedThematicBlock(),
    audience_level: value("improveAudienceLevel"),
    title_seed: value("improveTitleSeed"),
    project_description: value("improveDescription"),
    learning_outcomes: lines("improveLearningOutcomes"),
    skills: csv("improveSkills"),
    required_tools: csv("improveRequiredTools"),
    tasks_count: numberOrNull("improveTasksCount"),
    group_size: numberOrNull("improveGroupSize"),
    methodology_human_review: document.getElementById("improveMethodologyHumanReview").checked,
    zun: value("improveZUN"),
    bonus_wish: document.getElementById("improveGenerateBonus").checked ? value("improveBonusWish") : null,
    repo_base_url: value("improveRepoBaseUrl"),
    repo_path_template: value("improveRepoPathTemplate"),
  };
}

function renderDiff() {
  const rows = diffFilter === "changes" ? diffRows.filter((row) => row.type !== "equal") : diffRows;
  diffStats.innerHTML = [
    metricCard("Исходный", diffStatsPayload.original_lines || 0),
    metricCard("Улучшенный", diffStatsPayload.improved_lines || 0),
    metricCard("Добавлено", diffStatsPayload.added || 0),
    metricCard("Удалено", diffStatsPayload.deleted || 0),
    metricCard("Изменено", diffStatsPayload.modified || 0),
  ].join("");
  diffTable.innerHTML = rows.slice(0, 80).map((row, index) => `
    <article class="review-item diff-${escapeHtml(row.type)} ${index === diffIndex ? "active" : ""}">
      <strong>${escapeHtml(row.type)}</strong>
      <span>− ${escapeHtml(row.original || "")}</span>
      <span>+ ${escapeHtml(row.improved || "")}</span>
    </article>
  `).join("");
  diffOutput.textContent = rows.map((row, index) => {
    const marker = row.type === "insert" ? "+" : row.type === "delete" ? "-" : row.type === "replace" ? "~" : " ";
    const original = row.original || "";
    const improved = row.improved || "";
    const active = index === diffIndex ? ">" : " ";
    return `${active}${marker} ${original}\n ${marker} ${improved}`;
  }).join("\n");
}

function setDiffFilter(nextFilter) {
  diffFilter = nextFilter;
  diffIndex = -1;
  renderDiff();
  activateTab("checkerDiffTabPanel");
}

function navigateDiff(direction) {
  const rows = (diffFilter === "changes" ? diffRows.filter((row) => row.type !== "equal") : diffRows);
  if (!rows.length) return;
  diffIndex = Math.max(0, Math.min(rows.length - 1, diffIndex + direction));
  renderDiff();
}

function startRunView() {
  runView.hidden = false;
  document.getElementById("improvementGenerationProgress").hidden = false;
  runStartedAt = Date.now();
  setRunProgress(12, "extract");
  runTimer = setInterval(() => {
    const seconds = Math.floor((Date.now() - runStartedAt) / 1000);
    const formatted = `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
    document.getElementById("improvementTimer").textContent = formatted;
    document.getElementById("checkerRunTimer").textContent = formatted;
  }, 1000);
}

function finishRunView(status) {
  clearInterval(runTimer);
  runTimer = null;
  setRunProgress(status === "completed" ? 100 : 0, status);
  setTimeout(() => { runView.hidden = true; }, 500);
}

function setRunProgress(percent, phase) {
  const pct = Math.max(0, Math.min(100, Number(percent) || 0));
  runProgress.style.setProperty("--progress", `${pct}%`);
  runRing?.style.setProperty("--run-progress", `${pct}%`);
  if (runPercent) runPercent.textContent = `${pct}%`;
  document.getElementById("improvementCurrentAgent").textContent = phaseLabel(phase);
  document.getElementById("checkerRunStageIndex").textContent = pct >= 100 ? "06 из 06" : "03 из 06";
}

async function handleReadmeFileSelect(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  const text = await file.text();
  markdownInput.value = text;
  document.getElementById("checkerReadmeUploadTitle").textContent = file.name;
  document.getElementById("readmeFileNameChecker").textContent = `${Math.max(1, Math.round(file.size / 1024))} КБ · загружен`;
  await renderMarkdownPreview(preview, text, "README пуст.");
}

function clearCheckerFile() {
  document.getElementById("readmeFile").value = "";
  document.getElementById("checkerReadmeUploadTitle").textContent = "Загрузить README.md";
  document.getElementById("readmeFileNameChecker").textContent = "Markdown-файл для проверки";
}

function clearCheckerResults() {
  markdownInput.value = "";
  originalReadme = "";
  improvedReadme = "";
  improvementRequestId = null;
  improvementGenerationRequestId = null;
  output.textContent = "";
  summary.innerHTML = "";
  metricsOriginal.innerHTML = "";
  metricsImproved.innerHTML = "";
  metricsSwitcher.hidden = true;
  originalIssues = [];
  improvedIssues = [];
  warningsArea.innerHTML = "";
  statusLine.textContent = "";
  scorePercent.textContent = "—";
  scoreValue.textContent = "—";
  scoreStatus.textContent = "Загрузите README для оценки";
  improveButton.disabled = true;
  improvedTab.hidden = true;
  diffTab.hidden = true;
  clearCheckerFile();
  renderMarkdownPreview(preview, "", "README пуст.");
}

function closeImprovementModal() {
  modal.hidden = true;
}

function downloadImprovedReadme() {
  if (!improvementGenerationRequestId) return;
  window.location.href = `/checker/improve/download/${improvementGenerationRequestId}`;
}

function collectCurriculumContext() {
  return {
    block: document.getElementById("checkerCurriculumBlock").value,
    project: document.getElementById("checkerCurriculumProject").value,
    learning_outcomes: lines("learningOutcomes"),
  };
}

async function handleCheckerCurriculumUpload(event) {
  const file = event.target.files?.[0];
  const label = document.getElementById("checkerCurriculumFileName");
  if (!file) {
    label.textContent = "Для точного контекста улучшения";
    checkerCurriculumRows = [];
    populateCurriculumBlocks();
    return;
  }
  const text = await file.text();
  checkerCurriculumRows = parseCurriculumCsv(text);
  label.textContent = `${file.name} · ${checkerCurriculumRows.length} строк`;
  populateCurriculumBlocks();
}

function parseCurriculumCsv(text) {
  const lines = text.split(/\r?\n/).filter((line) => line.trim());
  if (!lines.length) return [];
  const delimiter = lines[0].includes(";") ? ";" : ",";
  const header = splitCsvLine(lines[0], delimiter).map((item) => item.toLowerCase());
  return lines.slice(1).map((line) => {
    const cells = splitCsvLine(line, delimiter);
    const byName = Object.fromEntries(header.map((name, index) => [name, cells[index] || ""]));
    return {
      block: byName["block"] || byName["блок"] || byName["тематический блок"] || cells[3] || cells[0] || "Без блока",
      project: byName["project"] || byName["проект"] || byName["название проекта"] || cells[6] || cells[1] || "Без названия",
    };
  });
}

function splitCsvLine(line, delimiter) {
  const cells = [];
  let current = "";
  let quoted = false;
  for (const char of line) {
    if (char === '"') quoted = !quoted;
    else if (char === delimiter && !quoted) {
      cells.push(current.trim());
      current = "";
    } else current += char;
  }
  cells.push(current.trim());
  return cells;
}

function populateCurriculumBlocks() {
  const select = document.getElementById("checkerCurriculumBlock");
  const blocks = Array.from(new Set(checkerCurriculumRows.map((row) => row.block).filter(Boolean)));
  select.innerHTML = '<option value="">— Тематический блок —</option>' + blocks.map((block) => `<option value="${escapeHtml(block)}">${escapeHtml(block)}</option>`).join("");
  populateCurriculumProjects();
}

function populateCurriculumProjects() {
  const block = document.getElementById("checkerCurriculumBlock").value;
  const select = document.getElementById("checkerCurriculumProject");
  const projects = checkerCurriculumRows.filter((row) => !block || row.block === block).map((row) => row.project).filter(Boolean);
  select.innerHTML = '<option value="">— Проект в блоке —</option>' + projects.map((project) => `<option value="${escapeHtml(project)}">${escapeHtml(project)}</option>`).join("");
}

function toggleImproveAddBlock() {
  const expander = document.getElementById("improveAddBlockExpander");
  const visible = document.getElementById("improveThematicBlock").value === "ADD";
  expander.hidden = !visible;
  expander.open = visible;
}

function addImprovementThematicBlock() {
  const name = value("improveNewBlockName");
  const code = value("improveNewBlockCode");
  if (!name || !code) {
    document.getElementById("improvementWarnings").textContent = "Введите название и код тематического блока.";
    return;
  }
  const select = document.getElementById("improveThematicBlock");
  if (!Array.from(select.options).some((option) => option.value === code)) {
    const option = document.createElement("option");
    option.value = code;
    option.textContent = name;
    select.insertBefore(option, select.querySelector('option[value="ADD"]'));
  }
  select.value = code;
  document.getElementById("improveAddBlockExpander").hidden = true;
}

function ensureThematicOption(code, name) {
  if (!code) return;
  const select = document.getElementById("improveThematicBlock");
  if (Array.from(select.options).some((option) => option.value === code)) return;
  const option = document.createElement("option");
  option.value = code;
  option.textContent = name || code;
  select.insertBefore(option, select.querySelector('option[value="ADD"]'));
}

function selectedThematicBlock() {
  const selected = value("improveThematicBlock");
  return selected === "ADD" ? value("improveNewBlockCode") : selected;
}

function toggleImproveGroupSize() {
  document.getElementById("improveGroupSizeGroup").hidden = value("improveProjectType") !== "group";
}

function toggleImproveBonusWish() {
  document.getElementById("improveBonusWishGroup").hidden = !document.getElementById("improveGenerateBonus").checked;
}

function activateTab(targetId) {
  document.querySelectorAll(".tab-button[data-tab-target]").forEach((button) => {
    const active = button.dataset.tabTarget === targetId;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", active ? "true" : "false");
  });
  document.querySelectorAll(".tab-content").forEach((panel) => {
    const active = panel.id === targetId;
    panel.classList.toggle("active", active);
    panel.hidden = !active;
  });
}

async function renderMarkdownPreview(target, markdown, emptyMessage) {
  if (!target) return;
  if (window.ContentFactoryMarkdown) {
    await window.ContentFactoryMarkdown.renderMarkdown(target, markdown, { emptyMessage });
    return;
  }
  target.textContent = markdown || emptyMessage || "";
}

function phaseLabel(phase) {
  return {
    extract: "Извлечение структуры",
    completed: "Готово",
    failed: "Ошибка",
  }[phase] || "Сборка улучшенного README";
}

function metricCard(label, value) {
  return `<div class="metric-card"><strong>${escapeHtml(value)}</strong><span>${escapeHtml(label)}</span></div>`;
}

function value(id) {
  return document.getElementById(id)?.value.trim() || "";
}

function setValue(id, nextValue) {
  const element = document.getElementById(id);
  if (element) element.value = nextValue ?? "";
}

function lines(id) {
  return value(id).split("\n").map((item) => item.trim()).filter(Boolean);
}

function csv(id) {
  return value(id).split(",").map((item) => item.trim()).filter(Boolean);
}

function numberOrNull(id) {
  const numeric = Number(value(id));
  return Number.isFinite(numeric) && numeric > 0 ? numeric : null;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
}
