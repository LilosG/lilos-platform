import { createServerClient, type CookieOptions } from "@supabase/ssr";
import type { AstroCookies } from "astro";
import type { ConsoleConfig } from "./config";
import { cookieOptions } from "./security";
export interface CookieWrite {
  name: string;
  value: string;
  options: CookieOptions;
}
export function validCookieHeader(header: string, base: string): boolean {
  if (Buffer.byteLength(header) > 16384) throw new Error("COOKIE_TOO_LARGE");
  const names = header.split(";").map((part) => part.trim().split("=", 1)[0]);
  const session = names.filter(
    (name) => name === base || name.startsWith(base + "."),
  );
  if (new Set(session).size !== session.length) return false;
  const chunks = session.filter((name) => name !== base);
  if (chunks.length > 8) throw new Error("COOKIE_TOO_LARGE");
  return (
    !(chunks.length && session.includes(base)) &&
    chunks.sort().every((name, index) => name === `${base}.${index}`)
  );
}
// Refresh errors may be a stale request finishing after another instance rotated cookies.
// Buffer all SDK writes and emit only after verified identity; failures emit no Set-Cookie.
export function acceptedWrites(
  writes: CookieWrite[],
  verified: boolean,
): CookieWrite[] {
  return verified ? writes : [];
}
export function requestSession(
  cookies: AstroCookies,
  settings: ConsoleConfig,
  header: string,
) {
  const base = settings.local ? "lilos-session" : "__Host-lilos-session";
  const valid = validCookieHeader(header, base);
  const writes: CookieWrite[] = [];
  const names = header
    .split(";")
    .map((part) => part.trim().split("=", 1)[0])
    .filter(Boolean);
  const jar = new Map(
    names.map((name) => [name, cookies.get(name)?.value ?? ""]),
  );
  const deadline = Date.now() + 15000;
  const authFetch: typeof fetch = async (input, init) => {
    try {
      const response = await fetch(input, {
        ...init,
        signal: AbortSignal.timeout(Math.max(1, deadline - Date.now())),
        redirect: "error",
      });
      if (response.ok) return response;
      // Never pass provider prose/raw bodies to SDK logging. Preserve only known error codes.
      const body = await response.json().catch(() => ({}));
      const allowed = [
        "invalid_credentials",
        "refresh_token_not_found",
        "mfa_verification_failed",
      ];
      const code = allowed.includes(body.code)
        ? body.code
        : "authentication_denied";
      return new Response(
        JSON.stringify({
          msg: "Authentication request denied",
          error_code: code,
        }),
        {
          status: response.status,
          headers: {
            "Content-Type": "application/json",
            "X-Supabase-Api-Version": "2024-01-01",
          },
        },
      );
    } catch {
      return new Response(
        JSON.stringify({
          msg: "Authentication unavailable",
          error_code: "authentication_unavailable",
        }),
        { status: 400, headers: { "Content-Type": "application/json" } },
      );
    }
  };
  const client = createServerClient(
    settings.supabaseUrl,
    settings.supabaseKey,
    {
      global: { fetch: authFetch },
      cookieOptions: { name: base, ...cookieOptions(settings.local) },
      auth: { autoRefreshToken: false, detectSessionInUrl: false },
      cookies: {
        getAll: () =>
          valid ? Array.from(jar, ([name, value]) => ({ name, value })) : [],
        setAll: (values) => {
          writes.push(...values);
          for (const entry of values) {
            if (entry.value) jar.set(entry.name, entry.value);
            else jar.delete(entry.name);
          }
        },
      },
    },
  );
  function flush(verified: boolean) {
    if (verified)
      validCookieHeader(
        Array.from(
          jar,
          ([name, value]) => `${name}=${encodeURIComponent(value)}`,
        ).join("; "),
        base,
      );
    for (const entry of acceptedWrites(writes, verified)) {
      // SDK controls chunk cleanup, never cookie security attributes.
      cookies.set(entry.name, entry.value, {
        ...entry.options,
        ...cookieOptions(settings.local),
        domain: undefined,
      });
    }
    writes.length = 0;
  }
  function clear() {
    for (const name of new Set([...names, ...jar.keys()]))
      if (name === base || name.startsWith(base + "."))
        cookies.delete(name, cookieOptions(settings.local));
    writes.length = 0;
  }
  return { client, flush, clear, valid };
}
