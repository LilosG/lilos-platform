export {};
type Filter = "all" | "indexable" | "issues" | "not_indexable" | "unchecked";
type Sort = "attention" | "name" | "recent";
const root = document.querySelector<HTMLElement>('[data-page-table="full"]');
const body = root?.querySelector<HTMLElement>("[data-page-rows]");
if (root && body) {
  const rows = [
    ...body.querySelectorAll<HTMLTableRowElement>("[data-page-row]"),
  ];
  const state: { term: string; filter: Filter; sort: Sort } = {
    term: "",
    filter: "all",
    sort: "attention",
  };
  const keep: Record<Filter, (row: HTMLElement) => boolean> = {
    all: () => true,
    indexable: (row) => row.dataset.index === "indexable",
    issues: (row) => row.dataset.issues === "true",
    not_indexable: (row) => row.dataset.index === "not_indexable",
    unchecked: (row) => row.dataset.checked === "false",
  };
  const number = (row: HTMLElement, key: string) =>
    Number(row.dataset[key] ?? 0);
  const order: Record<Sort, (a: HTMLElement, b: HTMLElement) => number> = {
    attention: (a, b) => number(b, "attention") - number(a, "attention"),
    name: (a, b) => (a.dataset.name ?? "").localeCompare(b.dataset.name ?? ""),
    recent: (a, b) => number(b, "observed") - number(a, "observed"),
  };
  const render = () => {
    const term = state.term.trim().toLowerCase();
    const matching = rows
      .filter(
        (row) =>
          (row.dataset.search ?? "").includes(term) && keep[state.filter](row),
      )
      .sort(order[state.sort]);
    rows.forEach((row) => (row.hidden = true));
    matching.forEach((row) => {
      row.hidden = false;
      body.append(row);
    });
    const empty = body.querySelector<HTMLElement>("[data-page-empty]");
    if (empty) empty.hidden = matching.length > 0;
    const count = root.querySelector<HTMLElement>("[data-page-count]");
    if (count) count.textContent = `${matching.length} of ${rows.length} pages`;
  };
  root
    .querySelector<HTMLInputElement>("[data-page-search]")
    ?.addEventListener("input", (event) => {
      state.term = (event.target as HTMLInputElement).value;
      render();
    });
  root
    .querySelector<HTMLSelectElement>("[data-page-sort]")
    ?.addEventListener("change", (event) => {
      state.sort = (event.target as HTMLSelectElement).value as Sort;
      render();
    });
  root
    .querySelectorAll<HTMLButtonElement>("button[data-page-filter]")
    .forEach((chip) =>
      chip.addEventListener("click", () => {
        state.filter = chip.dataset.pageFilter as Filter;
        root
          .querySelectorAll<HTMLElement>("button[data-page-filter]")
          .forEach((other) => other.classList.toggle("active", other === chip));
        render();
      }),
    );
}
