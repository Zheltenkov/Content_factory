const statusBox = document.getElementById("translatorStatus");
const resultBox = document.getElementById("translatorResult");
const originalBox = document.getElementById("translatorOriginal");
const downloadsBox = document.getElementById("translatorDownloads");

function setStatus(text, isError = false) {
  statusBox.textContent = text;
  statusBox.classList.toggle("error-msg", isError);
}

async function pollJob(requestId) {
  const response = await fetch(`/translator/translate/status/${requestId}`);
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

document.getElementById("translatorDocumentForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  setStatus("Перевод выполняется...");
  resultBox.textContent = "";
  downloadsBox.textContent = "";
  const file = document.getElementById("translatorDocumentFile").files[0];
  const targetLanguage = document.getElementById("translatorLanguage").value;
  const translationMode = document.getElementById("translatorMode").value;
  let startResponse;
  if (file) {
    const body = new FormData();
    body.append("file", file);
    body.append("target_language", targetLanguage);
    body.append("translation_mode", translationMode);
    startResponse = await fetch("/translator/translate/document", { method: "POST", body });
    originalBox.textContent = `Файл: ${file.name}`;
  } else {
    const markdown = document.getElementById("translatorMarkdown").value.trim();
    originalBox.textContent = markdown;
    startResponse = await fetch("/translator/translate/readme", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ markdown, target_language: targetLanguage, translation_mode: translationMode }),
    });
  }
  await renderStartedJob(startResponse, false);
});

document.getElementById("translatorVideoForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = document.getElementById("translatorVideoFile").files[0];
  const transcript = document.getElementById("translatorTranscript").value.trim();
  if (!file && !transcript) {
    setStatus("Добавьте файл субтитров или transcript.", true);
    return;
  }
  const body = new FormData();
  body.append("file", file || new Blob([transcript], { type: "text/plain" }), file ? file.name : "transcript.txt");
  body.append("target_language", document.getElementById("translatorVideoLanguage").value);
  body.append("output_mode", document.getElementById("translatorOutputMode").value);
  if (transcript) body.append("transcript_text", transcript);
  const startResponse = await fetch("/translator/translate/video", { method: "POST", body });
  await renderStartedJob(startResponse, true);
});

async function renderStartedJob(startResponse, isVideo) {
  if (!startResponse.ok) {
    setStatus(await startResponse.text(), true);
    return;
  }
  const started = await startResponse.json();
  const job = await pollJob(started.request_id);
  if (job.status === "failed") {
    setStatus(job.error || "Ошибка перевода", true);
    return;
  }
  setStatus("Готово");
  if (isVideo) {
    resultBox.textContent = job.translated_subtitles || "";
    renderDownloads(started.request_id, job.result_links || {});
  } else {
    resultBox.textContent = job.translated_markdown || "";
  }
}

function renderDownloads(requestId, links) {
  downloadsBox.innerHTML = "";
  for (const type of Object.keys(links)) {
    const link = document.createElement("a");
    link.href = `/translator/translate/download/${requestId}?type=${encodeURIComponent(type)}`;
    link.textContent = links[type];
    link.className = "back-link";
    downloadsBox.appendChild(link);
    downloadsBox.appendChild(document.createElement("br"));
  }
}
