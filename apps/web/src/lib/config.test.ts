import { afterEach, describe, expect, it, vi } from "vitest";
import { readPublicConfig } from "./config";

describe("readPublicConfig", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("returns null when any required deployment value is missing", () => {
    expect(readPublicConfig({})).toBeNull();
    expect(
      readPublicConfig({
        PUBLIC_LILOS_API_BASE_URL: "https://api.lilos.invalid",
      }),
    ).toBeNull();
  });

  it("never fabricates a default when configuration is absent", () => {
    expect(
      readPublicConfig({
        PUBLIC_LILOS_API_BASE_URL: "https://api.lilos.invalid",
        PUBLIC_LILOS_SUPABASE_URL: "https://project.supabase.co",
      }),
    ).toBeNull();
  });

  it("strips a trailing slash from the API base URL", () => {
    expect(
      readPublicConfig({
        PUBLIC_LILOS_API_BASE_URL: "https://api.lilos.invalid/",
        PUBLIC_LILOS_SUPABASE_URL: "https://project.supabase.co",
        PUBLIC_LILOS_SUPABASE_ANON_KEY: "anon-key",
      }),
    ).toEqual({
      apiBaseUrl: "https://api.lilos.invalid",
      supabaseUrl: "https://project.supabase.co",
      supabaseAnonKey: "anon-key",
    });
  });

  it("reads the required public values from the build environment", () => {
    vi.stubEnv("PUBLIC_LILOS_API_BASE_URL", "https://api.lilos.invalid/");
    vi.stubEnv("PUBLIC_LILOS_SUPABASE_URL", "https://project.supabase.co");
    vi.stubEnv("PUBLIC_LILOS_SUPABASE_ANON_KEY", "anon-key");

    expect(readPublicConfig()).toEqual({
      apiBaseUrl: "https://api.lilos.invalid",
      supabaseUrl: "https://project.supabase.co",
      supabaseAnonKey: "anon-key",
    });
  });
});
