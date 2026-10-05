import {
  adaptChangeSets,
  adaptCompleteness,
  adaptGbpPerformance,
  adaptMedia,
  adaptSpecialHours,
  type GbpPerformanceView,
} from "../adapters/gbp";
import { adaptProfile, type LocalSearchView } from "../adapters/local-search";
import { gbpViewKey, type GbpTabData } from "../lib/gbp-view";
import { read } from "./bff";
/** One failed read must not blank the screen: it becomes null and that panel shows its own error. */
async function soft<T>(load: () => Promise<T>): Promise<T | null> {
  try {
    return await load();
  } catch {
    return null;
  }
}
const periodOf = (days: number) => `${days}d`;
/** The Overview's Business Profile tiles: every readable location, over the reporting period. */
export function loadGbpOverview(
  locals: App.Locals,
  org: string,
  days: number,
): Promise<GbpPerformanceView | null> {
  return soft(async () =>
    adaptGbpPerformance(
      await read(
        locals,
        `organizations/${org}/command-center/gbp/performance/?period=${periodOf(days)}`,
      ),
      org,
    ),
  );
}
export async function loadGbpTab(
  locals: App.Locals,
  search: LocalSearchView,
  params: URLSearchParams,
  days: number,
  pathname: string,
): Promise<GbpTabData> {
  const org = search.organization_id;
  const view = gbpViewKey(params.get("view"));
  const locations = search.profiles.map((p) => ({
    gbpId: p.id,
    locationId: p.location_id,
    name: p.business_name,
    writeEnabled: p.write_enabled,
  }));
  const wanted = params.get("location");
  const selected =
    locations.find((place) => place.locationId === wanted) ??
    locations[0] ??
    null;
  const data: GbpTabData = {
    view,
    organizationId: org,
    locations,
    selected,
    performance: null,
    detail: null,
    media: null,
    hours: null,
    changes: null,
    completeness: null,
    verifyHref: `/mfa/?return=${encodeURIComponent(`${pathname}?${params}`)}`,
  };
  if (!selected) return data;
  const ops = `organizations/${org}/locations/${selected.locationId}/gbp/operations/`;
  const place = `${ops}locations/${selected.gbpId}/`;
  const detail = () =>
    soft(async () =>
      adaptProfile(
        await read(
          locals,
          `organizations/${org}/command-center/local-search/locations/${selected.locationId}/profiles/${selected.gbpId}/`,
        ),
        org,
        selected.locationId,
        selected.gbpId,
      ),
    );
  if (view === "performance")
    data.performance = await soft(async () =>
      adaptGbpPerformance(
        await read(
          locals,
          `organizations/${org}/command-center/gbp/performance/?period=${periodOf(days)}&location_id=${selected.locationId}`,
        ),
        org,
      ),
    );
  else if (view === "posts") data.detail = await detail();
  else if (view === "photos") {
    [data.detail, data.media] = await Promise.all([
      detail(),
      soft(async () => adaptMedia(await read(locals, `${place}media/`))),
    ]);
  } else if (view === "special-hours") {
    [data.detail, data.hours] = await Promise.all([
      detail(),
      soft(async () =>
        adaptSpecialHours(await read(locals, `${place}special-hours/`)),
      ),
    ]);
  } else {
    [data.detail, data.completeness, data.changes] = await Promise.all([
      detail(),
      soft(async () =>
        adaptCompleteness(await read(locals, `${place}completeness/`)),
      ),
      soft(async () =>
        adaptChangeSets(await read(locals, `${place}change-sets/`)),
      ),
    ]);
  }
  return data;
}
