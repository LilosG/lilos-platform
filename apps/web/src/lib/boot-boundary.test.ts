import { describe, expect, it } from "vitest";
import {
  renderBootFailure,
  withBootBoundary,
  type BootBoundaryRegions,
} from "./boot-boundary";

function fakeRegions(): BootBoundaryRegions {
  return {
    loading: { hidden: false } as unknown as HTMLElement,
    error: { hidden: true, textContent: "" } as unknown as HTMLElement,
  };
}

describe("renderBootFailure", () => {
  it("hides loading and shows + populates the error region", () => {
    const regions = fakeRegions();
    renderBootFailure(regions, "Administration failed to load: boom");
    expect(regions.loading.hidden).toBe(true);
    expect(regions.error.hidden).toBe(false);
    expect(regions.error.textContent).toBe(
      "Administration failed to load: boom",
    );
  });
});

describe("withBootBoundary (Administration boot failure boundary)", () => {
  // Regression: production incident on /administration threw
  // `data.map is not a function` during boot. With `void boot()` and no
  // top-level rejection handler, that unhandled rejection left the page
  // permanently on "Loading Administration…". The boundary must guarantee
  // an unexpected exception renders the truthful error region instead.
  it("renders the error region (and leaves loading hidden) when boot throws, so the page can never stay on Loading", async () => {
    const regions = fakeRegions();
    const throwingBoot = (): Promise<void> =>
      Promise.reject(new TypeError("data.map is not a function"));

    await withBootBoundary(regions, throwingBoot, (error) =>
      error instanceof Error && error.message
        ? `Administration failed to load: ${error.message}`
        : "Administration failed to load unexpectedly.",
    );

    expect(regions.loading.hidden).toBe(true);
    expect(regions.error.hidden).toBe(false);
    expect(regions.error.textContent).toBe(
      "Administration failed to load: data.map is not a function",
    );
  });

  it("still reports a truthful message for non-Error rejections, never a generic hang", async () => {
    const regions = fakeRegions();
    await withBootBoundary(
      regions,
      () => Promise.reject("a bare string throw"),
      (error) =>
        error instanceof Error && error.message
          ? `Administration failed to load: ${error.message}`
          : "Administration failed to load unexpectedly.",
    );
    expect(regions.loading.hidden).toBe(true);
    expect(regions.error.textContent).toBe(
      "Administration failed to load unexpectedly.",
    );
  });

  it("does not touch the regions when boot completes (boot owns region toggling on the success path)", async () => {
    const regions = fakeRegions();
    let ran = false;
    await withBootBoundary(
      regions,
      async () => {
        ran = true;
      },
      () => "should not be called",
    );
    expect(ran).toBe(true);
    expect(regions.loading.hidden).toBe(false);
    expect(regions.error.hidden).toBe(true);
    expect(regions.error.textContent).toBe("");
  });
});
