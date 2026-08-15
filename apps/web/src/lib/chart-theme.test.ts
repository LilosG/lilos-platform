import { describe, expect, it } from "vitest";
import { niceAxis } from "./chart-theme";

describe("niceAxis", () => {
  it("uses round ticks with controlled headroom", () => {
    expect(niceAxis(0, 52)).toEqual({ minimum: 0, stepSize: 10, maximum: 60 });
    expect(niceAxis(88, 190)).toEqual({
      minimum: 80,
      stepSize: 20,
      maximum: 200,
    });
  });
});
