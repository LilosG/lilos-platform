import type { Client, ReportingPeriod } from "../types/domain";
/** Revision 10 sample scan shape; fixed ranking samples are not event counts. */
export function visibilitySeries(
  current: number,
  declining: boolean,
  range: ReportingPeriod["days"],
) {
  const shift = range === "7" ? 5 : range === "90" ? 15 : 10;
  const values = declining
    ? [
        current + 12,
        current + 9,
        current + 11,
        current + 6,
        current + 3,
        current,
      ]
    : [
        current - shift,
        current - shift + 3,
        current - shift + 1,
        current - shift + 7,
        current - 2,
        current,
      ];
  const path = (previous: boolean) =>
    values
      .map(
        (v, i) =>
          `${i ? "L" : "M"} ${35 + i * 100} ${previous ? 158 - (v - 22) * 1.8 : 150 - (v - 20) * 1.8}`,
      )
      .join(" ");
  return {
    values,
    path: path(false),
    previous: path(true),
    labels:
      range === "90"
        ? ["Jul 1", "Aug 1"]
        : range === "7"
          ? ["Sep 23", "Sep 26"]
          : ["Sep 1", "Sep 15"],
  };
}
export function chartSample(client?: Client) {
  return {
    current: client?.visibility ?? 57,
    declining: (client?.change ?? 0) < 0,
  };
}
