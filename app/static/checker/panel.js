const form = document.getElementById("checkerForm");
const markdownInput = document.getElementById("markdownInput");
const statusLine = document.getElementById("checkerStatus");
const summary = document.getElementById("checkerSummary");
const output = document.getElementById("checkerOutput");
const preview = document.getElementById("checkerPreview");

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  statusLine.textContent = "Проверка...";
  output.textContent = "";
  await renderMarkdownPreview(preview, markdownInput.value, "README пуст.");
  const response = await fetch("/checker/evaluate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ markdown: markdownInput.value }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    statusLine.textContent = body.detail || `HTTP ${response.status}`;
    return;
  }
  const result = await response.json();
  const issues = result.rubric_json?.issues || [];
  summary.innerHTML = `
    <span>${result.passed ? "passed" : "needs review"}</span>
    <span>${issues.length} issues</span>
    <span>${result.gate_review?.human_review_required ? "human review" : "auto"}</span>
  `;
  output.textContent = JSON.stringify(issues, null, 2);
  statusLine.textContent = "Готово";
});

async function renderMarkdownPreview(target, markdown, emptyMessage) {
  if (!target) return;
  if (window.ContentFactoryMarkdown) {
    await window.ContentFactoryMarkdown.renderMarkdown(target, markdown, { emptyMessage });
    return;
  }
  target.textContent = markdown || emptyMessage || "";
}
