import { describe, expect, it } from "vitest";
import {
  buildDataTable,
  buildGroupedDataTable,
  type TableColumn,
} from "./table";

interface Run {
  skill: string;
  status: string;
  started: string;
}

const columns: TableColumn<Run>[] = [
  { key: "skill", header: "Skill", render: (row) => row.skill },
  { key: "status", header: "Status", render: (row) => row.status },
  { key: "started", header: "Started", render: (row) => row.started },
];

function runs(count: number, skill = "gbp.operator"): Run[] {
  return Array.from({ length: count }, (_, index) => ({
    skill,
    status: "completed",
    started: `2026-08-${String((index % 27) + 1).padStart(2, "0")}`,
  }));
}

function visibleRows(frame: HTMLElement): HTMLTableRowElement[] {
  return Array.from(frame.querySelectorAll("tbody tr")).filter(
    (row) =>
      !(row as HTMLTableRowElement).hidden &&
      !row.classList.contains("ui-table__group-row") &&
      !row.classList.contains("ui-table__group-footer"),
  ) as HTMLTableRowElement[];
}

describe("bounded tables", () => {
  it("renders every row when no bound is asked for", () => {
    const frame = buildDataTable(columns, runs(40));
    expect(visibleRows(frame).length).toBe(40);
    expect(frame.querySelector(".ui-table__disclosure")).toBeNull();
  });

  it("shows a useful head and discloses the remainder by count", () => {
    const frame = buildDataTable(columns, runs(34), {
      disclosure: { initialRows: 5, noun: "runs" },
    });

    expect(visibleRows(frame).length).toBe(5);
    const toggle = frame.querySelector(
      ".ui-table__disclosure button",
    ) as HTMLButtonElement;
    expect(toggle.textContent).toBe("+ 29 more runs");
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
  });

  it("keeps disclosed rows in the document rather than truncating them", () => {
    const frame = buildDataTable(columns, runs(34), {
      disclosure: { initialRows: 5, noun: "runs" },
    });
    expect(frame.querySelectorAll("tbody tr").length).toBe(34);
  });

  it("expands and collapses, and says which it will do next", () => {
    const frame = buildDataTable(columns, runs(12), {
      disclosure: { initialRows: 4 },
    });
    const toggle = frame.querySelector(
      ".ui-table__disclosure button",
    ) as HTMLButtonElement;

    toggle.click();
    expect(visibleRows(frame).length).toBe(12);
    expect(toggle.getAttribute("aria-expanded")).toBe("true");
    expect(toggle.textContent).toBe("Show less");

    toggle.click();
    expect(visibleRows(frame).length).toBe(4);
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    expect(toggle.textContent).toBe("+ 8 more rows");
  });

  it("offers no disclosure when the rows already fit the bound", () => {
    const frame = buildDataTable(columns, runs(3), {
      disclosure: { initialRows: 5 },
    });
    expect(frame.querySelector(".ui-table__disclosure")).toBeNull();
    expect(visibleRows(frame).length).toBe(3);
  });

  it("still renders the empty state when there is nothing to bound", () => {
    const frame = buildDataTable(columns, [], {
      disclosure: { initialRows: 5 },
      emptyHeading: "No runs yet",
    });
    expect(frame.querySelector(".ui-table__state h3")?.textContent).toBe(
      "No runs yet",
    );
  });
});

describe("grouped tables", () => {
  it("groups rows under a labelled header carrying its own count", () => {
    const frame = buildGroupedDataTable(columns, [
      { key: "gbp", label: "GBP agent", rows: runs(3, "gbp.operator") },
      { key: "seo", label: "SEO agent", rows: runs(2, "seo.operator") },
    ]);

    const groups = frame.querySelectorAll("tbody[data-group]");
    expect(groups.length).toBe(2);
    expect(groups[0].querySelector(".ui-table__group-label")?.textContent).toBe(
      "GBP agent",
    );
    expect(groups[0].querySelector(".ui-table__group-count")?.textContent).toBe(
      "3",
    );
  });

  it("bounds each group independently so one busy automation cannot flood the page", () => {
    const frame = buildGroupedDataTable(
      columns,
      [
        { key: "gbp", label: "GBP agent", rows: runs(30, "gbp.operator") },
        { key: "seo", label: "SEO agent", rows: runs(2, "seo.operator") },
      ],
      { disclosure: { initialRows: 3, noun: "runs" } },
    );

    expect(visibleRows(frame).length).toBe(5);
    const toggles = frame.querySelectorAll(".ui-table__disclosure button");
    expect(toggles.length).toBe(1);
    expect(toggles[0].textContent).toBe("+ 27 more runs");
  });

  it("drops empty groups instead of rendering a header with nothing under it", () => {
    const frame = buildGroupedDataTable(columns, [
      { key: "gbp", label: "GBP agent", rows: runs(2) },
      { key: "content", label: "Content agent", rows: [] },
    ]);
    expect(frame.querySelectorAll("tbody[data-group]").length).toBe(1);
  });

  it("falls back to the empty state when no group has any rows", () => {
    const frame = buildGroupedDataTable(
      columns,
      [{ key: "gbp", label: "GBP agent", rows: [] }],
      { emptyHeading: "No agent runs yet" },
    );
    expect(frame.querySelector(".ui-table__state h3")?.textContent).toBe(
      "No agent runs yet",
    );
  });

  it("carries a caption on the group header for per-automation health", () => {
    const frame = buildGroupedDataTable(columns, [
      {
        key: "gbp",
        label: "GBP agent",
        caption: "Last run 2 hr ago · 1 running",
        rows: runs(1),
      },
    ]);
    expect(frame.querySelector(".ui-table__group-caption")?.textContent).toBe(
      "Last run 2 hr ago · 1 running",
    );
  });
});
