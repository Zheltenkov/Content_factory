const form = document.getElementById("generatorForm");
const planSelect = document.getElementById("planSelect");
const projectOrder = document.getElementById("projectOrder");
const statusLine = document.getElementById("generatorStatus");
const output = document.getElementById("generatorOutput");

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
  const plans = await request("/curriculum/plans");
  planSelect.innerHTML = plans
    .map((plan) => `<option value="${plan.plan_id}">${escapeHtml(plan.direction || "Без направления")} · ${escapeHtml(plan.title)}</option>`)
    .join("");
  statusLine.textContent = plans.length ? `${plans.length} планов доступно` : "Нет учебных планов";
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  output.textContent = "";
  statusLine.textContent = "Генерация...";
  const payload = {
    plan_id: Number(planSelect.value),
    project_order: Number(projectOrder.value || 1),
  };
  const result = await request("/generator/runs/from-curriculum", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  output.textContent = result.document?.markdown || "";
  statusLine.textContent = result.gate_review?.human_review_required ? "Нужна проверка методолога" : "Готово";
});

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
}

loadPlans().catch((error) => {
  statusLine.textContent = error.message;
});
