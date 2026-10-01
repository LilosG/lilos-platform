import { describe, it, expect, vi } from "vitest";
import fixtures from "../fixtures/phase2.json";
import {
  adaptIntegrations,
  adaptLocalSearch,
  adaptPage,
  adaptProfile,
  value,
} from "../../src/adapters/local-search";
import { forward } from "../../src/server/bff";
import { csrfToken } from "../../src/server/security";
const org = fixtures.search.organization_id;
const settings = {
  origin: "https://console.test",
  apiOrigin: "https://api.test",
  supabaseUrl: "https://auth.test",
  supabaseKey: "key",
  csrfSecret: "x".repeat(32),
  local: false,
};
const locals = {
  settings,
  userId: org,
  token: "server-only",
  binding: "synthetic-binding",
  csrf: "",
  correlationId: "phase2-test",
  auth: {} as App.Locals["auth"],
};
describe("Phase 2 adapters", () => {
  it("retains reconnect, stale, partial, failure, missing and observed zero independently", () => {
    const integration = adaptIntegrations(fixtures.integration, org);
    expect(integration.google.connection_status).toBe("reconnect_required");
    expect(integration.search_properties[0].freshness_status).toBe("stale");
    expect(integration.syncs[0].failure_code).toBe("PROVIDER_RATE_LIMITED");
    const search = adaptLocalSearch(fixtures.search, org, org);
    expect(search.search_console?.metrics.clicks.current).toBe(0);
    expect(search.search_console?.metrics.clicks.previous).toBeNull();
    expect(search.search_console?.metrics.clicks.quality).toBe("partial");
    expect(search.search_console?.metrics.impressions.current).toBeNull();
    expect(search.crawls[0].status).toBe("partial");
    expect(search.analytics).toBeNull();
    expect(search.unsupported).toContain("geographic_rank_grid");
    expect(value(null)).toBe("Unavailable");
    expect(value(0)).toBe("0");
  });
  it("rejects organization, website, page and location substitutions", () => {
    const foreign = "22222222-2222-4222-8222-222222222222";
    expect(() => adaptIntegrations(fixtures.integration, foreign)).toThrow();
    expect(() => adaptLocalSearch(fixtures.search, foreign)).toThrow();
    expect(() =>
      adaptLocalSearch(
        {
          ...fixtures.search,
          pages: [{ ...fixtures.search.pages[0], website_id: foreign }],
        },
        org,
      ),
    ).toThrow();
    expect(() => adaptPage(fixtures.page, org, org, foreign)).toThrow();
    expect(() =>
      adaptProfile(fixtures.profile, org, foreign, fixtures.profile.profile_id),
    ).toThrow();
    expect(() =>
      adaptLocalSearch({ ...fixtures.search, analytics_scope: "website" }, org),
    ).toThrow();
  });
  it("retains absent profile and exact immutable post approval state", () => {
    const profile = adaptProfile(
      fixtures.profile,
      org,
      org,
      fixtures.profile.profile_id,
    );
    expect(profile.profile).toBeNull();
    expect(profile.completeness_code).toBe("GBP_CAPABILITY_SNAPSHOT_NOT_FOUND");
    expect(profile.posts[0].status).toBe("awaiting_approval");
    expect(profile.can_approve).toBe(false);
    expect(profile.posts[0].publication).toBeNull();
    const page = adaptPage(
      fixtures.page,
      org,
      org,
      fixtures.page.identity.page_id,
    );
    expect(page.gsc.availability).toBe("unavailable");
    expect(page.internal_links.availability).toBe("partial");
  });
});
describe("Phase 2 closed BFF", () => {
  const post = (body: unknown, method = "POST", origin = settings.origin) =>
    new Request(settings.origin + "/api/action/", {
      method,
      headers: {
        origin,
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfToken(locals.binding, org, settings.csrfSecret),
      },
      ...(method === "DELETE" ? {} : { body: JSON.stringify(body) }),
    });
  const upstream = () =>
    vi.fn(
      async () =>
        new Response(JSON.stringify({ data: { status: "queued" } }), {
          headers: { "Content-Type": "application/json" },
        }),
    );
  it("forwards exact canonical sync and mapping bodies without browser credentials", async () => {
    const fetcher = upstream();
    const path = `organizations/${org}/seo/websites/${org}/search-properties/${fixtures.profile.posts[0].id}/sync/`;
    const response = await forward(post({ days: 28 }), path, locals, fetcher);
    expect(response.status).toBe(200);
    expect(response.headers.get("cache-control")).toBe("private, no-store");
    expect(fetcher.mock.calls[0]).toBeDefined();
    expect(
      await forward(
        post({ days: 28, access_token: "evil" }),
        path,
        locals,
        fetcher,
      ).then((r) => r.status),
    ).toBe(400);
  });
  it("protects DELETE mappings with the same CSRF/origin boundary", async () => {
    const fetcher = upstream();
    const path = `organizations/${org}/locations/${org}/gbp-mapping/${fixtures.profile.profile_id}/`;
    expect(
      (
        await forward(
          post({}, "DELETE", "https://evil.test"),
          path,
          locals,
          fetcher,
        )
      ).status,
    ).toBe(403);
    expect(fetcher).not.toHaveBeenCalled();
    expect(
      (await forward(post({}, "DELETE"), path, locals, fetcher)).status,
    ).toBe(200);
  });
  it("rejects unknown workflows, arbitrary query values and unauthorized requests", async () => {
    const fetcher = upstream();
    expect(
      (
        await forward(
          post({}),
          `organizations/${org}/rank-scan/`,
          locals,
          fetcher,
        )
      ).status,
    ).toBe(404);
    const path = `organizations/${org}/command-center/local-search/`;
    for (const query of [
      "?days=30",
      "?website_id=example",
      "?offset=-1",
      "?days=28&days=7",
      "?url=https://evil.test",
    ]) {
      expect(
        (
          await forward(
            new Request(settings.origin + "/api/" + path + query),
            path,
            locals,
            fetcher,
          )
        ).status,
      ).toBe(400);
    }
    expect(
      (
        await forward(
          new Request(settings.origin + "/api/" + path),
          path,
          { ...locals, token: null },
          fetcher,
        )
      ).status,
    ).toBe(401);
    expect(fetcher).not.toHaveBeenCalled();
  });
});
