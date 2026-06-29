const state = {
  plans: [],
  cascade: null,
  currentPlan: null,
  currentProject: null,
};

const el = {
  csvInput: document.getElementById("csvInput"),
  exportCsv: document.getElementById("exportCsv"),
  planSelect: document.getElementById("planSelect"),
  blockSelect: document.getElementById("blockSelect"),
  projectSelect: document.getElementById("projectSelect"),
  statusLine: document.getElementById("statusLine"),
  form: document.getElementById("projectForm"),
  title: document.getElementById("projectTitle"),
  order: document.getElementById("projectOrder"),
  block: document.getElementById("projectBlock"),
  hours: document.getElementById("projectHours"),
  description: document.getElementById("projectDescription"),
  outcomes: document.getElementById("projectOutcomes"),
  tools: document.getElementById("projectTools"),
  story: document.getElementById("projectStory"),
  summaryPlans: document.getElementById("curriculumSummaryPlans"),
  summaryBlocks: document.getElementById("curriculumSummaryBlocks"),
  summaryProjects: document.getElementById("curriculumSummaryProjects"),
  summaryHours: document.getElementById("curriculumSummaryHours"),
  summaryStatus: document.getElementById("curriculumSummaryStatus"),
};

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${response.status}`);
  }
  if (response.status === 204) return null;
  return response.json();
}

async function loadPlans(selectPlanId = null) {
  state.plans = await request("/curriculum/plans");
  renderPlanOptions(selectPlanId);
  if (state.plans.length) {
    await loadPlan(Number(el.planSelect.value));
  } else {
    renderSummary();
    setStatus("Нет сохраненных учебных планов");
  }
}

function renderPlanOptions(selectPlanId) {
  el.planSelect.innerHTML = "";
  for (const plan of state.plans) {
    const option = document.createElement("option");
    option.value = plan.plan_id;
    option.textContent = `${plan.direction || "Без направления"} · ${plan.title}`;
    el.planSelect.append(option);
  }
  if (selectPlanId) el.planSelect.value = String(selectPlanId);
}

async function loadPlan(planId) {
  if (!planId) return;
  const [planPayload, cascade] = await Promise.all([
    request(`/curriculum/plans/${planId}`),
    request(`/curriculum/plans/${planId}/cascade`),
  ]);
  state.currentPlan = planPayload.plan;
  state.cascade = cascade;
  renderBlocks();
  renderSummary();
  await loadSelectedProject();
  setStatus(`${cascade.direction || "Направление"} · ${cascade.blocks.length} блоков`);
}

function renderSummary() {
  const blocks = state.cascade?.blocks || [];
  const projects = blocks.reduce((count, block) => count + block.projects.length, 0);
  const rows = state.currentPlan?.rows || [];
  const hours = rows.reduce((sum, row) => sum + Number(row.hours_astro || 0), 0);
  setText(el.summaryPlans, state.plans.length || 0);
  setText(el.summaryBlocks, blocks.length || 0);
  setText(el.summaryProjects, projects || rows.length || 0);
  setText(el.summaryHours, hours ? Number(hours.toFixed(1)) : 0);
  setText(el.summaryStatus, state.currentPlan?.status || "draft");
}

function setText(node, value) {
  if (node) node.textContent = String(value);
}

function renderBlocks() {
  el.blockSelect.innerHTML = "";
  for (const block of state.cascade.blocks) {
    const option = document.createElement("option");
    option.value = block.name;
    option.textContent = block.name;
    el.blockSelect.append(option);
  }
  renderProjects();
}

function renderProjects() {
  const block = selectedBlock();
  el.projectSelect.innerHTML = "";
  for (const project of block?.projects || []) {
    const option = document.createElement("option");
    option.value = project.project_id;
    option.textContent = `${project.order}. ${project.title}`;
    el.projectSelect.append(option);
  }
}

async function loadSelectedProject() {
  const projectId = Number(el.projectSelect.value);
  if (!projectId) return;
  const payload = await request(`/curriculum/projects/${projectId}`);
  state.currentProject = payload;
  fillForm(payload.project);
}

function selectedBlock() {
  return (state.cascade?.blocks || []).find((block) => block.name === el.blockSelect.value);
}

function fillForm(project) {
  el.title.value = project.title || "";
  el.order.value = project.order || 1;
  el.block.value = project.block || "";
  el.hours.value = project.hours_astro || 0;
  el.description.value = project.description || "";
  el.outcomes.value = (project.outcomes_can || project.learning_outcomes || []).join("\n");
  el.tools.value = (project.required_tools || []).join(", ");
  el.story.value = project.storytelling || "";
}

function formProject() {
  const current = state.currentProject.project;
  return {
    ...current,
    title: el.title.value.trim(),
    order: Number(el.order.value || 1),
    block: el.block.value.trim(),
    hours_astro: Number(el.hours.value || 0),
    description: el.description.value.trim(),
    outcomes_can: splitLines(el.outcomes.value),
    required_tools: splitComma(el.tools.value),
    storytelling: el.story.value.trim(),
  };
}

function splitLines(value) {
  return value.split(/\n+/).map((item) => item.trim()).filter(Boolean);
}

function splitComma(value) {
  return value.split(/[,;\n]+/).map((item) => item.trim()).filter(Boolean);
}

function setStatus(message) {
  el.statusLine.textContent = message;
}

el.planSelect.addEventListener("change", () => loadPlan(Number(el.planSelect.value)).catch((error) => setStatus(error.message)));
el.blockSelect.addEventListener("change", () => {
  renderProjects();
  loadSelectedProject().catch((error) => setStatus(error.message));
});
el.projectSelect.addEventListener("change", () => loadSelectedProject().catch((error) => setStatus(error.message)));

el.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.currentProject) return;
  const saved = await request(`/curriculum/projects/${state.currentProject.project_id}`, {
    method: "PUT",
    body: JSON.stringify(formProject()),
  });
  state.currentProject = saved;
  await loadPlan(Number(el.planSelect.value));
  setStatus("Сохранено");
});

el.csvInput.addEventListener("change", async () => {
  const file = el.csvInput.files?.[0];
  if (!file) return;
  const csvText = await file.text();
  const created = await request("/curriculum/plans/import-csv", {
    method: "POST",
    body: JSON.stringify({ csv_text: csvText, title: file.name.replace(/\.csv$/i, "") }),
  });
  await loadPlans(created.plan_id);
  setStatus("CSV импортирован");
});

el.exportCsv.addEventListener("click", () => {
  const planId = Number(el.planSelect.value);
  if (planId) window.location.href = `/curriculum/plans/${planId}/export.csv`;
});

loadPlans().catch((error) => setStatus(error.message));
