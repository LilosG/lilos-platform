import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { readPublicConfig } from "./config";

let cached: SupabaseClient | null | undefined;

/** Returns null when Supabase is not configured for this deployment. */
export function getSupabaseClient(): SupabaseClient | null {
  if (cached !== undefined) {
    return cached;
  }
  const config = readPublicConfig();
  cached = config
    ? createClient(config.supabaseUrl, config.supabaseAnonKey, {
        auth: { persistSession: true, autoRefreshToken: true },
      })
    : null;
  return cached;
}

/** Test-only escape hatch so each test starts from an unconfigured client. */
export function resetSupabaseClientForTests(): void {
  cached = undefined;
}
