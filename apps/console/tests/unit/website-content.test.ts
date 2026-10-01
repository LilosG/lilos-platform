// @vitest-environment node
import { describe, it, expect, vi } from "vitest";
import fixtures from "../fixtures/phase4.json";
import {
  adaptWebsite,
  adaptWebsitePage,
  adaptContent,
} from "../../src/adapters/website-content";
import { csrfToken } from "../../src/server/security";
import { forward } from "../../src/server/bff";
import { config } from "../../src/server/config";
const org = fixtures.workspace.organization_id;
describe("Website & Content canonical scope and truth", () => {
  it("retains stale/partial/missing page evidence and unavailable conversions", () => {
    const data = adaptWebsite(structuredClone(fixtures.workspace), org);
    data.pages[0].http_status = null;
    data.pages[0].quality_status = "partial";
    const view = adaptWebsite(data, org);
    expect(view.pages[0].http_status).toBeNull();
    expect(view.pages[0].quality_status).toBe("partial");
    expect(view.conversions).toBe("unavailable_no_canonical_path_source");
    const page = adaptWebsitePage(
      structuredClone(fixtures.page),
      org,
      fixtures.page.evidence.identity.website_id,
      fixtures.page.evidence.identity.page_id,
    );
    page.evidence.ga4_organic_landing = {
      availability: "observed",
      metrics: { keyEvents: 0 },
      quality: "partial",
    };
    expect(
      adaptWebsitePage(
        page,
        org,
        page.evidence.identity.website_id,
        page.evidence.identity.page_id,
      ).evidence.ga4_organic_landing,
    ).toEqual(page.evidence.ga4_organic_landing);
  });
  it("rejects foreign organizations, sites and content identity", () => {
    expect(() =>
      adaptWebsite(fixtures.workspace, fixtures.detail.id),
    ).toThrow();
    expect(() =>
      adaptWebsite(fixtures.workspace, org, fixtures.detail.id),
    ).toThrow();
    const bad = structuredClone(fixtures.workspace);
    bad.pages[0].website_id = fixtures.detail.id;
    expect(() => adaptWebsite(bad, org)).toThrow();
    expect(() => adaptContent(fixtures.detail, org, org)).toThrow();
  });
  it("preserves approval revisions and no PR/deployment/live inference", () => {
    const view = adaptContent(fixtures.detail, org, fixtures.detail.id);
    expect(view.revisions[0].status).toBe("awaiting_editorial");
    expect(view.publications).toEqual([]);
    expect(view.can_approve).toBe(false);
  });
  it("closed reads reject unknown UUID query, unauthenticated and arbitrary proxy before upstream", async () => {
    const locals = {
      settings: config({
        CONSOLE_ENV: "local",
        CONSOLE_ORIGIN: "http://localhost:4346",
        CONSOLE_EXPECTED_HOST: "localhost:4346",
        CONSOLE_API_ORIGIN: "http://localhost:4455",
        CONSOLE_SUPABASE_URL: "http://localhost:4455",
        CONSOLE_SUPABASE_KEY: "synthetic",
        CONSOLE_CSRF_SECRET: "synthetic-csrf-secret-32-characters-minimum",
      }),
      correlationId: "phase4",
      token: "synthetic",
      userId: org,
      binding: "synthetic",
    } as App.Locals;
    const path = `organizations/${org}/command-center/website-content/`;
    const upstream = vi.fn();
    expect(
      (
        await forward(
          new Request(`http://localhost:4346/api/${path}?website_id=slug`),
          path,
          locals,
          upstream,
        )
      ).status,
    ).toBe(400);
    expect(
      (
        await forward(
          new Request(`http://localhost:4346/api/${path}?unknown=1`),
          path,
          locals,
          upstream,
        )
      ).status,
    ).toBe(400);
    expect(
      (
        await forward(
          new Request(`http://localhost:4346/api/${path}`),
          path,
          { ...locals, token: null },
          upstream,
        )
      ).status,
    ).toBe(401);
    expect(
      (
        await forward(
          new Request(
            "http://localhost:4346/api/proxy/?url=http://evil.invalid",
          ),
          "proxy/",
          locals,
          upstream,
        )
      ).status,
    ).toBe(404);
    expect(upstream).not.toHaveBeenCalled();
  });
  it("validates exact action bodies and UUID assets while retaining CSRF/origin/cache boundaries", async () => {
    const settings = config({
      CONSOLE_ENV: "local",
      CONSOLE_ORIGIN: "http://localhost:4346",
      CONSOLE_EXPECTED_HOST: "localhost:4346",
      CONSOLE_API_ORIGIN: "http://localhost:4455",
      CONSOLE_SUPABASE_URL: "http://localhost:4455",
      CONSOLE_SUPABASE_KEY: "synthetic",
      CONSOLE_CSRF_SECRET: "synthetic-csrf-secret-32-characters-minimum",
    });
    const locals = {
      settings,
      userId: org,
      token: "server-only",
      binding: "session",
      correlationId: "phase4",
    } as App.Locals;
    const nonce = csrfToken(locals.binding, org, settings.csrfSecret);
    const path = `organizations/${org}/content-operations/${fixtures.detail.id}/revisions/${fixtures.detail.revisions[0].id}/decision/`;
    const request = (body: unknown, origin = settings.origin) =>
      new Request(settings.origin + "/api/" + path, {
        method: "POST",
        headers: {
          Origin: origin,
          "Content-Type": "application/json",
          "X-CSRF-Token": nonce,
        },
        body: JSON.stringify(body),
      });
    const upstream = vi.fn(
      async (_url: unknown, _init?: RequestInit) =>
        new Response(JSON.stringify({ data: { status: "awaiting_client" } }), {
          headers: {
            "Content-Type": "application/json",
            "Set-Cookie": "unsafe=1",
          },
        }),
    );
    expect(
      (
        await forward(
          request({ stage: "editorial", approve: true, repository: "evil" }),
          path,
          locals,
          upstream,
        )
      ).status,
    ).toBe(400);
    expect(
      (
        await forward(
          request(
            { stage: "editorial", approve: true },
            "https://evil.invalid",
          ),
          path,
          locals,
          upstream,
        )
      ).status,
    ).toBe(403);
    expect(upstream).not.toHaveBeenCalled();
    const response = await forward(
      request({ stage: "editorial", approve: true }),
      path,
      locals,
      upstream,
    );
    expect(response.status).toBe(200);
    expect(response.headers.get("Cache-Control")).toBe("private, no-store");
    expect(response.headers.get("Set-Cookie")).toBeNull();
    expect(upstream.mock.calls[0][1]).toMatchObject({
      headers: {
        Authorization: "Bearer server-only",
        "X-Correlation-ID": "phase4",
      },
      body: JSON.stringify({ stage: "editorial", approve: true }),
    });
    const assets = `organizations/${org}/content-operations/${fixtures.detail.id}/publishing-assets/`;
    expect(
      (
        await forward(
          new Request(settings.origin + "/api/" + assets + "?target_id=wrong"),
          assets,
          locals,
          upstream,
        )
      ).status,
    ).toBe(400);
  });
});
