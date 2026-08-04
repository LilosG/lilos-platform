export type PublicConfig = {
  apiBaseUrl: string;
  supabaseUrl: string;
  supabaseAnonKey: string;
};

type PublicEnv = Partial<
  Record<
    | "PUBLIC_LILOS_API_BASE_URL"
    | "PUBLIC_LILOS_SUPABASE_URL"
    | "PUBLIC_LILOS_SUPABASE_ANON_KEY",
    string
  >
>;

/** Returns null when required deployment configuration is absent, never a fabricated default. */
export function readPublicConfig(
  env: PublicEnv = import.meta.env,
): PublicConfig | null {
  const apiBaseUrl = env.PUBLIC_LILOS_API_BASE_URL;
  const supabaseUrl = env.PUBLIC_LILOS_SUPABASE_URL;
  const supabaseAnonKey = env.PUBLIC_LILOS_SUPABASE_ANON_KEY;
  if (!apiBaseUrl || !supabaseUrl || !supabaseAnonKey) {
    return null;
  }
  return {
    apiBaseUrl: apiBaseUrl.replace(/\/+$/, ""),
    supabaseUrl,
    supabaseAnonKey,
  };
}
