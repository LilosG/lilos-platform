export interface ConsoleConfig {
  origin: string;
  apiOrigin: string;
  supabaseUrl: string;
  supabaseKey: string;
  csrfSecret: string;
  local: boolean;
}
export function config(
  env: Record<string, string | undefined> = process.env,
): ConsoleConfig {
  const local = env.CONSOLE_ENV === "local";
  const origin = new URL(env.CONSOLE_ORIGIN ?? "https://invalid.invalid");
  const api = new URL(env.CONSOLE_API_ORIGIN ?? "https://invalid.invalid");
  const supabase = new URL(
    env.CONSOLE_SUPABASE_URL ?? "https://invalid.invalid",
  );
  const loopback = (url: URL) =>
    ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname);
  if (
    !env.CONSOLE_ORIGIN ||
    !env.CONSOLE_API_ORIGIN ||
    !env.CONSOLE_SUPABASE_URL ||
    !env.CONSOLE_SUPABASE_KEY ||
    (env.CONSOLE_CSRF_SECRET?.length ?? 0) < 32 ||
    [origin, api, supabase].some(
      (url) =>
        url.username ||
        url.password ||
        url.search ||
        url.hash ||
        url.pathname !== "/" ||
        (url.protocol !== "https:" &&
          !(local && loopback(url) && url.protocol === "http:")),
    ) ||
    origin.host !== env.CONSOLE_EXPECTED_HOST
  )
    throw new Error("CONSOLE_CONFIGURATION_REQUIRED");
  if (env.VERCEL_ENV === "preview" || env.CONSOLE_ENV === "staging") {
    const expected =
      env.VERCEL_ENV === "preview"
        ? env.VERCEL_URL
        : "console-staging.lilosgrowth.com";
    if (
      origin.host !== expected ||
      env.CONSOLE_DEPLOYMENT_PROTECTED !== "true" ||
      api.origin !== env.CONSOLE_APPROVED_STAGING_API_ORIGIN ||
      api.origin === env.CONSOLE_PRODUCTION_API_ORIGIN ||
      !env.CONSOLE_STAGING_SUPABASE_PROJECT_REF ||
      env.CONSOLE_STAGING_SUPABASE_PROJECT_REF ===
        env.CONSOLE_PRODUCTION_SUPABASE_PROJECT_REF ||
      supabase.hostname !==
        `${env.CONSOLE_STAGING_SUPABASE_PROJECT_REF}.supabase.co`
    )
      throw new Error("CONSOLE_STAGING_ISOLATION_REQUIRED");
  }
  return {
    origin: origin.origin,
    apiOrigin: api.origin,
    supabaseUrl: supabase.origin,
    supabaseKey: env.CONSOLE_SUPABASE_KEY,
    csrfSecret: env.CONSOLE_CSRF_SECRET!,
    local,
  };
}
