/**
 * Packet 4 visual-evidence server.
 *
 * Gating:
 * - exits unless LILOS_PACKET4_FIXTURES=1 is set explicitly;
 * - binds only to 127.0.0.1;
 * - lives under apps/web/tests and is never imported by application code;
 * - proxies an Astro development server, so it is absent from deployed builds.
 */
import { Buffer } from "node:buffer";
import http from "node:http";
import process from "node:process";
import { URL } from "node:url";

import * as fixtures from "./responses.ts";

if (process.env.LILOS_PACKET4_FIXTURES !== "1") {
  throw new Error(
    "Packet 4 fixtures are disabled. Set LILOS_PACKET4_FIXTURES=1 for local visual evidence only.",
  );
}

const proxyPort = 4322;
const astroOrigin = "http://127.0.0.1:4321";
const evidenceCaption = "Fixture-rendered acceptance evidence · not live data";

function base64Url(value) {
  return Buffer.from(JSON.stringify(value)).toString("base64url");
}

const accessToken = `${base64Url({ alg: "HS256", typ: "JWT" })}.${base64Url({
  iss: `http://127.0.0.1:${proxyPort}/auth/v1`,
  sub: "auth-packet-4",
  aud: "authenticated",
  exp: 1893456000,
  iat: 1786700000,
  email: "operator@example.test",
  role: "authenticated",
  aal: "aal2",
  session_id: "session-packet-4",
})}.fixture`;

const session = {
  access_token: accessToken,
  refresh_token: "fixture-refresh-token",
  expires_in: 31536000,
  expires_at: 1893456000,
  token_type: "bearer",
  user: {
    id: "auth-packet-4",
    aud: "authenticated",
    role: "authenticated",
    email: "operator@example.test",
    email_confirmed_at: "2026-01-01T00:00:00Z",
    phone: "",
    confirmed_at: "2026-01-01T00:00:00Z",
    last_sign_in_at: fixtures.observedAt,
    app_metadata: { provider: "email", providers: ["email"] },
    user_metadata: {},
    identities: [],
    created_at: "2026-01-01T00:00:00Z",
    updated_at: fixtures.observedAt,
    is_anonymous: false,
  },
};

function responseFor(pathname) {
  const organizationBase = `/api/v1/organizations/${fixtures.organizationId}`;

  if (pathname === "/api/v1/me") return fixtures.principal;
  if (pathname === "/api/v1/me/organizations") return fixtures.organizations;
  if (pathname === "/api/v1/me/platform-administrator") {
    return fixtures.platformAdministratorStatus;
  }
  if (pathname === "/api/v1/platform/industries") {
    return fixtures.onboardingIndustries;
  }
  if (pathname === "/api/v1/platform/products") {
    return fixtures.onboardingProductCatalog;
  }
  if (pathname === "/api/v1/platform/organizations") {
    return fixtures.onboardingOrganizations;
  }
  if (
    pathname === `/api/v1/platform/organizations/${fixtures.organizationId}`
  ) {
    return fixtures.onboardingOrganization;
  }
  if (
    pathname ===
    `/api/v1/platform/organizations/${fixtures.organizationId}/profile`
  ) {
    return fixtures.onboardingOrganizationProfile;
  }
  if (
    pathname ===
    `/api/v1/platform/organizations/${fixtures.organizationId}/locations`
  ) {
    return fixtures.onboardingLocations;
  }
  if (
    pathname ===
    `/api/v1/platform/organizations/${fixtures.organizationId}/locations/${fixtures.locationId}/profile`
  ) {
    return null;
  }
  if (
    pathname ===
    `/api/v1/platform/organizations/${fixtures.organizationId}/domains`
  ) {
    return fixtures.onboardingDomains;
  }
  if (
    pathname ===
    `/api/v1/platform/organizations/${fixtures.organizationId}/onboarding-state`
  ) {
    return fixtures.onboardingState;
  }
  if (
    pathname ===
    `/api/v1/platform/organizations/${fixtures.organizationId}/product-entitlements`
  ) {
    return fixtures.onboardingEntitlements;
  }
  if (pathname === `${organizationBase}/products`) {
    return fixtures.entitledProducts;
  }
  if (pathname === `${organizationBase}/memberships`) {
    return fixtures.onboardingMemberships;
  }
  if (pathname === `${organizationBase}/invitations`) return [];
  if (pathname === `${organizationBase}/policies/effective/approval`) {
    return fixtures.onboardingApprovalPolicies;
  }
  if (pathname === `${organizationBase}/policies/effective/notification`) {
    return [];
  }
  if (pathname === `${organizationBase}/business-facts/candidates`) {
    return fixtures.onboardingFactCandidates;
  }
  if (pathname === `${organizationBase}/business-facts/effective`) {
    return fixtures.onboardingEffectiveFacts;
  }
  if (pathname.startsWith(`${organizationBase}/products/`)) {
    const segments = pathname.split("/");
    return fixtures.readyProduct(segments.at(-2) ?? "");
  }
  if (pathname === `${organizationBase}/locations`) return fixtures.locations;
  if (pathname === `${organizationBase}/insights/summary`) {
    return fixtures.insightsSummary;
  }
  if (pathname.endsWith("/insights/analytics/performance")) {
    return fixtures.analyticsPerformance;
  }
  if (pathname.endsWith("/search-console/performance")) {
    return fixtures.searchConsolePerformance;
  }
  if (pathname === `${organizationBase}/seo/websites`) {
    return fixtures.websites;
  }
  if (pathname.endsWith("/seo/websites/website-main/search-properties")) {
    return fixtures.searchProperties;
  }
  if (pathname === `${organizationBase}/seo/summary`) {
    return fixtures.seoSummary;
  }
  if (pathname === `${organizationBase}/seo/opportunities`) {
    return fixtures.seoOpportunities;
  }
  if (pathname === `${organizationBase}/integrations/google/status`) {
    return fixtures.googleConnection;
  }
  if (pathname === `${organizationBase}/integrations/google/workspace`) {
    return fixtures.googleWorkspace;
  }
  if (pathname === `${organizationBase}/integrations/google/unmapped`) {
    return fixtures.unmappedResources;
  }
  if (pathname === `${organizationBase}/integrations/github/workspace`) {
    return fixtures.githubWorkspace;
  }
  if (pathname === `${organizationBase}/integrations/github/repositories`) {
    return fixtures.githubWorkspace.repositories;
  }
  if (pathname === `${organizationBase}/content/connections`) {
    return fixtures.githubConnections;
  }
  if (pathname === `${organizationBase}/gbp/locations`) {
    return fixtures.gbpLocations;
  }
  if (pathname.endsWith("/completeness")) return fixtures.completeness;
  if (pathname.endsWith("/suspension-cases")) return [];
  if (pathname.endsWith("/change-sets")) return [];
  if (pathname.endsWith("/special-hours")) return fixtures.specialHours;
  if (pathname.endsWith("/posts/provider")) return fixtures.providerPosts;
  if (pathname.endsWith("/posts")) return fixtures.gbpPosts;
  if (pathname.endsWith("/media")) return fixtures.gbpMedia;
  if (pathname.endsWith("/audit")) return [];
  if (pathname.endsWith("/reviews/summary")) return fixtures.reviewSummary;
  if (pathname.endsWith("/reviews")) return fixtures.reviews;
  if (pathname === `${organizationBase}/content/summary`) {
    return fixtures.contentSummary;
  }
  if (pathname === `${organizationBase}/content/opportunities`) {
    return fixtures.contentOpportunities;
  }
  if (pathname === `${organizationBase}/content/targets`) {
    return fixtures.publishingTargets;
  }
  if (pathname === `${organizationBase}/content`) {
    return fixtures.contentItems;
  }
  if (pathname === `${organizationBase}/leads/summary`) {
    return fixtures.leadSummary;
  }
  if (pathname === `${organizationBase}/leads/sources/performance`) {
    return fixtures.leadSources;
  }
  if (pathname === `${organizationBase}/leads/assignees`) {
    return fixtures.leadAssignees;
  }
  if (pathname === `${organizationBase}/leads`) return fixtures.leads;
  if (pathname.startsWith(`${organizationBase}/leads/`)) {
    return fixtures.leadDetails.find((lead) =>
      pathname.endsWith(`/${lead.id}`),
    );
  }
  if (pathname === `${organizationBase}/workflows/schedules`) {
    return fixtures.workflowSchedules;
  }
  if (pathname === `${organizationBase}/workflows/runs`) {
    return fixtures.workflowRuns;
  }
  if (pathname === `${organizationBase}/workflows`) {
    return fixtures.workflowCatalog;
  }
  return undefined;
}

function sendJson(response, data, status = 200) {
  const body = JSON.stringify(status === 200 ? { data } : data);
  response.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "content-length": Buffer.byteLength(body),
    "cache-control": "no-store",
  });
  response.end(body);
}

function evidenceSessionPage(next) {
  return `<!doctype html><meta charset="utf-8"><title>Evidence session</title><script>
    localStorage.setItem("sb-127-auth-token", ${JSON.stringify(JSON.stringify(session))});
    localStorage.setItem("selected_org_id", ${JSON.stringify(fixtures.organizationId)});
    location.replace(${JSON.stringify(next)});
  </script>`;
}

function injectEvidenceCaption(html) {
  const caption = `<div data-packet-4-evidence-caption style="position:fixed;right:16px;bottom:12px;z-index:2147483647;padding:7px 11px;border:1px solid #a96f18;border-radius:999px;background:#fff8e8;color:#5b3a07;font:600 12px/1.2 system-ui,sans-serif;box-shadow:0 2px 10px rgba(0,0,0,.12)">${evidenceCaption}</div>`;
  return html.includes("</body>")
    ? html.replace("</body>", `${caption}</body>`)
    : `${html}${caption}`;
}

const server = http.createServer(async (request, response) => {
  const url = new URL(request.url ?? "/", `http://127.0.0.1:${proxyPort}`);

  if (url.pathname === "/ready") {
    try {
      const upstream = await globalThis.fetch(astroOrigin);
      if (!upstream.ok) throw new Error(`Astro returned ${upstream.status}`);
      response.writeHead(200, {
        "content-type": "text/plain; charset=utf-8",
        "cache-control": "no-store",
      });
      response.end("ready");
    } catch {
      response.writeHead(503, {
        "content-type": "text/plain; charset=utf-8",
        "cache-control": "no-store",
      });
      response.end("starting");
    }
    return;
  }

  if (url.pathname === "/evidence-session") {
    const next = url.searchParams.get("next") || "/";
    const mode = url.searchParams.get("mode") || "full";
    const body = evidenceSessionPage(next);
    response.writeHead(200, {
      "content-type": "text/html; charset=utf-8",
      "content-length": Buffer.byteLength(body),
      "cache-control": "no-store",
      "set-cookie": `packet4-fixture-mode=${encodeURIComponent(mode)}; Path=/; SameSite=Lax`,
    });
    response.end(body);
    return;
  }

  if (url.pathname.startsWith("/api/v1/")) {
    const fixtureMode =
      request.headers.cookie
        ?.split(";")
        .map((part) => part.trim())
        .find((part) => part.startsWith("packet4-fixture-mode="))
        ?.split("=")[1] ?? "full";
    if (
      decodeURIComponent(fixtureMode) === "no-data" &&
      url.pathname.endsWith("/insights/summary")
    ) {
      sendJson(response, fixtures.emptyInsightsSummary);
      return;
    }
    if (
      decodeURIComponent(fixtureMode) === "missing-google" &&
      url.pathname.endsWith("/integrations/google/status")
    ) {
      sendJson(response, fixtures.disconnectedGoogleConnection);
      return;
    }
    const fixture = responseFor(url.pathname);
    if (fixture === undefined) {
      process.stdout.write(
        `[fixture-miss] ${request.method ?? "GET"} ${url.pathname}\n`,
      );
      sendJson(
        response,
        {
          error: {
            code: "FIXTURE_NOT_DEFINED",
            message: "No Packet 4 response fixture is defined for this route.",
            details: [],
          },
        },
        501,
      );
      return;
    }
    sendJson(response, fixture);
    return;
  }

  if (url.pathname.startsWith("/auth/v1/")) {
    sendJson(response, session.user);
    return;
  }

  try {
    const upstream = await globalThis.fetch(
      `${astroOrigin}${url.pathname}${url.search}`,
      {
        method: request.method,
        headers: { accept: request.headers.accept ?? "*/*" },
      },
    );
    const contentType = upstream.headers.get("content-type") ?? "";
    let body = Buffer.from(await upstream.arrayBuffer());
    if (contentType.includes("text/html")) {
      body = Buffer.from(injectEvidenceCaption(body.toString("utf8")));
    }
    const headers = Object.fromEntries(upstream.headers.entries());
    delete headers["content-encoding"];
    delete headers["content-length"];
    headers["content-length"] = String(body.byteLength);
    headers["cache-control"] = "no-store";
    response.writeHead(upstream.status, headers);
    response.end(body);
  } catch (error) {
    response.writeHead(502, { "content-type": "text/plain; charset=utf-8" });
    response.end(`Astro proxy failed: ${String(error)}`);
  }
});

server.listen(proxyPort, "127.0.0.1", () => {
  process.stdout.write(
    `Packet 4 evidence server listening on http://127.0.0.1:${proxyPort}\n`,
  );
});
