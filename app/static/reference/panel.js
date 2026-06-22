const state = {
  competencies: [],
  profiles: [],
  skills: [],
  reviews: [],
  current: null,
  currentProfile: null,
  selectedSkill: null,
  mode: "competencies",
};

const el = {
  searchInput: document.getElementById("searchInput"),
  searchButton: document.getElementById("searchButton"),
  reviewStatusFilter: document.getElementById("reviewStatusFilter"),
  includeServiceProfiles: document.getElementById("includeServiceProfiles"),
  summaryCards: document.getElementById("summaryCards"),
  competencyList: document.getElementById("competencyList"),
  profileList: document.getElementById("profileList"),
  skillList: document.getElementById("skillList"),
  reviewList: document.getElementById("reviewList"),
  form: document.getElementById("competencyForm"),
  title: document.getElementById("competencyTitle"),
  status: document.getElementById("competencyStatus"),
  description: document.getElementById("competencyDescription"),
  detailMeta: document.getElementById("detailMeta"),
  skillTree: document.getElementById("skillTree"),
  competencySection: document.getElementById("competencyDetailSection"),
  skillSection: document.getElementById("skillDetailSection"),
  profileSection: document.getElementById("profileDetailSection"),
  profileDetail: document.getElementById("profileDetail"),
  skillForm: document.getElementById("skillForm"),
  skillName: document.getElementById("skillCanonicalName"),
  skillStatus: document.getElementById("skillStatus"),
  skillType: document.getElementById("skillType"),
  skillAliases: document.getElementById("skillAliases"),
  newSkillButton: document.getElementById("newSkillButton"),
  statusLine: document.getElementById("referenceStatus"),
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
  return response.status === 204 ? null : response.json();
}

async function loadAll() {
  const q = el.searchInput.value.trim();
  const includeService = el.includeServiceProfiles.checked ? "true" : "false";
  const reviewStatus = el.reviewStatusFilter.value;
  const [summary, competencies, profiles, skills, reviews] = await Promise.all([
    request("/reference/summary"),
    request(`/reference/competencies?limit=80&q=${encodeURIComponent(q)}`),
    request(`/reference/profiles?limit=80&include_service=${includeService}`),
    request(`/reference/skills?limit=80&include_deprecated=true&q=${encodeURIComponent(q)}`),
    request(`/reference/reviews?status_filter=${encodeURIComponent(reviewStatus)}&limit=20`),
  ]);
  state.competencies = competencies;
  state.profiles = profiles;
  state.skills = skills;
  state.reviews = reviews;
  renderSummary(summary);
  renderCompetencies();
  renderProfiles();
  renderSkills();
  renderReviews();
  setListMode(state.mode);
  if (!state.current && competencies.length) await selectCompetency(competencies[0].id);
  if (!competencies.length) renderEmptyDetail("Компетенции не найдены");
}

function renderSummary(summary) {
  const labels = [
    ["competencies", "компетенции"],
    ["skills", "skills"],
    ["indicators", "индикаторы"],
    ["open_reviews", "review"],
  ];
  el.summaryCards.innerHTML = labels
    .map(([key, label]) => `<div class="summary-card"><strong>${summary[key] || 0}</strong><span>${label}</span></div>`)
    .join("");
}

function renderCompetencies() {
  el.competencyList.innerHTML = state.competencies
    .map(
      (item) => `
        <button class="list-item" type="button" data-competency-id="${item.id}">
          <strong>${escapeHtml(item.title)}</strong>
          <span>${item.profile_count} профилей · ${item.skill_count} skills · ${item.indicator_count} инд.</span>
        </button>`,
    )
    .join("") || '<div class="empty-inline">Компетенции не найдены</div>';
}

function renderProfiles() {
  el.profileList.innerHTML = state.profiles
    .map(
      (profile) => `
        <button class="list-item" type="button" data-profile-id="${profile.id}">
          <strong>${escapeHtml(profile.name)}</strong>
          <span>${escapeHtml(profile.source_kind)} · ${profile.competency_count} компетенций · ${profile.skill_count} skills</span>
          ${profile.review_competencies ? `<span class="badge warning">${profile.review_competencies} review</span>` : ""}
        </button>`,
    )
    .join("") || '<div class="empty-inline">Профили не найдены</div>';
}

function renderSkills() {
  el.skillList.innerHTML = state.skills
    .map(
      (skill) => `
        <button class="list-item" type="button" data-skill-id="${skill.skill_id}">
          <strong>${escapeHtml(skill.canonical_name)}</strong>
          <span>${escapeHtml(skill.skill_type)} · ${escapeHtml(skill.status)} · ${skill.aliases.length} aliases</span>
        </button>`,
    )
    .join("") || '<div class="empty-inline">Skills не найдены</div>';
}

function renderReviews() {
  el.reviewList.innerHTML =
    state.reviews
      .map(
        (item) => `
          <article class="review-item" data-review-card="${item.id}">
            <strong>${escapeHtml(item.entity_type)} #${item.entity_id || "-"}</strong>
            <span>${escapeHtml(item.reason_code)} · ${escapeHtml(item.severity)} · ${escapeHtml(item.status)}</span>
            <p class="small">${escapeHtml(item.details || "")}</p>
            <textarea data-review-note rows="2" placeholder="Комментарий решения"></textarea>
            <div class="inline-actions">
              <button type="button" data-review-id="${item.id}" data-review-status="resolved">Resolved</button>
              <button class="btn-ghost" type="button" data-review-id="${item.id}" data-review-status="ignored">Ignored</button>
            </div>
          </article>`,
      )
      .join("") || '<div class="empty-inline">Записей нет</div>';
}

async function selectCompetency(id) {
  state.current = await request(`/reference/competencies/${id}`);
  showDetailSection("competency");
  el.title.value = state.current.title || "";
  el.status.value = state.current.status || "candidate";
  el.description.value = state.current.description || "";
  el.detailMeta.innerHTML = `
    <span>${state.current.profile_count} профилей</span>
    <span>${state.current.skill_count} skills</span>
    <span>${state.current.indicator_count} индикаторов</span>
  `;
  renderSkillTree();
  setStatus(`Открыто: ${state.current.title}`);
}

async function selectProfile(id) {
  state.currentProfile = await request(`/reference/profiles/${id}`);
  showDetailSection("profile");
  el.profileDetail.innerHTML = `
    <div class="metrics">
      <span>${escapeHtml(state.currentProfile.name)}</span>
      <span>${state.currentProfile.competency_count} компетенций</span>
      <span>${state.currentProfile.indicator_count} индикаторов</span>
    </div>
    ${renderProfileTree(state.currentProfile.competencies || [])}
  `;
  setStatus(`Профиль: ${state.currentProfile.name}`);
}

function renderSkillTree() {
  el.skillTree.innerHTML =
    (state.current.skills || [])
      .map(
        (skill) => `
          <details class="tree-card" open>
            <summary>
              <strong>${escapeHtml(skill.name || "Без названия")}</strong>
              <span class="status-badge">${escapeHtml(skill.status || "unknown")}</span>
            </summary>
            <div class="card-body">
              <div class="inline-actions">
                <button class="btn" type="button" data-edit-skill="${skill.skill_id || ""}">Редактировать skill</button>
                <span class="small">${escapeHtml(skill.profile_name || "")}</span>
              </div>
              ${skill.aliases?.length ? `<p class="small"><strong>Алиасы:</strong> ${skill.aliases.map(escapeHtml).join(", ")}</p>` : ""}
              ${renderIndicators(skill.indicators || [])}
            </div>
          </details>`,
      )
      .join("") || '<div class="empty-inline">Связанные skills и индикаторы пока отсутствуют</div>';
}

function renderProfileTree(competencies) {
  return competencies
    .map(
      (competency) => `
        <details class="tree-card" open>
          <summary>
            <strong>${escapeHtml(competency.title_in_source || competency.title)}</strong>
            <span class="status-badge">${escapeHtml(competency.review_state)}</span>
          </summary>
          <div class="card-body">
            ${competency.prerequisites_text ? `<p class="small"><strong>Prerequisites:</strong> ${escapeHtml(competency.prerequisites_text)}</p>` : ""}
            ${(competency.skills || [])
              .map(
                (skill) => `
                  <details class="indicator-block">
                    <summary>
                      <strong>${escapeHtml(skill.name)}</strong>
                      <span class="pill">${escapeHtml(skill.status)}</span>
                    </summary>
                    ${skill.aliases?.length ? `<p class="small">Aliases: ${skill.aliases.map(escapeHtml).join(", ")}</p>` : ""}
                    ${renderIndicators(skill.indicators || [])}
                  </details>`,
              )
              .join("")}
          </div>
        </details>`,
    )
    .join("") || '<div class="empty-inline">Профиль пуст</div>';
}

function renderIndicators(indicators) {
  return indicators
    .map(
      (indicator) => `
        <div class="indicator-block">
          <div class="indicator-line">
            <span class="pill">${escapeHtml(indicator.dimension_title || indicator.dimension_code || "N/A")}</span>
            <span>${escapeHtml(indicator.text || "")}</span>
          </div>
          ${
            indicator.levels?.length
              ? `<div class="levels-grid">${indicator.levels
                  .map((level) => `<div class="level-cell"><span>${escapeHtml(level.label)}</span><span>${escapeHtml(level.value)}</span></div>`)
                  .join("")}</div>`
              : ""
          }
        </div>`,
    )
    .join("");
}

function selectSkillById(skillId) {
  const source = findSkill(skillId);
  if (!source || !source.skill_id) return;
  state.selectedSkill = {
    skill_id: source.skill_id,
    canonical_name: source.canonical_name || source.name,
    skill_type: source.skill_type || "unknown",
    status: source.status || "active",
    aliases: source.aliases || [],
  };
  showDetailSection("skill");
  fillSkillForm(state.selectedSkill);
  setStatus(`Skill: ${state.selectedSkill.canonical_name}`);
}

function findSkill(skillId) {
  const id = Number(skillId);
  if (!id) return null;
  return (
    state.skills.find((skill) => skill.skill_id === id)
    || (state.current?.skills || []).find((skill) => skill.skill_id === id)
    || (state.currentProfile?.competencies || []).flatMap((competency) => competency.skills || []).find((skill) => skill.skill_id === id)
  );
}

function fillSkillForm(skill) {
  el.skillName.value = skill?.canonical_name || "";
  el.skillStatus.value = skill?.status || "active";
  el.skillType.value = skill?.skill_type || "unknown";
  el.skillAliases.value = (skill?.aliases || []).join("\n");
}

function showDetailSection(kind) {
  el.competencySection.hidden = kind !== "competency";
  el.skillSection.hidden = kind !== "skill";
  el.profileSection.hidden = kind !== "profile";
}

function setListMode(mode) {
  state.mode = mode;
  for (const node of document.querySelectorAll("[data-reference-mode]")) {
    node.classList.toggle("active", node.dataset.referenceMode === mode);
  }
  el.competencyList.hidden = mode !== "competencies";
  el.profileList.hidden = mode !== "profiles";
  el.skillList.hidden = mode !== "skills";
  el.reviewList.hidden = mode !== "reviews";
}

function renderEmptyDetail(message) {
  state.current = null;
  el.form.reset();
  el.detailMeta.innerHTML = "";
  el.skillTree.innerHTML = `<div class="empty-inline">${escapeHtml(message)}</div>`;
}

function splitAliases(value) {
  return value.split(/[\n;]+/).map((item) => item.trim()).filter(Boolean);
}

function setStatus(message) {
  el.statusLine.textContent = message;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
}

document.querySelector(".tab-list").addEventListener("click", (event) => {
  const item = event.target.closest("[data-reference-mode]");
  if (item) setListMode(item.dataset.referenceMode);
});
el.searchButton.addEventListener("click", () => loadAll().catch((error) => setStatus(error.message)));
el.reviewStatusFilter.addEventListener("change", () => loadAll().catch((error) => setStatus(error.message)));
el.includeServiceProfiles.addEventListener("change", () => loadAll().catch((error) => setStatus(error.message)));
el.searchInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") loadAll().catch((error) => setStatus(error.message));
});
el.competencyList.addEventListener("click", (event) => {
  const item = event.target.closest("[data-competency-id]");
  if (item) selectCompetency(Number(item.dataset.competencyId)).catch((error) => setStatus(error.message));
});
el.profileList.addEventListener("click", (event) => {
  const item = event.target.closest("[data-profile-id]");
  if (item) selectProfile(Number(item.dataset.profileId)).catch((error) => setStatus(error.message));
});
el.skillList.addEventListener("click", (event) => {
  const item = event.target.closest("[data-skill-id]");
  if (item) selectSkillById(Number(item.dataset.skillId));
});
el.skillTree.addEventListener("click", (event) => {
  const item = event.target.closest("[data-edit-skill]");
  if (item) selectSkillById(Number(item.dataset.editSkill));
});
el.reviewList.addEventListener("click", async (event) => {
  const item = event.target.closest("[data-review-id]");
  if (!item) return;
  const card = item.closest("[data-review-card]");
  const note = card?.querySelector("[data-review-note]")?.value || "";
  await request(`/reference/reviews/${item.dataset.reviewId}`, {
    method: "PATCH",
    body: JSON.stringify({ status: item.dataset.reviewStatus, note }),
  });
  await loadAll();
});
el.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.current) return;
  state.current = await request(`/reference/competencies/${state.current.id}`, {
    method: "PATCH",
    body: JSON.stringify({
      title: el.title.value.trim(),
      description: el.description.value.trim(),
      status: el.status.value,
    }),
  });
  await loadAll();
  await selectCompetency(state.current.id);
  setStatus("Компетенция сохранена");
});
el.skillForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = {
    canonical_name: el.skillName.value.trim(),
    skill_type: el.skillType.value.trim() || "unknown",
    status: el.skillStatus.value,
    aliases: splitAliases(el.skillAliases.value),
  };
  const path = state.selectedSkill?.skill_id ? `/reference/skills/${state.selectedSkill.skill_id}` : "/reference/skills";
  const method = state.selectedSkill?.skill_id ? "PATCH" : "POST";
  const saved = await request(path, { method, body: JSON.stringify(payload) });
  state.selectedSkill = saved;
  await loadAll();
  fillSkillForm(saved);
  showDetailSection("skill");
  setStatus("Skill сохранен");
});
el.newSkillButton.addEventListener("click", () => {
  state.selectedSkill = null;
  fillSkillForm(null);
  showDetailSection("skill");
  setStatus("Новый skill");
});

loadAll().catch((error) => setStatus(error.message));
