import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("./supabase-client", () => ({
  getSupabaseClient: vi.fn(),
}));

import { getSupabaseClient } from "./supabase-client";
import {
  enrollTotpFactor,
  findVerifiedTotpFactor,
  getAssuranceLevels,
  hasReachedAal2,
  verifyTotpCode,
} from "./session";

afterEach(() => {
  vi.restoreAllMocks();
});

function fakeClient(mfa: Record<string, unknown>) {
  return { auth: { mfa } } as unknown as ReturnType<typeof getSupabaseClient>;
}

describe("getAssuranceLevels", () => {
  it("returns not-configured when Supabase is unavailable", async () => {
    vi.mocked(getSupabaseClient).mockReturnValue(null);
    const result = await getAssuranceLevels();
    expect(result).toEqual({
      ok: false,
      message: "Sign-in is not configured for this deployment.",
    });
  });

  it("reports the real current/next AAL levels from Supabase, not a fabricated default", async () => {
    vi.mocked(getSupabaseClient).mockReturnValue(
      fakeClient({
        getAuthenticatorAssuranceLevel: vi.fn().mockResolvedValue({
          data: { currentLevel: "aal1", nextLevel: "aal2" },
          error: null,
        }),
      }),
    );
    const result = await getAssuranceLevels();
    expect(result).toEqual({
      ok: true,
      data: { currentLevel: "aal1", nextLevel: "aal2" },
    });
  });
});

describe("hasReachedAal2", () => {
  it("returns false for aal1/aal1 (no factor enrolled yet) instead of treating it as step-up complete", () => {
    // Regression: this is exactly the shape Supabase returns for a signed-in
    // session with no MFA factor enrolled -- currentLevel and nextLevel are
    // both "aal1" because there is no further level to step up to yet.
    // Comparing currentLevel to nextLevel previously treated that as "no
    // step-up needed" and sent the still-AAL1 session straight back to the
    // AAL2-protected route, producing an infinite /onboarding <-> /mfa loop.
    expect(hasReachedAal2("aal1")).toBe(false);
  });
});

describe("findVerifiedTotpFactor", () => {
  it("only returns a factor with status 'verified', never an unverified one", async () => {
    vi.mocked(getSupabaseClient).mockReturnValue(
      fakeClient({
        listFactors: vi.fn().mockResolvedValue({
          data: {
            totp: [
              { id: "unverified-1", status: "unverified", friendly_name: null },
              { id: "verified-1", status: "verified", friendly_name: "Phone" },
            ],
          },
          error: null,
        }),
      }),
    );
    const result = await findVerifiedTotpFactor();
    expect(result).toEqual({
      ok: true,
      data: { factorId: "verified-1", friendlyName: "Phone" },
    });
  });

  it("returns null (not an error) when no verified factor exists yet", async () => {
    vi.mocked(getSupabaseClient).mockReturnValue(
      fakeClient({
        listFactors: vi
          .fn()
          .mockResolvedValue({ data: { totp: [] }, error: null }),
      }),
    );
    const result = await findVerifiedTotpFactor();
    expect(result).toEqual({ ok: true, data: null });
  });
});

describe("enrollTotpFactor", () => {
  it("returns exactly the QR/secret payload Supabase issued, once, for direct rendering", async () => {
    vi.mocked(getSupabaseClient).mockReturnValue(
      fakeClient({
        enroll: vi.fn().mockResolvedValue({
          data: {
            id: "factor-123",
            totp: { qr_code: "<svg>fake</svg>", secret: "JBSWY3DPEHPK3PXP" },
          },
          error: null,
        }),
      }),
    );
    const result = await enrollTotpFactor();
    expect(result).toEqual({
      ok: true,
      data: {
        factorId: "factor-123",
        qrCodeSvg: "<svg>fake</svg>",
        secret: "JBSWY3DPEHPK3PXP",
      },
    });
  });

  it("surfaces a Supabase enrollment error truthfully", async () => {
    vi.mocked(getSupabaseClient).mockReturnValue(
      fakeClient({
        enroll: vi.fn().mockResolvedValue({
          data: null,
          error: { message: "rate limited" },
        }),
      }),
    );
    const result = await enrollTotpFactor();
    expect(result).toEqual({ ok: false, message: "rate limited" });
  });
});

describe("verifyTotpCode", () => {
  it("elevates to AAL2 on a correct code and reports the new level", async () => {
    const challengeAndVerify = vi
      .fn()
      .mockResolvedValue({ data: { access_token: "new-token" }, error: null });
    const getAuthenticatorAssuranceLevel = vi.fn().mockResolvedValue({
      data: { currentLevel: "aal2", nextLevel: "aal2" },
      error: null,
    });
    vi.mocked(getSupabaseClient).mockReturnValue(
      fakeClient({ challengeAndVerify, getAuthenticatorAssuranceLevel }),
    );
    const result = await verifyTotpCode("factor-123", "123456");
    expect(result).toEqual({ ok: true, data: { currentLevel: "aal2" } });
    expect(challengeAndVerify).toHaveBeenCalledWith({
      factorId: "factor-123",
      code: "123456",
    });
  });

  it("returns a truthful failure for an incorrect code without elevating", async () => {
    const challengeAndVerify = vi.fn().mockResolvedValue({
      data: null,
      error: { message: "Invalid TOTP code entered" },
    });
    vi.mocked(getSupabaseClient).mockReturnValue(
      fakeClient({ challengeAndVerify }),
    );
    const result = await verifyTotpCode("factor-123", "000000");
    expect(result).toEqual({ ok: false, message: "Invalid TOTP code entered" });
  });

  it("never includes the verification code or a token in its return value", async () => {
    const challengeAndVerify = vi.fn().mockResolvedValue({
      data: { access_token: "super-secret-token" },
      error: null,
    });
    const getAuthenticatorAssuranceLevel = vi.fn().mockResolvedValue({
      data: { currentLevel: "aal2", nextLevel: "aal2" },
      error: null,
    });
    vi.mocked(getSupabaseClient).mockReturnValue(
      fakeClient({ challengeAndVerify, getAuthenticatorAssuranceLevel }),
    );
    const result = await verifyTotpCode("factor-123", "654321");
    const serialized = JSON.stringify(result);
    expect(serialized).not.toContain("654321");
    expect(serialized).not.toContain("super-secret-token");
  });
});
