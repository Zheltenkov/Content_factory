const statusBox = document.getElementById("translationStatus") || document.getElementById("translatorStatus");
const resultBox = document.getElementById("translatorResult");
const originalBox = document.getElementById("translatorOriginal");
const downloadsBox = document.getElementById("translatorDownloads");
const progressBar = document.getElementById("translationProgressBar") || document.getElementById("translatorProgress");
const metricsBox = document.getElementById("translatorMetrics");
const jobPayload = document.getElementById("translatorJobPayload");
const phaseLabel = document.getElementById("translationPhaseLabel");
const progressPhase = document.getElementById("translationProgressPhase");
const videoResultPanel = document.getElementById("translationVideoResultPanel");
const videoInlineDownloads = document.getElementById("translationVideoInlineDownloadLinks");

const DOWNLOAD_ORDER = ["video", "srt", "vtt", "ass", "transcript"];
const PHASE_LABELS = {
  queued: "В очереди",
  parse_transcript: "Разбор transcript",
  translate: "Перевод",
  build_subtitles: "Формирование субтитров",
  completed: "Готово",
};

let currentRequestId = null;
let translatedMarkdown = "";

function setStatus(text, kind = "") {
  statusBox.textContent = text;
  statusBox.classList.toggle("error-msg", kind === "error");
  statusBox.classList.toggle("success-msg", kind === "success");
  statusBox.classList.toggle("status-line", kind === "warning");
  if (phaseLabel) phaseLabel.textContent = text;
  if (progressPhase) progressPhase.textContent = text;
}

async function pollJob(requestId) {
  const response = await fetch(`/translator/translate/status/${requestId}`);
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

document.getElementById("translatorDocumentForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  toggleTranslationSourceMode("document");
  resetResult("document");
  setStatus("Перевод документа выполняется...");
  setProgress(35);
  const file = document.getElementById("translationFile").files[0];
  const targetLanguage = document.getElementById("translationLanguage").value;
  const translationMode = document.getElementById("translationMode").value;
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
    const markdown = document.getElementById("translationInput").value.trim();
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
  toggleTranslationSourceMode("video");
  resetResult("video");
  resetVideoResultPanel();
  setProgress(25);
  setVideoProgress("Загрузка video/subtitle source", 15, true);
  const file = document.getElementById("translationVideoFile").files[0];
  const transcript = document.getElementById("translatorTranscript").value.trim();
  if (!file && !transcript) {
    setStatus("Добавьте файл субтитров или transcript.", "error");
    setProgress(0);
    return;
  }
  const body = new FormData();
  body.append("file", file || new Blob([transcript], { type: "text/plain" }), file ? file.name : "transcript.txt");
  body.append("target_language", document.getElementById("translationLanguageMirror").value);
  body.append("output_mode", document.getElementById("translationOutputMode").value);
  body.append("subtitle_style", document.getElementById("translatorSubtitleStyle").value);
  const provider = document.getElementById("translatorVideoProvider").value.trim();
  if (provider) body.append("llm_provider", provider);
  if (transcript) body.append("transcript_text", transcript);
  setUploadProgress(15, true);
  const startResponse = await fetch("/translator/translate/video", { method: "POST", body });
  setUploadProgress(startResponse.ok ? 100 : 0, startResponse.ok);
  await renderStartedJob(startResponse, true);
});

async function renderStartedJob(startResponse, isVideo) {
  if (!startResponse.ok) {
    setStatus(await startResponse.text(), "error");
    setProgress(0);
    return;
  }
  const started = await startResponse.json();
  currentRequestId = started.request_id;
  const job = await pollJob(started.request_id);
  renderJob(job);
  if (job.status === "failed") {
    setStatus(job.error || "Ошибка перевода", "error");
    setProgress(job.progress || 0);
    return;
  }
  setProgress(job.progress || 100);
  setVideoProgress(labelForPhase(job.phase, job.status), job.progress || 100, isVideo);
  setStatus(isVideo ? "Видео / субтитры готовы" : "Документ готов", "success");
  if (isVideo) {
    await renderMarkdownPreview(originalBox, transcriptToMarkdown(job.original_transcript), "Транскрипт не вернулся.");
    await renderMarkdownPreview(resultBox, job.translated_subtitles || "", "Субтитры не вернулись.");
    renderDownloads(started.request_id, job.result_links || {});
    renderVideoResultPanel(started.request_id, job);
    if (job.error_code === "video_burn_deferred") appendDeferredVideoNotice();
  } else {
    translatedMarkdown = job.translated_markdown || "";
    await renderMarkdownPreview(originalBox, job.original_markdown || "", "Исходный документ не вернулся.");
    await renderMarkdownPreview(resultBox, translatedMarkdown, "Перевод не вернулся.");
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

function renderVideoResultPanel(requestId, job) {
  if (!videoResultPanel || !videoInlineDownloads) return;
  videoResultPanel.hidden = false;
  const links = job.result_links || {};
  document.getElementById("translationVideoResultTitle").textContent = job.error_code === "video_burn_deferred"
    ? "Субтитры готовы, video burn отложен"
    : "Субтитры и файлы перевода готовы";
  document.getElementById("translationVideoResultHint").textContent = job.error_code === "video_burn_deferred"
    ? "Backend вернул video_burn_deferred: скачайте VTT/SRT/ASS/transcript, а burned video будет доступен после подключения burn adapter."
    : "Скачайте нужные файлы здесь. Они относятся к обработанному видео.";
  videoInlineDownloads.innerHTML = "";
  for (const type of DOWNLOAD_ORDER.filter((item) => links[item])) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = type === "video" ? "Скачать видео с переводом" : type.toUpperCase();
    button.disabled = type === "video" && job.error_code === "video_burn_deferred";
    button.addEventListener("click", () => downloadArtifact(requestId, type));
    videoInlineDownloads.appendChild(button);
  }
  if (links.srt) {
    const fallback = document.createElement("button");
    fallback.id = "downloadTranslatedSubtitlesBtn";
    fallback.type = "button";
    fallback.textContent = "Скачать субтитры";
    fallback.addEventListener("click", downloadTranslatedSubtitles);
    videoInlineDownloads.appendChild(fallback);
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
  resetVideoResultPanel();
}

function setProgress(value) {
  progressBar?.style.setProperty("--progress", `${Math.max(0, Math.min(100, Number(value) || 0))}%`);
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

function resetVideoResultPanel() {
  if (videoResultPanel) videoResultPanel.hidden = true;
  if (videoInlineDownloads) videoInlineDownloads.innerHTML = "";
}

function setVideoProgress(label, percent, visible) {
  const panel = document.getElementById("translationVideoProgress");
  const labelEl = document.getElementById("translationVideoProgressLabel");
  const pctEl = document.getElementById("translationVideoProgressPct");
  const barEl = document.getElementById("translationVideoProgressBar");
  if (!panel || !labelEl || !pctEl || !barEl) return;
  const normalized = Math.max(0, Math.min(100, Math.round(Number(percent) || 0)));
  panel.hidden = !visible;
  labelEl.textContent = label || "Выполняется";
  pctEl.textContent = `${normalized}%`;
  barEl.style.setProperty("--progress", `${normalized}%`);
}

function setUploadProgress(percent, visible) {
  const panel = document.getElementById("translationUploadProgressContainer");
  const label = document.getElementById("translationUploadProgressLabel");
  const bar = document.getElementById("translationUploadProgressBar");
  if (!panel || !label || !bar) return;
  const normalized = Math.max(0, Math.min(100, Math.round(Number(percent) || 0)));
  panel.hidden = !visible;
  label.textContent = `Загрузка видео: ${normalized}%`;
  bar.style.setProperty("--progress", `${normalized}%`);
}

function labelForPhase(phase, status) {
  if (status === "completed") return "Готово";
  return PHASE_LABELS[phase] || "Выполняется";
}

function updateTranslationOutputMode() {
  const wantVideo = document.getElementById("translationWantVideo").checked;
  const wantSubtitles = document.getElementById("translationWantSubtitles").checked;
  const output = document.getElementById("translationOutputMode");
  if (wantVideo && wantSubtitles) output.value = "both";
  else if (wantVideo) output.value = "burned_video";
  else output.value = "subtitles_only";
}

function syncTranslationLanguageFromMirror(sourceId) {
  const documentLanguage = document.getElementById("translationLanguage");
  const mirror = document.getElementById("translationLanguageMirror");
  if (sourceId === "mirror") documentLanguage.value = mirror.value;
  else mirror.value = documentLanguage.value;
}

function toggleTranslationSourceMode(mode) {
  const isVideo = mode === "video" || document.getElementById("translationSourceVideo").checked;
  document.getElementById("translationSourceDocument").checked = !isVideo;
  document.getElementById("translationSourceVideo").checked = isVideo;
  document.getElementById("translatorDocumentForm").style.display = isVideo ? "none" : "block";
  document.getElementById("translationVideoScreen").style.display = isVideo ? "block" : "none";
  document.getElementById("translationSourceDocumentLabel").classList.toggle("active", !isVideo);
  document.getElementById("translationSourceVideoLabel").classList.toggle("active", isVideo);
}

async function downloadArtifact(requestId, type) {
  if (!requestId || !type) return;
  window.location.href = `/translator/translate/download/${requestId}?type=${encodeURIComponent(type)}`;
}

async function downloadTranslatedSubtitles() {
  if (!currentRequestId) return;
  const format = document.getElementById("translationSubtitleFormat")?.value || "srt";
  if (format !== "srt") {
    await downloadArtifact(currentRequestId, format);
    return;
  }
  window.location.href = `/translator/translate/subtitles/${currentRequestId}`;
}

function copyTranslatedMarkdown() {
  const text = translatedMarkdown || resultBox.innerText || "";
  if (!text.trim()) return;
  navigator.clipboard?.writeText(text);
}

function downloadTranslatedMarkdown() {
  const blob = new Blob([translatedMarkdown || resultBox.innerText || ""], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "README_translated.md";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function showTranslationCompare() {
  document.querySelectorAll(".tab-button[data-tab-target]").forEach((button) => {
    button.classList.remove("active");
    button.setAttribute("aria-selected", "false");
  });
  document.getElementById("translatorOriginalTab").hidden = false;
  document.getElementById("translatorResultTab").hidden = false;
  document.getElementById("translatorOriginalTab").classList.add("active");
  document.getElementById("translatorResultTab").classList.add("active");
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

document.getElementById("translationSourceDocument").addEventListener("change", () => toggleTranslationSourceMode("document"));
document.getElementById("translationSourceVideo").addEventListener("change", () => toggleTranslationSourceMode("video"));
document.getElementById("translationLanguage").addEventListener("change", () => syncTranslationLanguageFromMirror("document"));
document.getElementById("translationLanguageMirror").addEventListener("change", () => syncTranslationLanguageFromMirror("mirror"));
document.getElementById("translationWantVideo").addEventListener("change", updateTranslationOutputMode);
document.getElementById("translationWantSubtitles").addEventListener("change", updateTranslationOutputMode);
document.getElementById("translationWantTranscript").addEventListener("change", updateTranslationOutputMode);
document.getElementById("translationVideoFile").addEventListener("change", (event) => {
  const file = event.target.files?.[0];
  document.getElementById("translationVideoTitle").textContent = file?.name || "Видео не выбрано";
  document.getElementById("translationVideoFileName").textContent = file ? `${Math.max(1, Math.round(file.size / 1024 / 1024))} MB · загружен` : "До 500 MB";
  setVideoProgress("Готов к обработке", 0, Boolean(file));
  setUploadProgress(0, false);
});
document.getElementById("translationFile").addEventListener("change", (event) => {
  const file = event.target.files?.[0];
  document.getElementById("translationFileName").textContent = file ? `${file.name} · ${Math.max(1, Math.round(file.size / 1024))} КБ` : "Документ для перевода";
});
document.getElementById("translationClearBtn").addEventListener("click", () => {
  document.getElementById("translationInput").value = "";
  document.getElementById("translationFile").value = "";
  document.getElementById("translationFileName").textContent = "Документ для перевода";
  resetResult("document");
  setStatus("Ожидает запуска.");
  setProgress(0);
});
document.getElementById("copyTranslatedMarkdownBtn").addEventListener("click", copyTranslatedMarkdown);
document.getElementById("downloadTranslatedMarkdownBtn").addEventListener("click", downloadTranslatedMarkdown);
document.getElementById("compareTranslationBtn").addEventListener("click", showTranslationCompare);
syncTranslationLanguageFromMirror("document");
toggleTranslationSourceMode("document");
