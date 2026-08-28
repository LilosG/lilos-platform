import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import path from "node:path";

/**
 * The platform read as a developer console: cool grey canvas, system sans
 * everywhere, small bold numerals. The client-facing dashboard it is judged
 * against uses a warm parchment ground, large serif figures and letterspaced
 * caps labels. These tests pin the token decisions that carry that across all
 * pages, and — more importantly — pin the contrast ratios so a future palette
 * tweak cannot quietly break legibility.
 */

// Resolved from the vitest root rather than import.meta.url: the test runs in a
// jsdom environment where import.meta.url is not a file: URL.
const tokens = readFileSync(
  path.resolve(process.cwd(), "src/styles/tokens.css"),
  "utf8",
);

function tokenValue(name: string): string {
  const match = tokens.match(new RegExp(`${name}:\\s*([^;]+);`));
  if (!match) throw new Error(`token ${name} is not defined`);
  return match[1].trim();
}

/**
 * Follows a token through any number of var() indirections to the literal hex.
 * Semantic roles are defined in terms of palette entries, so a contrast check on
 * a semantic role has to resolve the chain rather than measure the string
 * "var(--palette-sage-700)".
 */
function resolve(name: string, depth = 0): string {
  if (depth > 10) throw new Error(`token ${name} does not resolve to a value`);
  const value = tokenValue(name);
  const indirection = value.match(/^var\(\s*(--[\w-]+)\s*\)$/);
  if (indirection) return resolve(indirection[1], depth + 1);
  return value.replace(/\s/g, "");
}

function channel(value: number): number {
  const c = value / 255;
  return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
}

function luminance(hex: string): number {
  const h = hex.replace("#", "");
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

describe("design tokens", () => {
  it("defines a serif display family distinct from the sans", () => {
    const display = tokenValue("--font-family-display");
    const sans = tokenValue("--font-family-sans");

    expect(display).toContain("Playfair Display");
    expect(display).not.toBe(sans);
    // A serif fallback must exist for the moment the webfont has not loaded.
    expect(display).toMatch(/serif/);
  });

  it("uses a warm ground rather than a cool grey", () => {
    // Warm means the red channel leads the blue channel.
    for (const name of [
      "--palette-neutral-0",
      "--palette-neutral-50",
      "--palette-neutral-100",
    ]) {
      const hex = tokenValue(name).replace("#", "");
      const red = parseInt(hex.slice(0, 2), 16);
      const blue = parseInt(hex.slice(4, 6), 16);
      expect(red, `${name} should be warm`).toBeGreaterThan(blue);
    }
  });

  it("keeps every text role above the WCAG AA threshold", () => {
    const page = tokenValue("--palette-neutral-50").replace(/\s/g, "");
    const card = tokenValue("--palette-neutral-0").replace(/\s/g, "");
    const primary = tokenValue("--palette-neutral-900").replace(/\s/g, "");
    const secondary = tokenValue("--palette-neutral-600").replace(/\s/g, "");
    const tertiary = tokenValue("--palette-neutral-500").replace(/\s/g, "");

    // 4.5:1 is the AA threshold for normal-size text.
    expect(contrast(primary, page)).toBeGreaterThanOrEqual(4.5);
    expect(contrast(primary, card)).toBeGreaterThanOrEqual(4.5);
    expect(contrast(secondary, page)).toBeGreaterThanOrEqual(4.5);
    expect(contrast(secondary, card)).toBeGreaterThanOrEqual(4.5);
    expect(contrast(tertiary, page)).toBeGreaterThanOrEqual(4.5);
  });

  it("keeps the sage and gold accents legible on a card", () => {
    const card = tokenValue("--palette-neutral-0");

    expect(
      contrast(tokenValue("--palette-gold-600"), card),
    ).toBeGreaterThanOrEqual(4.5);
    expect(
      contrast(tokenValue("--palette-sage-700"), card),
    ).toBeGreaterThanOrEqual(4.5);
  });

  it("leads the chart series with sage and gold", () => {
    expect(tokenValue("--palette-chart-1")).toBe(
      tokenValue("--palette-sage-500"),
    );
    expect(tokenValue("--palette-chart-2")).toBe(
      tokenValue("--palette-gold-400"),
    );
  });

  it("keeps every rank band legible on its own background", () => {
    // A rank badge is coloured by band, so each band carries its own
    // foreground/background pair and each pair has to clear AA on its own.
    for (const band of ["top", "page-one", "reachable", "distant"]) {
      const foreground = resolve(`--color-rank-${band}-foreground`);
      const background = resolve(`--color-rank-${band}-background`);
      expect(
        contrast(foreground, background),
        `rank band ${band} should clear AA`,
      ).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("keeps the rank bands distinguishable from one another", () => {
    // Colour is doing the work of communicating the band, so two bands that
    // resolve to the same background would silently collapse into one.
    const backgrounds = ["top", "page-one", "reachable", "distant"].map(
      (band) => resolve(`--color-rank-${band}-background`),
    );
    expect(new Set(backgrounds).size).toBe(backgrounds.length);
  });

  it("keeps the inverted current-period card legible", () => {
    // The comparison row inverts the current period, so its text roles are
    // measured against the inverse surface rather than the card.
    const surface = resolve("--color-surface-inverse");

    expect(
      contrast(resolve("--color-text-on-inverse-primary"), surface),
    ).toBeGreaterThanOrEqual(4.5);
    expect(
      contrast(resolve("--color-text-on-inverse-secondary"), surface),
    ).toBeGreaterThanOrEqual(4.5);
    // Positive deltas on the inverted card use the brand accent, not the
    // light-card delta foreground, which fails against a dark ground.
    expect(
      contrast(resolve("--color-brand-accent"), surface),
    ).toBeGreaterThanOrEqual(4.5);
  });

  it("sizes display figures well above body text", () => {
    const figure = parseFloat(tokenValue("--type-figure-size"));
    const body = parseFloat(tokenValue("--type-body-size"));

    expect(figure).toBeGreaterThan(body * 2.5);
  });
});
