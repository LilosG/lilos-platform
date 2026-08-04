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
