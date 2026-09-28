/**
 * Read-only Search Intelligence production acceptance. Execute only for an
 * authorized fixture after production:auth has saved its operator session.
 * Required: LILOS_PRODUCTION_ACCEPTANCE_ORG_NAME,
 * LILOS_SEARCH_ACCEPTANCE_ORG_ID, LILOS_SEARCH_ACCEPTANCE_LOCATION_ID,
 * LILOS_SEARCH_ACCEPTANCE_WEBSITE_ID. Optional: LILOS_SEARCH_ACCEPTANCE_PAGE_ID.
 * Run explicitly with npm run production:search-intelligence.
 */
import { expect, test, type Page } from "@playwright/test";
import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import type {
  SearchIntelligenceItem,
  SearchIntelligenceWorkspace,
  SEOPageIntelligence,
  SEOWebsite,
} from "../../src/lib/seo";
import { statusLabel } from "../../src/lib/status-language";

const WEB_BASE = "https://lilos-platform-web.vercel.app";
const API_BASE = "https://lilos-api.onrender.com";
const AUTH_FILE = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../.auth/production-state.json",
);
const fixture = {
  organizationName: process.env.LILOS_PRODUCTION_ACCEPTANCE_ORG_NAME?.trim(),
  organizationId: process.env.LILOS_SEARCH_ACCEPTANCE_ORG_ID?.trim(),
  locationId: process.env.LILOS_SEARCH_ACCEPTANCE_LOCATION_ID?.trim(),
  websiteId: process.env.LILOS_SEARCH_ACCEPTANCE_WEBSITE_ID?.trim(),
  pageId: process.env.LILOS_SEARCH_ACCEPTANCE_PAGE_ID?.trim(),
};

type ApiResponse<T> = { status: number; data?: T; error?: string };

async function get<T>(page: Page, route: string, layer: string): Promise<T> {
  const result = (await page.evaluate(
    async ({ apiBase, route }) => {
      const key = Object.keys(localStorage).find(
        (value) => value.startsWith("sb-") && value.endsWith("-auth-token"),
      );
      let token = "";
      try {
        token =
          JSON.parse(localStorage.getItem(key ?? "") ?? "{}").access_token ??
          "";
      } catch {
        // A corrupt or expired session is reported below as authentication unavailable.
      }
      if (!token)
        return { status: 401, error: "saved session has no access token" };
      try {
        const response = await fetch(`${apiBase}${route}`, {
          method: "GET",
          headers: {
            Accept: "application/json",
            Authorization: `Bearer ${token}`,
          },
        });
        if (!response.ok) {
          return {
            status: response.status,
            error: (await response.text()).slice(0, 300),
          };
        }
        return { status: response.status, data: await response.json() };
      } catch (error) {
        return { status: 0, error: String(error) };
      }
    },
    { apiBase: API_BASE, route },
  )) as ApiResponse<{ data: T }>;
  expect(
    result.status,
    `${layer}: ${result.status === 401 ? "authentication unavailable" : result.status === 404 ? "deployed route unavailable" : `GET ${route} failed`} (HTTP ${result.status}: ${result.error ?? "no detail"})`,
  ).toBe(200);
  expect(
    result.data?.data,
    `${layer}: API response missing data`,
  ).toBeDefined();
  return result.data!.data;
}

function requireFixture(): {
  organizationName: string;
  organizationId: string;
  locationId: string;
  websiteId: string;
  pageId?: string;
} {
  for (const [key, value] of [
    ["LILOS_PRODUCTION_ACCEPTANCE_ORG_NAME", fixture.organizationName],
    ["LILOS_SEARCH_ACCEPTANCE_ORG_ID", fixture.organizationId],
    ["LILOS_SEARCH_ACCEPTANCE_LOCATION_ID", fixture.locationId],
    ["LILOS_SEARCH_ACCEPTANCE_WEBSITE_ID", fixture.websiteId],
  ]) {
    if (!value) throw new Error(`Acceptance fixture missing: ${key}`);
  }
  if (!fs.existsSync(AUTH_FILE)) {
    throw new Error(
      `Authentication unavailable: ${AUTH_FILE} missing. Run production:auth for the authorized organization.`,
    );
  }
  return fixture as {
    organizationName: string;
    organizationId: string;
    locationId: string;
    websiteId: string;
    pageId?: string;
  };
}

test("Search Intelligence deployed read path matches persisted evidence", async ({
  page,
}) => {
  const target = requireFixture();
  const blockedWrites: string[] = [];
  await page.route("**/*", async (route) => {
    const request = route.request();
    const origin = new URL(request.url()).origin;
    if (
      (origin === API_BASE || origin === WEB_BASE) &&
      request.method() !== "GET"
    ) {
      blockedWrites.push(`${request.method()} ${request.url()}`);
      await route.abort("blockedbyclient");
      return;
    }
    await route.continue();
  });
  await page.goto(
    `${WEB_BASE}/seo?org=${encodeURIComponent(target.organizationId)}`,
    {
      waitUntil: "domcontentloaded",
    },
  );
  await expect(
    page.locator("#sign-out-button"),
    "authentication unavailable",
  ).toBeVisible();
  await expect(
    page.locator("#seo-content"),
    "Search Intelligence route unavailable or SEO access denied",
  ).toBeVisible();
  await expect(
    page.locator("#organization-switcher"),
    "organization scope missing from UI",
  ).toHaveValue(target.organizationId);
  await expect(
    page.locator("#active-organization-name"),
    "UI/backend organization identity mismatch",
  ).toHaveText(target.organizationName);

  const base = `/api/v1/organizations/${target.organizationId}`;
  const memberships = await get<
    Array<{ organization_id: string; organization_name: string }>
  >(page, "/api/v1/me/organizations", "organization scope");
  expect(
    memberships.some(
      (row) =>
        row.organization_id === target.organizationId &&
        row.organization_name === target.organizationName,
    ),
    "organization/location not resolved: authorized membership does not match fixture",
  ).toBe(true);
  const locations = await get<Array<{ id: string }>>(
    page,
    `${base}/locations?limit=100`,
    "location scope",
  );
  expect(
    locations.some((row) => row.id === target.locationId),
    "organization/location not resolved: fixture location is absent",
  ).toBe(true);
  const websites = await get<SEOWebsite[]>(
    page,
    `${base}/seo/websites`,
    "website identity",
  );
  const website = websites.find((row) => row.id === target.websiteId);
  expect(
    website,
    "website missing: configured fixture website is absent",
  ).toBeDefined();
  expect(website?.location_id, "UI/backend website location mismatch").toBe(
    target.locationId,
  );
  expect(website?.canonical_origin, "website origin missing").toBeTruthy();

  const workspace = await get<SearchIntelligenceWorkspace>(
    page,
    `${base}/seo/workspace?limit=50&offset=0`,
    "Search Intelligence workspace",
  );
  const readiness = workspace.readiness.find(
    (row) => row.website_id === target.websiteId,
  );
  expect(
    readiness,
    workspace.readiness_has_more
      ? "website readiness outside bounded first 100 sites"
      : "website missing from workspace readiness",
  ).toBeDefined();
  expect(readiness?.location_id, "readiness location mismatch").toBe(
    target.locationId,
  );
  for (const [source, state] of [
    ["GSC", readiness?.gsc],
    ["GA4", readiness?.ga4],
    ["page inventory", readiness?.page_inventory],
  ] as const) {
    expect(state, `${source} readiness missing`).toBeTruthy();
    if (state === "unavailable" || state === "stale")
      console.log(`LIMITATION ${source}: ${state}`);
  }
  const panel = page.locator("#tab-intelligence");
  await expect(
    panel.getByText("Acceptance journey readiness"),
    "workspace read route unavailable",
  ).toBeVisible();
  for (const heading of [
    "Requires Attention",
    "Growth Opportunities",
    "Technical Regressions",
    "Currently Measuring",
    "Completed / Learned",
  ]) {
    await expect(
      panel.getByRole("heading", { name: heading, exact: true }),
      `workspace section missing: ${heading}`,
    ).toBeVisible();
  }
  const readinessCard = panel
    .locator(".ui-card")
    .filter({ hasText: "Acceptance journey readiness" });
  const siteReadiness = readinessCard.locator("div.ui-stack").filter({
    has: page.getByRole("heading", { name: website!.name, exact: true }),
  });
  await expect(
    siteReadiness,
    "website identity absent from UI readiness",
  ).toBeVisible();
  for (const state of [
    readiness!.gsc,
    readiness!.ga4,
    readiness!.page_inventory,
  ]) {
    await expect(
      siteReadiness.getByText(statusLabel(state)).first(),
      `readiness mismatch: ${state}`,
    ).toBeVisible();
  }
  expect(readiness!.gsc, "GSC unmapped for acceptance website").not.toBe(
    "unavailable",
  );
  expect(readiness!.ga4, "GA4 unmapped for acceptance website").not.toBe(
    "unavailable",
  );
  expect(
    readiness!.page_inventory,
    "crawl/page inventory unavailable for acceptance website",
  ).toBe("observed");
  expect(readiness!.gsc, "GSC evidence stale for acceptance website").toBe(
    "fresh",
  );
  expect(readiness!.ga4, "GA4 evidence stale for acceptance website").toBe(
    "fresh",
  );

  let items: SearchIntelligenceItem[] = [...workspace.items];
  let next = workspace.pagination.next_offset;
  for (let count = 0; next !== null && count < 20; count += 1) {
    const batch = await get<SearchIntelligenceWorkspace>(
      page,
      `${base}/seo/workspace?limit=50&offset=${next}`,
      "workspace pagination",
    );
    items = items.concat(batch.items);
    next = batch.pagination.next_offset;
  }
  expect(
    next,
    "workspace history exceeds bounded acceptance scan; supply a known page fixture",
  ).toBeNull();
  const scoped = items.filter((item) => item.website.id === target.websiteId);
  for (const item of scoped) {
    expect(item.website.location_id, "opportunity location mismatch").toBe(
      target.locationId,
    );
    expect(
      Number.isFinite(item.opportunity.priority_score),
      "backend priority missing",
    ).toBe(true);
    if (item.page)
      expect(item.page.website_id, "opportunity page/website mismatch").toBe(
        target.websiteId,
      );
    else
      expect(
        item.opportunity.page_id,
        "query-only demand acquired an invented page attribution",
      ).toBeNull();
    const business = item.opportunity.evidence.business_importance as
      { business_importance_state?: string } | undefined;
    expect(
      business?.business_importance_state,
      "backend business importance state missing",
    ).toBeTruthy();
    const passes = item.recommendation?.decision_context?.passes;
    if (passes) {
      for (const key of [
        "access",
        "competition",
        "answer_engines",
        "conversion",
      ] as const) {
        expect(
          passes[key]?.availability,
          `Hermes ${key} persisted availability missing`,
        ).toBeTruthy();
      }
    }
  }
  const candidates = scoped.filter((item) =>
    target.pageId ? item.page?.id === target.pageId : Boolean(item.page),
  );
  const selected =
    candidates.find((item) => !item.outcome && !item.task?.verified_at) ??
    candidates[0];
  if (!selected?.page) {
    throw new Error(
      `no resolved page fixture: website ${target.websiteId}; inventory=${readiness!.page_inventory}; ${target.pageId ? `page ${target.pageId} has no workspace opportunity` : "no page-backed workspace opportunity"}`,
    );
  }
  const intelligence = await get<SEOPageIntelligence>(
    page,
    `${base}/seo/websites/${target.websiteId}/pages/${selected.page.id}/intelligence`,
    "Page Intelligence",
  );
  expect(
    intelligence.identity.organization_id,
    "Page Intelligence organization mismatch",
  ).toBe(target.organizationId);
  expect(
    intelligence.identity.website_id,
    "Page Intelligence website mismatch",
  ).toBe(target.websiteId);
  expect(intelligence.identity.page_id, "Page Intelligence page mismatch").toBe(
    selected.page.id,
  );
  expect(
    intelligence.identity.normalized_url,
    "Page Intelligence URL mismatch",
  ).toBe(selected.page.normalized_url);
  for (const [source, evidence] of [
    ["GSC", intelligence.gsc],
    ["GA4", intelligence.ga4_organic_landing],
  ] as const) {
    expect(
      evidence.availability,
      `${source} page availability missing`,
    ).toBeTruthy();
    expect(
      evidence.limitation,
      `${source} page limitation missing`,
    ).toBeDefined();
  }
  const pagePath = new URL(selected.page.normalized_url).pathname;
  const listSection =
    selected.opportunity.recommendation_class === "technical_regression" &&
    !selected.outcome
      ? "Technical Regressions"
      : selected.opportunity.recommendation_class === "growth_change" &&
          !selected.outcome &&
          !selected.task?.verified_at
        ? "Growth Opportunities"
        : selected.latest_measured
          ? "Completed / Learned"
          : selected.task?.verified_at
            ? "Currently Measuring"
            : "Requires Attention";
  let row = panel
    .locator("section.ui-card")
    .filter({
      has: page.getByRole("heading", { name: listSection, exact: true }),
    })
    .locator("ul.ui-record-list > li")
    .filter({
      has: page.getByRole("heading", {
        name: `${website!.name} · ${pagePath}`,
        exact: true,
      }),
    });
  if (!selected.outcome && !selected.task?.verified_at)
    row = row.filter({
      hasText: `Priority ${selected.opportunity.priority_score}`,
    });
  row = row.first();
  let uiOffset = 0;
  for (
    let pageNumber = 0;
    (await row.count()) === 0 && pageNumber < 20;
    pageNumber += 1
  ) {
    const nextButton = panel.getByRole("button", { name: "Next 50" });
    if (!(await nextButton.isVisible())) break;
    const expectedOffset = uiOffset + 50;
    const nextWorkspaceResponse = page.waitForResponse((response) => {
      const url = new URL(response.url());
      return (
        response.request().method() === "GET" &&
        url.origin === API_BASE &&
        url.pathname === `${base}/seo/workspace` &&
        url.searchParams.get("limit") === "50" &&
        url.searchParams.get("offset") === String(expectedOffset)
      );
    });
    await nextButton.click();
    const response = await nextWorkspaceResponse;
    expect(
      response.ok(),
      `Search Intelligence workspace page offset ${expectedOffset} failed: HTTP ${response.status()}`,
    ).toBe(true);
    await expect(
      panel.getByRole("navigation", { name: "Search Intelligence work pages" }),
      "workspace pagination did not settle",
    ).toBeVisible();
    uiOffset = expectedOffset;
  }
  await expect(
    row,
    "resolved page opportunity absent from deployed workspace UI",
  ).toBeVisible();
  if (
    selected.opportunity.recommendation_class === "growth_change" &&
    !selected.outcome &&
    !selected.task?.verified_at
  ) {
    const business = selected.opportunity.evidence.business_importance as {
      business_importance_state: string;
    };
    await expect(
      row,
      "browser business importance differs from backend",
    ).toContainText(
      `Business importance: ${statusLabel(business.business_importance_state)}`,
    );
  }
  await row.getByRole("button", { name: "Review" }).click();
  await expect(
    panel.getByRole("heading", { name: "Page identity" }),
    "Page Intelligence unavailable in UI",
  ).toBeVisible();
  await expect(
    panel.getByText(selected.page.normalized_url, { exact: true }).first(),
    "UI/backend page identity mismatch",
  ).toBeVisible();
  await expect(
    panel.getByText(target.websiteId),
    "UI/backend website identity mismatch",
  ).toBeVisible();
  await expect(
    panel
      .locator(".ui-inline")
      .filter({ has: page.getByText("Priority", { exact: true }) }),
    "browser priority differs from backend",
  ).toContainText(String(selected.opportunity.priority_score));
  for (const heading of [
    "Search evidence",
    "Conversion and content",
    "Decision",
    "Access",
    "Competition",
    "Answer Engines",
    "Conversion",
    "Implementation and verification",
    "Measurement and observed outcome",
  ]) {
    await expect(
      panel.getByRole("heading", { name: heading, exact: true }),
      `read-side section missing: ${heading}`,
    ).toBeVisible();
  }
  for (const [heading, source, evidence] of [
    ["Search evidence", "GSC", intelligence.gsc],
    ["Conversion and content", "GA4", intelligence.ga4_organic_landing],
  ] as const) {
    const card = panel.locator(".ui-card").filter({
      has: page.getByRole("heading", { name: heading, exact: true }),
    });
    await expect(
      card,
      `${source} availability differs from backend`,
    ).toContainText(statusLabel(String(evidence.availability)));
    if (typeof evidence.limitation === "string" && evidence.limitation)
      await expect(card, `${source} limitation hidden`).toContainText(
        evidence.limitation,
      );
  }
  const decision = selected.recommendation?.decision_context;
  if (selected.recommendation) {
    const decisionCard = panel.locator(".ui-card").filter({
      has: page.getByRole("heading", { name: "Decision", exact: true }),
    });
    await expect(
      decisionCard,
      "recommendation state differs from backend",
    ).toContainText(statusLabel(selected.recommendation.status));
  }
  if (decision) {
    for (const [name, key] of [
      ["Access", "access"],
      ["Competition", "competition"],
      ["Answer Engines", "answer_engines"],
      ["Conversion", "conversion"],
    ] as const) {
      const card = panel
        .locator(".ui-card")
        .filter({ has: page.getByRole("heading", { name, exact: true }) });
      await expect(card, `Hermes ${name} pass mismatch`).toContainText(
        statusLabel(decision.passes[key].availability),
      );
      if (decision.passes[key].availability === "unavailable") {
        expect(
          decision.passes[key].limitation,
          `Hermes ${name} unavailable without persisted limitation`,
        ).toBeTruthy();
        await expect(card, `Hermes ${name} limitation hidden`).toContainText(
          decision.passes[key].limitation!,
        );
      }
    }
    await expect(
      panel.getByText(statusLabel(decision.business_importance_state), {
        exact: true,
      }),
      "browser business importance differs from persisted decision",
    ).toBeVisible();
  }
  if (selected.task) {
    await expect(
      panel
        .getByText(statusLabel(selected.task.status), { exact: true })
        .first(),
      "implementation status mismatch",
    ).toBeVisible();
    const verification = selected.task.verification_evidence;
    if (verification && typeof verification.result === "string") {
      const implementationCard = panel.locator(".ui-card").filter({
        has: page.getByRole("heading", {
          name: "Implementation and verification",
          exact: true,
        }),
      });
      await expect(
        implementationCard,
        "verification result differs from backend",
      ).toContainText(statusLabel(verification.result));
    }
  }
  if (selected.measurement)
    await expect(
      panel.locator(".ui-card").filter({
        has: page.getByRole("heading", {
          name: "Measurement and observed outcome",
          exact: true,
        }),
      }),
      "measurement maturity differs from backend",
    ).toContainText(
      selected.outcome
        ? "Outcome recorded"
        : statusLabel(selected.measurement.maturity),
    );
  if (selected.outcome)
    await expect(
      panel
        .getByText(statusLabel(selected.outcome.classification), {
          exact: true,
        })
        .first(),
      "outcome status mismatch",
    ).toBeVisible();
  expect(
    blockedWrites,
    `production mutation attempted: ${blockedWrites.join(", ")}`,
  ).toEqual([]);
});
