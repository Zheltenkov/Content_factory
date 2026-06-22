const statusBox = document.getElementById("translatorStatus");
const resultBox = document.getElementById("translatorResult");
const originalBox = document.getElementById("translatorOriginal");
const downloadsBox = document.getElementById("translatorDownloads");
const progressBar = document.getElementById("translatorProgress");
const metricsBox = document.getElementById("translatorMetrics");
const jobPayload = document.getElementById("translatorJobPayload");

const DOWNLOAD_ORDER = ["video", "srt", "vtt", "ass", "transcript"];

function setStatus(text, kind = "") {
  statusBox.textContent = text;
  statusBox.classList.toggle("error-msg", kind === "error");
  statusBox.classList.toggle("success-msg", kind === "success");
  statusBox.classList.toggle("status-line", kind === "warning");
}

async function pollJob(requestId) {
  const response = await fetch(`/translator/translate/status/${requestId}`);
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

document.getElementById("translatorDocumentForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  resetResult("document");
  setStatus("Перевод документа выполняется...");
  setProgress(35);
  const file = document.getElementById("translatorDocumentFile").files[0];
  const targetLanguage = document.getElementById("translatorLanguage").value;
  const translationMode = document.getElementById("translatorMode").value;
  const provider = document.getElementById("translatorProvider").value.trim();
  let startResponse;
  if (file) {
    const body = new FormData();
    body.append("file", file);
    body.append("target_language", targetLanguage);
    body.append("translation_mode", translationMode);
    if (provider) body.append("llm_provider", provider);
    startResponse = await fetch("/translator/translate/document", { method: "POST", body });
    await renderMarkdownPreview(originalBox, `Файл: ${file.name}`, "Файл не выбран.");
  } else {
    const markdown = document.getElementById("translatorMarkdown").value.trim();
    await renderMarkdownPreview(originalBox, markdown, "Исходный документ пуст.");
    startResponse = await fetch("/translator/translate/readme", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ markdown, target_language: targetLanguage, translation_mode: translationMode, llm_provider: provider || null }),
    });
  }
  await renderStartedJob(startResponse, false);
});

document.getElementById("translatorVideoForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  resetResult("video");
  setProgress(25);
  const file = document.getElementById("translatorVideoFile").files[0];
  const transcript = document.getElementById("translatorTranscript").value.trim();
  if (!file && !transcript) {
    setStatus("Добавьте файл субтитров или transcript.", "error");
    setProgress(0);
    return;
  }
  const body = new FormData();
  body.append("file", file || new Blob([transcript], { type: "text/plain" }), file ? file.name : "transcript.txt");
  body.append("target_language", document.getElementById("translatorVideoLanguage").value);
  body.append("output_mode", document.getElementById("translatorOutputMode").value);
  body.append("subtitle_style", document.getElementById("translatorSubtitleStyle").value);
  const provider = document.getElementById("translatorVideoProvider").value.trim();
  if (provider) body.append("llm_provider", provider);
  if (transcript) body.append("transcript_text", transcript);
  const startResponse = await fetch("/translator/translate/video", { method: "POST", body });
  await renderStartedJob(startResponse, true);
});

async function renderStartedJob(startResponse, isVideo) {
  if (!startResponse.ok) {
    setStatus(await startResponse.text(), "error");
    setProgress(0);
    return;
  }
  const started = await startResponse.json();
  const job = await pollJob(started.request_id);
  renderJob(job);
  if (job.status === "failed") {
    setStatus(job.error || "Ошибка перевода", "error");
    setProgress(job.progress || 0);
    return;
  }
  setProgress(job.progress || 100);
  setStatus(isVideo ? "Видео / субтитры готовы" : "Документ готов", "success");
  if (isVideo) {
    await renderMarkdownPreview(originalBox, transcriptToMarkdown(job.original_transcript), "Транскрипт не вернулся.");
    await renderMarkdownPreview(resultBox, job.translated_subtitles || "", "Субтитры не вернулись.");
    renderDownloads(started.request_id, job.result_links || {});
    if (job.error_code === "video_burn_deferred") appendDeferredVideoNotice();
  } else {
    await renderMarkdownPreview(originalBox, job.original_markdown || "", "Исходный документ не вернулся.");
    await renderMarkdownPreview(resultBox, job.translated_markdown || "", "Перевод не вернулся.");
  }
  activateTab("translatorResultTab");
}

function renderDownloads(requestId, links) {
  downloadsBox.innerHTML = "";
  const orderedTypes = DOWNLOAD_ORDER.filter((type) => links[type]).concat(Object.keys(links).filter((type) => !DOWNLOAD_ORDER.includes(type)));
  if (!orderedTypes.length) {
    downloadsBox.innerHTML = '<div class="empty-inline">Файлы для скачивания появятся после video/subtitle job.</div>';
    return;
  }
  for (const type of orderedTypes) {
    const link = document.createElement("a");
    link.href = `/translator/translate/download/${requestId}?type=${encodeURIComponent(type)}`;
    link.textContent = `${type.toUpperCase()} · ${links[type]}`;
    link.className = "list-item";
    downloadsBox.appendChild(link);
  }
}

function renderJob(job) {
  jobPayload.textContent = JSON.stringify(job, null, 2);
  metricsBox.innerHTML = [
    metricCard("Request", job.request_id?.slice(0, 8) || "n/a"),
    metricCard("Type", job.job_type || "document"),
    metricCard("Status", job.status || "n/a"),
    metricCard("Phase", job.phase || "n/a"),
    metricCard("Language", job.target_language || "n/a"),
    metricCard("Source", job.source_format || "text"),
  ].join("");
}

function resetResult(kind) {
  resultBox.innerHTML = "";
  jobPayload.textContent = "";
  metricsBox.innerHTML = "";
  downloadsBox.innerHTML = kind === "video"
    ? '<div class="empty-inline">Ожидает video/subtitle job.</div>'
    : '<div class="empty-inline">Для документов отдельные файлы не создаются; результат доступен во вкладке Перевод.</div>';
}

function setProgress(value) {
  progressBar.style.setProperty("--progress", `${Math.max(0, Math.min(100, Number(value) || 0))}%`);
}

function metricCard(label, value) {
  return `<div class="metric-card"><strong>${escapeHtml(value)}</strong><span>${escapeHtml(label)}</span></div>`;
}

function activateTab(targetId) {
  document.querySelector(`[data-tab-target="${targetId}"]`)?.click();
}

function appendDeferredVideoNotice() {
  const notice = document.createElement("div");
  notice.className = "empty-inline";
  notice.textContent = "Burned video adapter отложен backend-ом: доступны subtitle artifacts.";
  downloadsBox.prepend(notice);
}

function transcriptToMarkdown(payload) {
  if (!payload) return "";
  try {
    const segments = JSON.parse(payload);
    if (Array.isArray(segments)) {
      return segments.map((segment) => `- ${segment.start ?? 0}s → ${segment.end ?? 0}s: ${segment.text || ""}`).join("\n");
    }
  } catch (_error) {
    return String(payload);
  }
  return String(payload);
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

setProgress(0);
