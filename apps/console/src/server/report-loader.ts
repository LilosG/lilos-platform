import {
  adaptPortfolioReports,
  adaptReportDetail,
  adaptReportList,
  type PortfolioReports,
  type ReportDetail,
  type ReportList,
} from "../adapters/reports";
import {
  comparisonOfSpec,
  comparisonSlug,
  periodSlug,
  sameComparison,
  samePeriod,
  type ComparisonRef,
  type PeriodRef,
} from "../lib/report-period";
import { APIError, read } from "./bff";
export type Loaded<T> =
  | { kind: "ok"; value: T }
  | { kind: "notfound" }
  | { kind: "unauthenticated" }
  | { kind: "error" };
async function load<T>(work: () => Promise<T>): Promise<Loaded<T>> {
  try {
    return { kind: "ok", value: await work() };
  } catch (e) {
    if (e instanceof APIError && e.status === 401)
      return { kind: "unauthenticated" };
    if (e instanceof APIError && [403, 404].includes(e.status))
      return { kind: "notfound" };
    return { kind: "error" };
  }
}
/** Every client the caller may read, with the latest report of one month. */
export const loadPortfolioReports = (
  locals: App.Locals,
): Promise<Loaded<PortfolioReports>> =>
  load(async () =>
    adaptPortfolioReports(await read(locals, "command-center/reports/")),
  );
/** One client's current report, stored history and next scheduled run. */
export const loadClientReports = (
  locals: App.Locals,
  organization: string,
): Promise<Loaded<ReportList>> =>
  load(async () =>
    adaptReportList(
      await read(
        locals,
        `organizations/${organization}/command-center/reports/`,
      ),
      organization,
    ),
  );
/** One stored revision exactly as saved; with no revision, the newest of that period and comparison. */
export function loadReport(
  locals: App.Locals,
  organization: string,
  period: PeriodRef,
  comparison: ComparisonRef,
  revision: number | null,
): Promise<Loaded<ReportDetail>> {
  const base = `organizations/${organization}/command-center/reports`;
  return load(async () => {
    let wanted = revision;
    if (wanted === null) {
      const list = adaptReportList(
        await read(locals, `${base}/`),
        organization,
      );
      const newest = list.history.find(
        (row) =>
          samePeriod(period, {
            start: row.period.start_month,
            end: row.period.end_month,
          }) &&
          sameComparison(comparison, comparisonOfSpec(row.comparison)) &&
          row.is_current,
      );
      if (!newest) throw new APIError(404, "SOURCE_UNAVAILABLE");
      wanted = newest.revision;
    }
    return adaptReportDetail(
      await read(
        locals,
        `${base}/${periodSlug(period)}/${comparisonSlug(comparison)}/${wanted}/`,
      ),
      { organization, period, comparison, revision: wanted },
    );
  });
}
