const PAGE_SIZE = 10;
type Key = "query" | "clicks" | "impressions" | "ctr" | "position";
function setup(root: HTMLElement) {
  const body = root.querySelector<HTMLElement>("[data-query-rows]");
  if (!body) return;
  const rows = [...body.querySelectorAll<HTMLTableRowElement>("tr")];
  let key: Key = "clicks";
  let direction: "ascending" | "descending" = "descending";
  let page = 0;
  let term = "";
  const value = (row: HTMLElement, by: Key): number | string => {
    if (by === "query") return row.dataset.query ?? "";
    const number = parseFloat(row.dataset[by] ?? "");
    // A query with no figure sorts last in either direction's reading of "none".
    return Number.isNaN(number) ? -1 : number;
  };
  const render = () => {
    const sign = direction === "ascending" ? 1 : -1;
    const matching = rows
      .filter((row) => (row.dataset.query ?? "").includes(term))
      .sort((a, b) => {
        const x = value(a, key);
        const y = value(b, key);
        return (
          sign *
          (typeof x === "string"
            ? x.localeCompare(String(y))
            : x - (y as number))
        );
      });
    const pages = Math.max(1, Math.ceil(matching.length / PAGE_SIZE));
    page = Math.min(page, pages - 1);
    rows.forEach((row) => (row.hidden = true));
    matching.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE).forEach((row) => {
      row.hidden = false;
      body.append(row);
    });
    const first = matching.length ? page * PAGE_SIZE + 1 : 0;
    const last = Math.min(matching.length, (page + 1) * PAGE_SIZE);
    const count = root.querySelector<HTMLElement>("[data-query-count]");
    if (count)
      count.textContent = `${first}–${last} of ${matching.length} queries`;
    root.querySelector<HTMLButtonElement>("[data-query-prev]")!.disabled =
      page === 0;
    root.querySelector<HTMLButtonElement>("[data-query-next]")!.disabled =
      page >= pages - 1;
    root.querySelector<HTMLElement>("[data-query-none]")!.hidden =
      matching.length > 0;
    root
      .querySelectorAll<HTMLElement>("[data-sort-header]")
      .forEach((header) =>
        header.setAttribute(
          "aria-sort",
          header.dataset.sortHeader === key ? direction : "none",
        ),
      );
  };
  root.querySelectorAll<HTMLElement>("[data-sort]").forEach((button) =>
    button.addEventListener("click", () => {
      const next = button.dataset.sort as Key;
      direction =
        next === key && direction === "descending" ? "ascending" : "descending";
      // Position is best when low, so its first sort puts the best first.
      if (next !== key && next === "position") direction = "ascending";
      if (next !== key && next === "query") direction = "ascending";
      key = next;
      page = 0;
      render();
    }),
  );
  root
    .querySelector<HTMLInputElement>("[data-query-search]")
    ?.addEventListener("input", (event) => {
      term = (event.target as HTMLInputElement).value.trim().toLowerCase();
      page = 0;
      render();
    });
  root.querySelector("[data-query-prev]")?.addEventListener("click", () => {
    page -= 1;
    render();
  });
  root.querySelector("[data-query-next]")?.addEventListener("click", () => {
    page += 1;
    render();
  });
  render();
}
document
  .querySelectorAll<HTMLElement>('[data-query-table="interactive"]')
  .forEach(setup);
