import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import path from "node:path";

/**
 * Insights is client-facing: the operator sees every product, a client sees only
 * the products they were set up with. Boot already resolved entitlement to hide
 * navigation items, but it did not hand the set to pages, so a page rendered
 * every product's section regardless. A client entitled to Insights but not SEO
 * was shown an Organic search panel for a product they do not have.
 *
 * These assertions are structural because the gating lives in an .astro inline
 * script that vitest cannot import. They are worth having anyway: the failure they
 * guard is a client seeing another product's panel.
 */

const read = (relative: string): string =>
  readFileSync(path.resolve(process.cwd(), relative), "utf8");

describe("product entitlement reaches pages", () => {
  it("boot exposes entitled product keys on its context", () => {
    const boot = read("src/lib/ui/boot.ts");

    expect(boot).toContain("entitledProductKeys: readonly string[]");
    // Resolved once and used for both navigation and page gating.
    expect(boot).toContain(
      "setProductNavigationVisibility(new Set(entitledProductKeys))",
    );
  });

  it("boot documents that hiding a panel is not access control", () => {
    const boot = read("src/lib/ui/boot.ts");

    expect(boot).toMatch(/not access control/i);
  });

  it("insights gates its provider sections on entitlement", () => {
    const insights = read("src/pages/insights.astro");

    expect(insights).toContain("applyProductEntitlement");
    // Both provider-backed sections are wrapped so they can be hidden.
    expect(insights).toContain('id="analytics-section"');
    expect(insights).toContain('id="search-console-section"');
    expect(insights).toContain('["search-console-section", "seo"]');
  });

  it("gated sections start hidden so nothing flashes before entitlement resolves", () => {
    const insights = read("src/pages/insights.astro");

    expect(insights).toMatch(/id="analytics-section"\s+hidden/);
    expect(insights).toMatch(/id="search-console-section"\s+hidden/);
  });
});
