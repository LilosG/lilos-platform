/**
 * Final boot failure boundary for top-level page boot.
 *
 * A page's `boot()` classifies known failures (a request returning a
 * non-`ok` outcome) and renders the appropriate truthful region itself.
 * This wrapper is the last-resort boundary for an *unexpected* exception —
 * anything `boot` did not classify — so a rejection can never propagate as
 * an unhandled promise rejection that leaves the page permanently showing
 * its "Loading…" region with no way to recover short of a full reload.
 *
 * On an unexpected exception it hides the loading region and renders the
 * existing truthful error region with an operator-safe message. Mirrors the
 * boundary already present in `/onboarding` so `/administration` cannot hang
 * on "Loading Administration…" the way production incident `data.map is not
 * a function` did before this contract was corrected.
 */
export type BootBoundaryRegions = {
  loading: HTMLElement;
  error: HTMLElement;
};

export function renderBootFailure(
  regions: BootBoundaryRegions,
  message: string,
): void {
  regions.loading.hidden = true;
  regions.error.hidden = false;
  regions.error.textContent = message;
}

export async function withBootBoundary(
  regions: BootBoundaryRegions,
  boot: () => Promise<void>,
  describeError: (error: unknown) => string,
): Promise<void> {
  try {
    await boot();
  } catch (error) {
    renderBootFailure(regions, describeError(error));
  }
}
