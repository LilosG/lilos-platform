import { describe, it, expect } from "vitest";
import {
  checkPhotoDimensions,
  checkPhotoFile,
  photoProblemText,
  sizeText,
} from "../../src/lib/photo-check";
import { failureText, ApiFailure } from "../../src/lib/api-client";

const KB = 1024;
describe("photo limits, checked before upload", () => {
  it.each([
    [{ type: "image/jpeg", size: 300 * KB }, null],
    [{ type: "image/png", size: 5 * KB * KB }, null],
    [{ type: "image/gif", size: 300 * KB }, "MEDIA_TYPE_UNSUPPORTED"],
    [{ type: "application/pdf", size: 300 * KB }, "MEDIA_TYPE_UNSUPPORTED"],
    [{ type: "image/jpeg", size: 9 * KB }, "MEDIA_TOO_SMALL"],
    [{ type: "image/jpeg", size: 5 * KB * KB + 1 }, "MEDIA_TOO_LARGE"],
    [{ type: "image/gif", size: 6 * KB * KB }, "MEDIA_TOO_LARGE"],
  ])("%j -> %s", (file, expected) =>
    expect(checkPhotoFile(file)).toBe(expected),
  );
  it("needs 250 pixels on both sides", () => {
    expect(checkPhotoDimensions(250, 250)).toBeNull();
    expect(checkPhotoDimensions(249, 800)).toBe("MEDIA_DIMENSIONS_TOO_SMALL");
    expect(checkPhotoDimensions(800, 249)).toBe("MEDIA_DIMENSIONS_TOO_SMALL");
  });
  it("words each typed problem, here and for the API's answer", () => {
    for (const [code, text] of Object.entries(photoProblemText)) {
      expect(text).not.toMatch(/[A-Z]+_[A-Z]+/);
      expect(failureText(new ApiFailure(code))).toBe(text);
    }
    expect(failureText(new ApiFailure("STORAGE_NOT_CONFIGURED"))).toMatch(
      /not set up/,
    );
  });
  it("reads sizes as a person would", () => {
    expect(sizeText(340 * KB)).toBe("340 KB");
    expect(sizeText(1.2 * KB * KB)).toBe("1.2 MB");
  });
});
