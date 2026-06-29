(function (window) {
  "use strict";

  const PANEL_PATH_PATTERN = /^[a-z0-9_/-]+\.html$/i;

  function safePanelPath(panel) {
    const value = String(panel ?? "").trim();
    if (!PANEL_PATH_PATTERN.test(value)) return "";
    if (value.includes("..") || value.startsWith("/") || value.includes("//")) return "";
    return value;
  }

  function panelUrl(panel) {
    const safePath = safePanelPath(panel);
    return safePath ? `/static/${safePath}` : "";
  }

  function navigateToPanel(panel, locationRef = window.location) {
    const target = panelUrl(panel);
    if (!target) return false;
    locationRef.href = target;
    return true;
  }

  function tileFromEvent(event) {
    return event.target?.closest?.(".module-tile[data-panel]") || null;
  }

  function shellRoot(root) {
    return root && typeof root.querySelectorAll === "function" ? root : document;
  }

  function bindDashboardTiles(root = document) {
    root = shellRoot(root);
    if (!root || root.__contentFactoryDashboardBound) return;
    root.__contentFactoryDashboardBound = true;

    root.querySelectorAll?.(".module-tile[data-panel]").forEach((tile) => {
      if (!tile.hasAttribute("tabindex")) tile.setAttribute("tabindex", "0");
      if (!tile.hasAttribute("role")) tile.setAttribute("role", "button");
    });

    root.addEventListener("click", (event) => {
      const tile = tileFromEvent(event);
      if (tile) navigateToPanel(tile.dataset.panel);
    });

    root.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      const tile = tileFromEvent(event);
      if (!tile) return;
      event.preventDefault();
      navigateToPanel(tile.dataset.panel);
    });
  }

  function bindTabs(root = document) {
    root = shellRoot(root);
    root.querySelectorAll?.("[data-tab-target]").forEach((tab) => {
      tab.addEventListener("click", () => {
        const targetId = tab.dataset.tabTarget;
        if (!targetId) return;
        root.querySelectorAll("[data-tab-target]").forEach((item) => {
          item.classList.remove("active");
          item.setAttribute("aria-selected", "false");
        });
        root.querySelectorAll(".tab-content").forEach((panel) => {
          panel.classList.remove("active");
          panel.hidden = true;
        });
        tab.classList.add("active");
        tab.setAttribute("aria-selected", "true");
        const panel = root.getElementById?.(targetId);
        if (panel) {
          panel.classList.add("active");
          panel.hidden = false;
        }
      });
    });
  }

  const MODULE_NAV = [
    ["", "Главная", "/app"],
    ["generator", "Генерация", "/app/generate"],
    ["checker", "Проверка", "/app/check"],
    ["translator", "Перевод", "/app/translate"],
    ["curriculum", "Учебный план", "/up"],
    ["reference", "Справочник", "/catalog-admin/groups"],
    ["instruction", "Инструкция", "/app/instruction"],
  ];

  function injectTopbar(root = document) {
    root = shellRoot(root);
    if (root.body?.classList.contains("methodologist-product")) return;
    const workbench = root.querySelector?.("main.workbench[data-module]");
    if (!workbench || root.querySelector?.(".dashboard-header--menu")) return;
    const current = workbench.dataset.module || "";
    const header = root.createElement("header");
    header.className = "hdr dashboard-header--menu";
    const nav = root.createElement("nav");
    nav.className = "hdr-nav dashboard-nav";
    nav.setAttribute("aria-label", "Основные разделы");
    MODULE_NAV.forEach(([id, label, href]) => {
      const link = root.createElement("a");
      link.href = href;
      link.textContent = label;
      if (id === current) link.className = "active";
      nav.appendChild(link);
    });
    const spacer = root.createElement("div");
    spacer.className = "hdr-spacer";
    const actions = root.createElement("div");
    actions.className = "hdr-right dashboard-header-actions";
    actions.innerHTML = '<span class="hdr-ai" aria-label="ИИ">ИИ</span><span class="hdr-user dashboard-user"><span class="av dashboard-user-avatar">VZ</span><span>Vasilii Zheltenkov</span></span>';
    header.append(nav, spacer, actions);
    workbench.before(header);
  }

  function init(root = document) {
    root = shellRoot(root);
    injectTopbar(root);
    bindDashboardTiles(root);
    bindTabs(root);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init(document);
  }

  window.ContentFactoryShell = {
    bindDashboardTiles,
    bindTabs,
    init,
    injectTopbar,
    navigateToPanel,
    panelUrl,
    safePanelPath,
  };
})(window);
