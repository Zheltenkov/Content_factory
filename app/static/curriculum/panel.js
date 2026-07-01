const state = {
  plans: [],
  cascade: null,
  currentPlan: null,
  currentProject: null,
  templateProposals: [],
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
  blockGoal: document.getElementById("projectBlockGoal"),
  hours: document.getElementById("projectHours"),
  description: document.getElementById("projectDescription"),
  outcomesKnow: document.getElementById("projectOutcomesKnow"),
  outcomes: document.getElementById("projectOutcomes"),
  outcomesSkills: document.getElementById("projectOutcomesSkills"),
  tools: document.getElementById("projectTools"),
  software: document.getElementById("projectSoftware"),
  materials: document.getElementById("projectMaterials"),
  story: document.getElementById("projectStory"),
  format: document.getElementById("projectFormat"),
  groupSize: document.getElementById("projectGroupSize"),
  regenerateTemplateProposals: document.getElementById("regenerateTemplateProposals"),
  templateProposalSummary: document.getElementById("templateProposalSummary"),
  templateProposalList: document.getElementById("templateProposalList"),
  summaryPlans: document.getElementById("curriculumSummaryPlans"),
  summaryBlocks: document.getElementById("curriculumSummaryBlocks"),
  summaryProjects: document.getElementById("curriculumSummaryProjects"),
  summaryHours: document.getElementById("curriculumSummaryHours"),
  summaryStatus: document.getElementById("curriculumSummaryStatus"),
  upProjectsTable: document.getElementById("upProjectsTable"),
  upProjectsCount: document.getElementById("upProjectsCount"),
  upProjectsTitle: document.getElementById("upProjectsTitle"),
  heroTitle: document.getElementById("curriculumHeroTitle"),
  heroSubtitle: document.getElementById("curriculumHeroSubtitle"),
  heroMeta: document.getElementById("curriculumHeroMeta"),
  backToPlanLink: document.getElementById("backToPlanLink"),
  templateStepper: document.getElementById("templateStepper"),
};

const TEMPLATE_FOCUS = window.location.pathname.endsWith("/template-proposals");

function planIdFromLocation() {
  const match = window.location.pathname.match(/^\/up\/plans\/(\d+)/);
  return match ? Number(match[1]) : null;
}

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
  if (!el.planSelect.value && state.plans.length) {
    el.planSelect.value = String(state.plans[0].plan_id);
  }
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
  const [planPayload, cascade, templateProposals] = await Promise.all([
    request(`/curriculum/plans/${planId}`),
    request(`/curriculum/plans/${planId}/cascade`),
    request(`/curriculum/plans/${planId}/template-proposals`),
  ]);
  state.currentPlan = planPayload.plan;
  state.cascade = cascade;
  state.templateProposals = templateProposals;
  renderBlocks();
  renderProjectsTable();
  renderTemplateProposals();
  renderSummary();
  if (TEMPLATE_FOCUS) applyTemplateFocus(planId);
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

const UP_FORMAT_LABELS = { individual: "индивидуальный", group: "групповой", pair: "парный", workshop: "воркшоп", unknown: "—" };

function allCascadeProjects() {
  return (state.cascade?.blocks || []).flatMap((block) => block.projects || []);
}

function renderProjectsTable() {
  const rows = allCascadeProjects()
    .map((entry) => ({ project_id: entry.project_id, ...entry.project }))
    .sort((a, b) => Number(a.order || 0) - Number(b.order || 0));
  if (el.upProjectsTitle) {
    el.upProjectsTitle.textContent = state.currentPlan?.title || "Проекты учебного плана";
  }
  setText(el.upProjectsCount, rows.length);
  el.upProjectsTable.innerHTML = `
    <thead><tr>
      <th>№</th><th>Тематический блок</th><th>Название проекта</th><th>Краткое описание</th>
      <th>Знать</th><th>Уметь</th><th>Навыки</th><th>Инструменты</th><th>Необходимое ПО</th>
      <th>Формат</th><th>Группа</th><th>Астр. часы</th><th>Действия</th>
    </tr></thead>
    <tbody>${rows.map(upProjectRow).join("")}</tbody>`;
}

function upListCell(items) {
  const list = Array.isArray(items) ? items.filter(Boolean) : [];
  if (!list.length) return "<span class=\"muted\">—</span>";
  return `<ul class="up-cell-list">${list.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
}

function upProjectRow(project) {
  const tools = Array.isArray(project.required_tools) ? project.required_tools.join(", ") : "";
  const software = Array.isArray(project.required_software) ? project.required_software.join(", ") : "";
  return `
    <tr>
      <td>${escapeHtml(String(project.order ?? ""))}</td>
      <td><strong>${escapeHtml(project.block || "—")}</strong>${project.block_goal ? `<div class="muted small">${escapeHtml(project.block_goal)}</div>` : ""}</td>
      <td><strong>${escapeHtml(project.title || "—")}</strong></td>
      <td class="muted">${escapeHtml(project.description || "—")}</td>
      <td>${upListCell(project.outcomes_know)}</td>
      <td>${upListCell(project.outcomes_can)}</td>
      <td>${upListCell(project.outcomes_skills)}</td>
      <td class="muted">${escapeHtml(tools || "—")}</td>
      <td class="muted">${escapeHtml(software || "—")}</td>
      <td>${escapeHtml(UP_FORMAT_LABELS[project.format] || project.format || "—")}</td>
      <td>${escapeHtml(String(project.group_size ?? 1))}</td>
      <td>${escapeHtml(String(project.hours_astro ?? 0))}</td>
      <td><button type="button" class="action-btn action-btn-secondary up-edit-btn" data-edit-project="${escapeAttr(String(project.project_id))}">Редактировать</button></td>
    </tr>`;
}

async function editProjectById(projectId) {
  const payload = await request(`/curriculum/projects/${projectId}`);
  state.currentProject = payload;
  const block = payload.project.block || "";
  if ([...el.blockSelect.options].some((option) => option.value === block)) {
    el.blockSelect.value = block;
    renderProjects();
  }
  fillForm(payload.project);
  el.form.scrollIntoView({ behavior: "smooth", block: "start" });
  setStatus(`Редактирование: ${payload.project.title}`);
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
  el.blockGoal.value = project.block_goal || "";
  el.hours.value = project.hours_astro || 0;
  el.description.value = project.description || "";
  el.outcomesKnow.value = (project.outcomes_know || []).join("\n");
  el.outcomes.value = (project.outcomes_can || project.learning_outcomes || []).join("\n");
  el.outcomesSkills.value = (project.outcomes_skills || []).join("\n");
  el.tools.value = (project.required_tools || []).join(", ");
  el.software.value = (project.required_software || []).join(", ");
  el.materials.value = project.materials || "";
  el.story.value = project.storytelling || "";
  el.format.value = project.format || "individual";
  el.groupSize.value = project.group_size || 1;
}

function formProject() {
  const current = state.currentProject.project;
  return {
    ...current,
    title: el.title.value.trim(),
    order: Number(el.order.value || 1),
    block: el.block.value.trim(),
    block_goal: el.blockGoal.value.trim(),
    hours_astro: Number(el.hours.value || 0),
    description: el.description.value.trim(),
    outcomes_know: splitLines(el.outcomesKnow.value),
    outcomes_can: splitLines(el.outcomes.value),
    outcomes_skills: splitLines(el.outcomesSkills.value),
    required_tools: splitComma(el.tools.value),
    required_software: splitComma(el.software.value),
    materials: el.materials.value.trim(),
    storytelling: el.story.value.trim(),
    format: el.format.value,
    group_size: Number(el.groupSize.value || 1),
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

function renderTemplateProposals() {
  const proposals = state.templateProposals || [];
  const counts = proposals.reduce((acc, item) => {
    acc[item.status] = (acc[item.status] || 0) + 1;
    return acc;
  }, {});
  el.templateProposalSummary.innerHTML = [
    metricCard("Всего", proposals.length),
    metricCard("Open", counts.open || 0),
    metricCard("Accepted", counts.accepted || 0),
    metricCard("Rejected", counts.rejected || 0),
  ].join("");
  if (!proposals.length) {
    el.templateProposalList.innerHTML = `<p class="empty-inline">Предложений нет. Сгенерируйте шаблоны по блокам текущего УП.</p>`;
    return;
  }
  el.templateProposalList.innerHTML = proposals.map(renderTemplateProposal).join("");
  if (TEMPLATE_FOCUS) renderTemplateStepper();
}

function applyTemplateFocus(planId) {
  document.body.classList.add("templates-focus");
  document.querySelectorAll(".templates-focus-only").forEach((node) => {
    node.hidden = false;
  });
  if (el.heroTitle) el.heroTitle.textContent = "Предложения шаблонов УП";
  if (el.heroSubtitle) {
    el.heroSubtitle.textContent =
      "Процесс: система предлагает шаблоны по принятым навыкам, методолог редактирует и принимает. После принятия УП перестраивается.";
  }
  if (el.heroMeta) {
    const brief = state.currentPlan?.brief_id || state.currentPlan?.metadata?.brief_id;
    el.heroMeta.hidden = false;
    el.heroMeta.textContent = `учебный план #${planId}${brief ? ` · бриф #${brief}` : ""}`;
  }
  if (el.backToPlanLink) el.backToPlanLink.href = `/up/plans/${planId}`;
  renderTemplateStepper();
}

function renderTemplateStepper() {
  if (!el.templateStepper) return;
  const proposals = state.templateProposals || [];
  const counts = proposals.reduce((acc, item) => {
    acc[item.status] = (acc[item.status] || 0) + 1;
    return acc;
  }, {});
  const steps = [
    ["Автопредложение", `Сгенерировано: ${proposals.length}.`],
    ["Редактирование", `Открыто: ${counts.open || 0}.`],
    ["Принятие", `Принято: ${counts.accepted || 0}, отклонено: ${counts.rejected || 0}.`],
    ["Перестройка УП", "Запускается автоматически при принятии шаблона."],
  ];
  el.templateStepper.hidden = false;
  el.templateStepper.innerHTML = steps
    .map(
      ([title, note], index) => `
      <div class="workflow-step">
        <span class="workflow-step-index">${index + 1}</span>
        <div class="workflow-step-body">
          <span class="workflow-step-label">${escapeHtml(title)}</span>
          <span class="workflow-step-description">${escapeHtml(note)}</span>
        </div>
      </div>`,
    )
    .join("");
}

function renderTemplateProposal(proposal) {
  const disabled = proposal.status !== "open" ? "disabled" : "";
  return `
    <article class="reference-item" data-proposal-id="${proposal.id}">
      <div class="inline-actions">
        <strong>${escapeHtml(proposal.title)}</strong>
        <span class="badge">${escapeHtml(proposal.status)}</span>
      </div>
      <div class="metrics">
        ${metricCard("Type", proposal.artifact_family)}
        ${metricCard("Confidence", Number(proposal.confidence || 0).toFixed(2))}
        ${metricCard("Skills", (proposal.covered_skill_names || []).length)}
      </div>
      <label>Название<input data-field="title" value="${escapeAttr(proposal.title)}" ${disabled} /></label>
      <div class="form-row two">
        <label>Тип
          <select data-field="artifact_family" ${disabled}>
            ${option("analysis", proposal.artifact_family)}
            ${option("document", proposal.artifact_family)}
            ${option("configuration", proposal.artifact_family)}
            ${option("design", proposal.artifact_family)}
            ${option("production", proposal.artifact_family)}
            ${option("practice", proposal.artifact_family)}
          </select>
        </label>
        <label>Область<input data-field="scope_names" value="${escapeAttr((proposal.scope_names || []).join(", "))}" ${disabled} /></label>
      </div>
      <label>Описание<textarea data-field="artifact_description" rows="3" ${disabled}>${escapeHtml(proposal.artifact_description)}</textarea></label>
      <label>Материалы<textarea data-field="materials_pattern" rows="3" ${disabled}>${escapeHtml(proposal.materials_pattern)}</textarea></label>
      <label>Критерии<textarea data-field="validation_criteria" rows="3" ${disabled}>${escapeHtml(proposal.validation_criteria)}</textarea></label>
      <p class="empty-inline">${escapeHtml(proposal.rationale || "")}</p>
      <div class="inline-actions">
        <button type="button" data-action="save" ${disabled}>Сохранить</button>
        <button type="button" data-action="accept" ${disabled}>Принять</button>
        <button type="button" data-action="reject" ${disabled}>Отклонить</button>
      </div>
    </article>
  `;
}

function option(value, selected) {
  return `<option value="${value}" ${value === selected ? "selected" : ""}>${value}</option>`;
}

function metricCard(label, value) {
  return `<span><strong>${escapeHtml(String(value))}</strong> ${escapeHtml(label)}</span>`;
}

function proposalPatch(card) {
  return {
    title: fieldValue(card, "title"),
    artifact_family: fieldValue(card, "artifact_family"),
    scope_names: splitComma(fieldValue(card, "scope_names")),
    artifact_description: fieldValue(card, "artifact_description"),
    materials_pattern: fieldValue(card, "materials_pattern"),
    validation_criteria: fieldValue(card, "validation_criteria"),
  };
}

function fieldValue(card, field) {
  return card.querySelector(`[data-field="${field}"]`)?.value?.trim() || "";
}

async function refreshTemplateProposals() {
  const planId = Number(el.planSelect.value);
  state.templateProposals = planId ? await request(`/curriculum/plans/${planId}/template-proposals`) : [];
  renderTemplateProposals();
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
}

function escapeAttr(value) {
  return escapeHtml(value).replace(/`/g, "&#96;");
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

el.regenerateTemplateProposals.addEventListener("click", async () => {
  const planId = Number(el.planSelect.value);
  if (!planId) return;
  state.templateProposals = await request(`/curriculum/plans/${planId}/template-proposals/generate`, { method: "POST" });
  renderTemplateProposals();
  setStatus("Предложения шаблонов обновлены");
});

el.templateProposalList.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const card = button.closest("[data-proposal-id]");
  const proposalId = Number(card?.dataset.proposalId);
  if (!proposalId) return;
  const action = button.dataset.action;
  if (action === "save") {
    await request(`/curriculum/template-proposals/${proposalId}`, {
      method: "PATCH",
      body: JSON.stringify(proposalPatch(card)),
    });
  } else {
    await request(`/curriculum/template-proposals/${proposalId}/${action}`, { method: "POST" });
  }
  await refreshTemplateProposals();
  setStatus("Предложение шаблона обновлено");
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

el.upProjectsTable.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-edit-project]");
  if (!button) return;
  const projectId = Number(button.dataset.editProject);
  if (projectId) editProjectById(projectId).catch((error) => setStatus(error.message));
});

loadPlans(planIdFromLocation()).catch((error) => setStatus(error.message));
