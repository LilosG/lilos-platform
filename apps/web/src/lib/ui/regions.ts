export type RegionKey = string;

export function createRegions<T extends Record<string, HTMLElement>>(
  map: T,
): T {
  return map;
}

export function showOnly(
  regions: Record<string, HTMLElement>,
  visible: HTMLElement,
): void {
  for (const key of Object.keys(regions)) {
    regions[key].hidden = regions[key] !== visible;
  }
}

export function goToLogin(): void {
  const next = encodeURIComponent(window.location.pathname);
  window.location.assign(`/login?next=${next}`);
}
