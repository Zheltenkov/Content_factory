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

  function bindDashboardTiles(root = document) {
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

  document.addEventListener("DOMContentLoaded", () => {
    bindDashboardTiles(document);
    bindTabs(document);
  });

  window.ContentFactoryShell = {
    bindDashboardTiles,
    bindTabs,
    navigateToPanel,
    panelUrl,
    safePanelPath,
  };
})(window);
