(function (window) {
  "use strict";

  const SAFE_PROTOCOLS = new Set(["http:", "https:", "mailto:"]);
  const MERMAID_SELECTOR = ".mermaid";
  const MERMAID_CDN_URL = "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js";
  let mermaidLoadPromise = null;

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (char) => {
      return {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      }[char];
    });
  }

  function escapeAttribute(value) {
    return escapeHtml(value).replace(/`/g, "&#96;");
  }

  function isSafeUrl(url) {
    const value = String(url ?? "").trim();
    if (!value || /[\u0000-\u001F\u007F]/.test(value)) return false;
    if (value.startsWith("#") || value.startsWith("/")) return true;
    try {
      const base = window.location?.href || "http://localhost/";
      return SAFE_PROTOCOLS.has(new URL(value, base).protocol);
    } catch (_err) {
      return false;
    }
  }

  function renderInlineSegment(text) {
    let html = escapeHtml(text);
    html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
    html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    html = html.replace(/\*([^*]+)\*/g, "<em>$1</em>");
    return html;
  }

  function renderInline(text) {
    const source = String(text ?? "");
    const linkPattern = /\[([^\]]+)\]\(([^)\s]+)\)/g;
    let cursor = 0;
    let html = "";
    let match;

    while ((match = linkPattern.exec(source)) !== null) {
      html += renderInlineSegment(source.slice(cursor, match.index));
      const label = match[1];
      const href = match[2];
      if (isSafeUrl(href)) {
        html += `<a href="${escapeAttribute(href)}" rel="noreferrer">${renderInlineSegment(label)}</a>`;
      } else {
        html += renderInlineSegment(match[0]);
      }
      cursor = match.index + match[0].length;
    }

    html += renderInlineSegment(source.slice(cursor));
    return html;
  }

  function normalizeMarkdown(markdown) {
    return String(markdown ?? "")
      .replace(/\r\n?/g, "\n")
      .replace(/FORMULA_(?:BLOCK|INLINE)_\d+/g, "")
      .trim();
  }

  function isFenceStart(line) {
    return /^```/.test(line.trim());
  }

  function fenceLanguage(line) {
    return line.trim().replace(/^```/, "").trim().toLowerCase();
  }

  function isTableSeparator(line) {
    return /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(line);
  }

  function splitTableRow(line) {
    return line
      .trim()
      .replace(/^\|/, "")
      .replace(/\|$/, "")
      .split("|")
      .map((cell) => cell.trim());
  }

  function renderTable(lines, index) {
    const header = splitTableRow(lines[index]);
    let cursor = index + 2;
    const rows = [];

    while (cursor < lines.length && /\|/.test(lines[cursor]) && lines[cursor].trim()) {
      rows.push(splitTableRow(lines[cursor]));
      cursor += 1;
    }

    const headHtml = header.map((cell) => `<th>${renderInline(cell)}</th>`).join("");
    const bodyHtml = rows
      .map((row) => `<tr>${row.map((cell) => `<td>${renderInline(cell)}</td>`).join("")}</tr>`)
      .join("");
    return {
      html: `<div class="table-wrapper"><table><thead><tr>${headHtml}</tr></thead><tbody>${bodyHtml}</tbody></table></div>`,
      nextIndex: cursor,
    };
  }

  function renderList(lines, index, ordered) {
    const pattern = ordered ? /^\s*\d+\.\s+(.+)$/ : /^\s*[-*]\s+(.+)$/;
    const tag = ordered ? "ol" : "ul";
    let cursor = index;
    const items = [];

    while (cursor < lines.length) {
      const match = lines[cursor].match(pattern);
      if (!match) break;
      items.push(`<li>${renderInline(match[1])}</li>`);
      cursor += 1;
    }

    return { html: `<${tag}>${items.join("")}</${tag}>`, nextIndex: cursor };
  }

  function renderCodeBlock(language, code) {
    const normalizedLanguage = String(language || "").toLowerCase();
    if (normalizedLanguage === "mermaid") {
      return [
        '<figure class="diagram-figure">',
        `<div class="mermaid" data-mermaid-source="${escapeAttribute(code)}">${escapeHtml(code)}</div>`,
        "</figure>",
      ].join("");
    }
    const className = normalizedLanguage ? ` class="language-${escapeAttribute(normalizedLanguage)}"` : "";
    return `<pre><code${className}>${escapeHtml(code)}</code></pre>`;
  }

  function renderParagraph(lines, index) {
    const parts = [];
    let cursor = index;

    while (cursor < lines.length) {
      const line = lines[cursor];
      const next = lines[cursor + 1] || "";
      if (!line.trim()) break;
      if (/^#{1,6}\s+/.test(line) || isFenceStart(line)) break;
      if (/^\s*[-*]\s+/.test(line) || /^\s*\d+\.\s+/.test(line)) break;
      if (/\|/.test(line) && isTableSeparator(next)) break;
      parts.push(line.trim());
      cursor += 1;
    }

    return { html: `<p>${renderInline(parts.join(" "))}</p>`, nextIndex: cursor };
  }

  function renderBlocks(markdown) {
    const lines = normalizeMarkdown(markdown).split("\n");
    const blocks = [];
    let index = 0;

    while (index < lines.length) {
      const line = lines[index];
      const trimmed = line.trim();

      if (!trimmed) {
        index += 1;
        continue;
      }

      if (isFenceStart(line)) {
        const language = fenceLanguage(line);
        const codeLines = [];
        index += 1;
        while (index < lines.length && !isFenceStart(lines[index])) {
          codeLines.push(lines[index]);
          index += 1;
        }
        if (index < lines.length) index += 1;
        blocks.push(renderCodeBlock(language, codeLines.join("\n").trim()));
        continue;
      }

      const heading = line.match(/^(#{1,6})\s+(.+)$/);
      if (heading) {
        const level = Math.min(heading[1].length, 4);
        blocks.push(`<h${level}>${renderInline(heading[2])}</h${level}>`);
        index += 1;
        continue;
      }

      if (/\|/.test(line) && isTableSeparator(lines[index + 1] || "")) {
        const table = renderTable(lines, index);
        blocks.push(table.html);
        index = table.nextIndex;
        continue;
      }

      if (/^\s*[-*]\s+/.test(line)) {
        const list = renderList(lines, index, false);
        blocks.push(list.html);
        index = list.nextIndex;
        continue;
      }

      if (/^\s*\d+\.\s+/.test(line)) {
        const list = renderList(lines, index, true);
        blocks.push(list.html);
        index = list.nextIndex;
        continue;
      }

      const paragraph = renderParagraph(lines, index);
      blocks.push(paragraph.html);
      index = paragraph.nextIndex;
    }

    return blocks.join("\n");
  }

  function loadScriptOnce(src) {
    if (!window.document?.createElement || !window.document?.head) return Promise.resolve(false);
    return new Promise((resolve) => {
      const script = window.document.createElement("script");
      script.src = src;
      script.async = true;
      script.onload = () => resolve(true);
      script.onerror = () => resolve(false);
      window.document.head.appendChild(script);
    });
  }

  async function ensureMermaidLoaded() {
    if (window.mermaid) return true;
    if (!mermaidLoadPromise) mermaidLoadPromise = loadScriptOnce(MERMAID_CDN_URL);
    return mermaidLoadPromise;
  }

  async function initializeMermaid(root) {
    const nodes = Array.from(root?.querySelectorAll?.(MERMAID_SELECTOR) || []);
    if (!nodes.length) return;

    if (!window.mermaid) {
      const loaded = await ensureMermaidLoaded();
      if (loaded && window.mermaid) {
        await initializeMermaid(root);
        return;
      }
      nodes.forEach((node) => {
        node.dataset.mermaidPending = "true";
      });
      return;
    }

    try {
      if (!window.__contentFactoryMermaidInitialized && typeof window.mermaid.initialize === "function") {
        window.mermaid.initialize({ startOnLoad: false, securityLevel: "strict" });
        window.__contentFactoryMermaidInitialized = true;
      }
      if (typeof window.mermaid.run === "function") {
        await window.mermaid.run({ nodes });
      }
    } catch (error) {
      nodes.forEach((node) => {
        node.dataset.mermaidError = error?.message || "render_failed";
      });
    }
  }

  async function renderMarkdown(container, markdown, options = {}) {
    if (!container) return;
    const emptyMessage = options.emptyMessage || "Контент отсутствует";
    const normalized = normalizeMarkdown(markdown);
    container.innerHTML = normalized ? renderBlocks(normalized) : `<div class="empty-inline">${escapeHtml(emptyMessage)}</div>`;
    await initializeMermaid(container);
  }

  window.ContentFactoryMarkdown = {
    escapeHtml,
    initializeMermaid,
    renderMarkdown,
    renderBlocks,
  };
})(window);
