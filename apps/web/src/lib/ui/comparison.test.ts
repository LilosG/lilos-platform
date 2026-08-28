import { describe, expect, it } from "vitest";
import {
  healthSummary,
  periodComparisonCard,
  periodComparisonGrid,
  rankBadge,
  rankTier,
} from "./comparison";

describe("period comparison cards", () => {
  it("inverts the current period so it leads the row", () => {
    const current = periodComparisonCard({
      label: "Aug 1 – Aug 27",
      current: true,
      metrics: [
        { label: "Impressions", value: 627, format: { unit: "count" } },
      ],
    });
    const prior = periodComparisonCard({
      label: "Jul 5 – Jul 31",
      metrics: [
        { label: "Impressions", value: 295, format: { unit: "count" } },
      ],
    });

    expect(current.classList.contains("ui-comparison-card--current")).toBe(
      true,
    );
    expect(current.dataset.current).toBe("true");
    expect(prior.classList.contains("ui-comparison-card--current")).toBe(false);
  });

  it("renders the first metric as the lead figure and the rest as rows", () => {
    const card = periodComparisonCard({
      label: "Aug 1 – Aug 27",
      metrics: [
        { label: "Impressions", value: 4821, format: { unit: "count" } },
        { label: "Clicks", value: 279, format: { unit: "count" } },
        {
          label: "CTR",
          value: 0.058,
          format: { unit: "percentage", sourceScale: "ratio" },
        },
      ],
    });

    expect(
      card.querySelector(".ui-comparison-card__lead-value")?.textContent,
    ).toBe("4,821");
    expect(card.querySelectorAll(".ui-comparison-card__metric").length).toBe(2);
    expect(card.textContent).toContain("5.8%");
  });

  it("distinguishes a zero delta from no comparison available", () => {
    const withZero = periodComparisonCard({
      label: "Aug",
      metrics: [
        {
          label: "Clicks",
          value: 10,
          delta: 0,
          format: { unit: "count", outcome: "higher-is-better" },
        },
      ],
    });
    const withNone = periodComparisonCard({
      label: "Aug",
      metrics: [{ label: "Clicks", value: 10, format: { unit: "count" } }],
    });

    expect(
      withZero.querySelector(".ui-comparison-card__lead-delta")?.textContent,
    ).toContain("0");
    expect(
      withNone.querySelector(".ui-comparison-card__lead-delta"),
    ).toBeNull();
  });

  it("marks a decline as negative even though the number is smaller", () => {
    const card = periodComparisonCard({
      label: "Aug",
      metrics: [
        {
          label: "Clicks",
          value: 210,
          delta: -69,
          format: { unit: "count", outcome: "higher-is-better" },
        },
      ],
    });

    const delta = card.querySelector(".ui-comparison-card__lead-delta");
    expect(delta?.className).toContain("delta--negative");
    expect(delta?.textContent).toContain("−69");
  });

  it("lays periods out as a single comparable row", () => {
    const grid = periodComparisonGrid([
      { label: "Aug", current: true, metrics: [] },
      { label: "Jul", metrics: [] },
      { label: "Jun", metrics: [] },
    ]);

    expect(grid.dataset.periods).toBe("3");
    expect(grid.querySelectorAll(".ui-comparison-card").length).toBe(3);
  });
});

describe("rank quality bands", () => {
  it("bands positions by what an operator would do about them", () => {
    expect(rankTier(1)).toBe("top");
    expect(rankTier(3)).toBe("top");
    expect(rankTier(4)).toBe("page-one");
    expect(rankTier(10)).toBe("page-one");
    expect(rankTier(11)).toBe("reachable");
    expect(rankTier(20)).toBe("reachable");
    expect(rankTier(21)).toBe("distant");
  });

  it("treats absent and nonsensical positions as not ranking", () => {
    expect(rankTier(null)).toBe("unranked");
    expect(rankTier(undefined)).toBe("unranked");
    expect(rankTier(Number.NaN)).toBe("unranked");
    expect(rankTier(0)).toBe("unranked");
  });

  it("carries the band in the class, the value in the text, and both to a screen reader", () => {
    const badge = rankBadge(2.4);
    expect(badge.className).toContain("ui-rank-badge--top");
    expect(badge.textContent).toBe("2.4");
    expect(badge.getAttribute("aria-label")).toBe("Position 2.4 · Top three");
  });

  it("renders an unranked position as an em dash, not as zero", () => {
    const badge = rankBadge(null);
    expect(badge.textContent).toBe("—");
    expect(badge.getAttribute("aria-label")).toBe("Not ranking");
  });
});

describe("health summary strip", () => {
  it("escalates tone so a count that means trouble is not styled like any other", () => {
    const strip = healthSummary([
      { label: "Active schedules", value: 4, format: { unit: "count" } },
      {
        label: "Overdue",
        value: 2,
        format: { unit: "count" },
        tone: "critical",
      },
      {
        label: "Running now",
        value: 1,
        format: { unit: "count" },
        tone: "attention",
      },
    ]);

    const items = strip.querySelectorAll(".ui-summary-strip__item");
    expect(items.length).toBe(3);
    expect((items[0] as HTMLElement).dataset.tone).toBe("neutral");
    expect((items[1] as HTMLElement).dataset.tone).toBe("critical");
    expect((items[2] as HTMLElement).dataset.tone).toBe("attention");
  });

  it("formats values through the shared metric formatter", () => {
    const strip = healthSummary([
      { label: "Runs", value: 12480, format: { unit: "count" } },
    ]);
    expect(strip.querySelector(".ui-summary-strip__value")?.textContent).toBe(
      "12,480",
    );
  });
});
