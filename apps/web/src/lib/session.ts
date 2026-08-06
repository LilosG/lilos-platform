import type { Session } from "@supabase/supabase-js";
import { getSupabaseClient } from "./supabase-client";

export type SessionState =
  | { status: "not-configured" }
  | { status: "signed-out" }
  | { status: "signed-in"; session: Session };

export type SignInResult = { ok: true } | { ok: false; message: string };

export async function getCurrentSession(): Promise<SessionState> {
  const client = getSupabaseClient();
  if (!client) {
    return { status: "not-configured" };
  }
  const { data } = await client.auth.getSession();
  return data.session
    ? { status: "signed-in", session: data.session }
    : { status: "signed-out" };
}

export async function signInWithPassword(
  email: string,
  password: string,
): Promise<SignInResult> {
  const client = getSupabaseClient();
  if (!client) {
    return {
      ok: false,
      message: "Sign-in is not configured for this deployment.",
    };
  }
  const { error } = await client.auth.signInWithPassword({ email, password });
  if (error) {
    return { ok: false, message: error.message };
  }
  return { ok: true };
}

export async function signOut(): Promise<void> {
  const client = getSupabaseClient();
  if (client) {
    await client.auth.signOut();
  }
}

/** Returns null when there is no configured client or no active session. */
export async function getAccessToken(): Promise<string | null> {
  const client = getSupabaseClient();
  if (!client) {
    return null;
  }
  const { data } = await client.auth.getSession();
  return data.session?.access_token ?? null;
}

// --- Multi-factor authentication (step-up to AAL2) ---
//
// Wraps the Supabase MFA API for the one step-up flow this application
// needs: TOTP enroll-or-reuse, then challenge+verify. Never returns or logs
// the TOTP secret/QR data beyond the single enrollment response the caller
// must render once; never logs a verification code.

export type MfaOutcome<T> =
  { ok: true; data: T } | { ok: false; message: string };

export type AssuranceLevels = {
  currentLevel: string | null;
  nextLevel: string | null;
};

export async function getAssuranceLevels(): Promise<
  MfaOutcome<AssuranceLevels>
> {
  const client = getSupabaseClient();
  if (!client) {
    return {
      ok: false,
      message: "Sign-in is not configured for this deployment.",
    };
  }
  const { data, error } =
    await client.auth.mfa.getAuthenticatorAssuranceLevel();
  if (error) {
    return { ok: false, message: error.message };
  }
  return {
    ok: true,
    data: { currentLevel: data.currentLevel, nextLevel: data.nextLevel },
  };
}

/**
 * Whether a session has actually reached AAL2 and may safely be returned to
 * an AAL2-protected route. Deliberately checks only `currentLevel`: an
 * `aal1` session with no MFA factor enrolled yet reports
 * `currentLevel === nextLevel === "aal1"` (there is no further level to step
 * up to until a factor exists), so comparing `currentLevel` to `nextLevel`
 * incorrectly treated that as "no step-up needed" and sent an AAL1 session
 * straight back to the AAL2-protected route — producing an infinite
 * /onboarding <-> /mfa redirect loop.
 */
export function hasReachedAal2(currentLevel: string | null): boolean {
  return currentLevel === "aal2";
}

export type VerifiedTotpFactor = {
  factorId: string;
  friendlyName: string | null;
};

/** Returns the caller's already-verified TOTP factor, if any (never unverified ones). */
export async function findVerifiedTotpFactor(): Promise<
  MfaOutcome<VerifiedTotpFactor | null>
> {
  const client = getSupabaseClient();
  if (!client) {
    return {
      ok: false,
      message: "Sign-in is not configured for this deployment.",
    };
  }
  const { data, error } = await client.auth.mfa.listFactors();
  if (error) {
    return { ok: false, message: error.message };
  }
  const factor = data.totp.find((item) => item.status === "verified");
  return {
    ok: true,
    data: factor
      ? { factorId: factor.id, friendlyName: factor.friendly_name ?? null }
      : null,
  };
}

export type TotpEnrollment = {
  factorId: string;
  /** SVG data URI — render directly as the QR code, do not persist or log. */
  qrCodeSvg: string;
  /** Manual-entry fallback for the same secret the QR code encodes. */
  secret: string;
};

/** Starts TOTP enrollment. The returned factor is unverified until `verifyTotpCode` succeeds. */
export async function enrollTotpFactor(): Promise<MfaOutcome<TotpEnrollment>> {
  const client = getSupabaseClient();
  if (!client) {
    return {
      ok: false,
      message: "Sign-in is not configured for this deployment.",
    };
  }
  const { data, error } = await client.auth.mfa.enroll({ factorType: "totp" });
  if (error) {
    return { ok: false, message: error.message };
  }
  return {
    ok: true,
    data: {
      factorId: data.id,
      qrCodeSvg: data.totp.qr_code,
      secret: data.totp.secret,
    },
  };
}

/**
 * Challenges and verifies a TOTP code in one call, elevating the session to
 * AAL2 on success. Works identically for a freshly enrolled factor (also
 * marks it verified) or an already-verified one from a prior enrollment.
 */
export async function verifyTotpCode(
  factorId: string,
  code: string,
): Promise<MfaOutcome<{ currentLevel: string | null }>> {
  const client = getSupabaseClient();
  if (!client) {
    return {
      ok: false,
      message: "Sign-in is not configured for this deployment.",
    };
  }
  const { error } = await client.auth.mfa.challengeAndVerify({
    factorId,
    code,
  });
  if (error) {
    return { ok: false, message: error.message };
  }
  const { data: levels } =
    await client.auth.mfa.getAuthenticatorAssuranceLevel();
  return { ok: true, data: { currentLevel: levels?.currentLevel ?? null } };
}
