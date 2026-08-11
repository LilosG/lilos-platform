/**
 * Wires one tablist to its sibling panels with complete keyboard semantics.
 * Pages provide stable `data-tab` values and `tab-{value}` panel IDs; this
 * helper owns aria-controls, tabindex, selection, focus, and arrow-key use.
 */
export function setupTabs(tablist: HTMLElement): void {
  const tabs = Array.from(
    tablist.querySelectorAll<HTMLButtonElement>('[role="tab"][data-tab]'),
  );

  function activate(tab: HTMLButtonElement, moveFocus: boolean): void {
    for (const candidate of tabs) {
      const selected = candidate === tab;
      candidate.setAttribute("aria-selected", String(selected));
      candidate.tabIndex = selected ? 0 : -1;
      const panelId = candidate.getAttribute("aria-controls");
      const panel = panelId ? document.getElementById(panelId) : null;
      if (panel) panel.hidden = !selected;
    }
    if (moveFocus) tab.focus();
  }

  tabs.forEach((tab, index) => {
    const key = tab.dataset.tab;
    if (!key) return;
    const panelId = `tab-${key}`;
    const tabId = `${tablist.id || "tabs"}-${key}`;
    tab.id = tabId;
    tab.setAttribute("aria-controls", panelId);
    tab.tabIndex = tab.getAttribute("aria-selected") === "true" ? 0 : -1;
    const panel = document.getElementById(panelId);
    if (panel) {
      panel.setAttribute("role", "tabpanel");
      panel.setAttribute("aria-labelledby", tabId);
      panel.tabIndex = 0;
    }

    tab.addEventListener("click", () => activate(tab, false));
    tab.addEventListener("keydown", (event) => {
      let targetIndex: number | null = null;
      if (event.key === "ArrowRight" || event.key === "ArrowDown") {
        targetIndex = (index + 1) % tabs.length;
      } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
        targetIndex = (index - 1 + tabs.length) % tabs.length;
      } else if (event.key === "Home") {
        targetIndex = 0;
      } else if (event.key === "End") {
        targetIndex = tabs.length - 1;
      }
      if (targetIndex !== null) {
        event.preventDefault();
        activate(tabs[targetIndex], true);
      }
    });
  });
}
