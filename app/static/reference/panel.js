const state = {
  competencies: [],
  current: null,
  reviews: [],
};

const el = {
  searchInput: document.getElementById("searchInput"),
  searchButton: document.getElementById("searchButton"),
  summaryCards: document.getElementById("summaryCards"),
  competencyList: document.getElementById("competencyList"),
  reviewList: document.getElementById("reviewList"),
  form: document.getElementById("competencyForm"),
  title: document.getElementById("competencyTitle"),
  status: document.getElementById("competencyStatus"),
  description: document.getElementById("competencyDescription"),
  detailMeta: document.getElementById("detailMeta"),
  skillTree: document.getElementById("skillTree"),
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
  const [summary, competencies, reviews] = await Promise.all([
    request("/reference/summary"),
    request(`/reference/competencies?limit=80&q=${encodeURIComponent(q)}`),
    request("/reference/reviews?status_filter=open&limit=6"),
  ]);
  state.competencies = competencies;
  state.reviews = reviews;
  renderSummary(summary);
  renderCompetencies();
  renderReviews();
  if (competencies.length) await selectCompetency(competencies[0].id);
  else renderEmptyDetail("Компетенции не найдены");
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
        <button class="list-item" type="button" data-id="${item.id}">
          <strong>${escapeHtml(item.title)}</strong>
          <span>${item.skill_count} skills · ${item.indicator_count} инд.</span>
        </button>`,
    )
    .join("");
}

function renderReviews() {
  el.reviewList.innerHTML =
    state.reviews
      .map(
        (item) => `
          <article class="review-item">
            <strong>${escapeHtml(item.entity_type)} #${item.entity_id || "-"}</strong>
            <span>${escapeHtml(item.reason_code)} · ${escapeHtml(item.severity)}</span>
            <button type="button" data-review="${item.id}">Закрыть</button>
          </article>`,
      )
      .join("") || '<div class="empty-inline">Открытых записей нет</div>';
}

async function selectCompetency(id) {
  state.current = await request(`/reference/competencies/${id}`);
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
              ${skill.aliases?.length ? `<p class="small"><strong>Алиасы:</strong> ${skill.aliases.map(escapeHtml).join(", ")}</p>` : ""}
              ${renderIndicators(skill.indicators || [])}
            </div>
          </details>`,
      )
      .join("") || '<div class="empty-inline">Связанные skills и индикаторы пока отсутствуют</div>';
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

function renderEmptyDetail(message) {
  state.current = null;
  el.form.reset();
  el.detailMeta.innerHTML = "";
  el.skillTree.innerHTML = `<div class="empty-inline">${escapeHtml(message)}</div>`;
}

function setStatus(message) {
  el.statusLine.textContent = message;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
}

el.searchButton.addEventListener("click", () => loadAll().catch((error) => setStatus(error.message)));
el.searchInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") loadAll().catch((error) => setStatus(error.message));
});
el.competencyList.addEventListener("click", (event) => {
  const item = event.target.closest("[data-id]");
  if (item) selectCompetency(Number(item.dataset.id)).catch((error) => setStatus(error.message));
});
el.reviewList.addEventListener("click", async (event) => {
  const item = event.target.closest("[data-review]");
  if (!item) return;
  await request(`/reference/reviews/${item.dataset.review}`, {
    method: "PATCH",
    body: JSON.stringify({ status: "resolved", note: "Закрыто из reference panel" }),
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
  setStatus("Сохранено");
});

loadAll().catch((error) => setStatus(error.message));
