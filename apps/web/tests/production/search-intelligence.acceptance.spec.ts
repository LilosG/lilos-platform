/**
 * Read-only Search Intelligence production acceptance. Execute only for an
 * authorized fixture after production:auth has saved its operator session.
 * Required: LILOS_PRODUCTION_ACCEPTANCE_ORG_NAME,
 * LILOS_SEARCH_ACCEPTANCE_ORG_ID, LILOS_SEARCH_ACCEPTANCE_LOCATION_ID,
 * LILOS_SEARCH_ACCEPTANCE_WEBSITE_ID. Optional: LILOS_SEARCH_ACCEPTANCE_PAGE_ID.
 * Run explicitly with npm run production:search-intelligence.
 */
import { expect, test, type Locator, type Page } from "@playwright/test";
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
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);
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
  opportunityId: process.env.LILOS_SEARCH_ACCEPTANCE_OPPORTUNITY_ID?.trim(),
  recommendationId:
    process.env.LILOS_SEARCH_ACCEPTANCE_RECOMMENDATION_ID?.trim(),
};

type ApiResponse<T> = { status: number; data?: T; error?: string };

async function authenticatedFetch<T>(
  page: Page,
  route: string,
): Promise<ApiResponse<{ data: T }>> {
  return page.evaluate(
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
  ) as Promise<ApiResponse<{ data: T }>>;
}

async function refreshSession(page: Page): Promise<boolean> {
  return page.evaluate(async () => {
    const key = Object.keys(localStorage).find(
      (value) => value.startsWith("sb-") && value.endsWith("-auth-token"),
    );
    if (!key) return false;
    try {
      const session = JSON.parse(localStorage.getItem(key) ?? "{}");
      if (!session.refresh_token) return false;
      const projectRef = key.replace(/^sb-/, "").replace(/-auth-token$/, "");
      const response = await fetch(
        `https://${projectRef}.supabase.co/auth/v1/token?grant_type=refresh_token`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: session.refresh_token }),
        },
      );
      if (!response.ok) return false;
      localStorage.setItem(key, JSON.stringify(await response.json()));
      return true;
    } catch {
      return false;
    }
  });
}

async function get<T>(page: Page, route: string, layer: string): Promise<T> {
  let result = await authenticatedFetch<T>(page, route);
  if (result.status === 401) {
    if (!(await refreshSession(page)))
      throw new Error(
        `${layer}: authentication unavailable; saved session could not be refreshed`,
      );
    result = await authenticatedFetch<T>(page, route);
  }
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

function card(page: Page, panel: Locator, title: string): Locator {
  return panel.locator("section.ui-card").filter({
    has: page.getByRole("heading", { name: title, exact: true }),
  });
}

function fact(card: Locator, label: string): Locator {
  return card.getByText(label, { exact: true }).locator("..").locator("span");
}

function workspacePath(
  base: string,
  websiteId: string,
  offset: number,
): string {
  return `${base}/seo/workspace?website_id=${encodeURIComponent(websiteId)}&limit=50&offset=${offset}`;
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
      !SAFE_METHODS.has(request.method())
    ) {
      blockedWrites.push(`${request.method()} ${request.url()}`);
      await route.abort("blockedbyclient");
      return;
    }
    await route.continue();
  });
  await page.goto(`${WEB_BASE}/`, { waitUntil: "domcontentloaded" });
  const base = `/api/v1/organizations/${target.organizationId}`;
  const memberships = await get<
    Array<{ organization_id: string; organization_name: string }>
  >(page, "/api/v1/me/organizations", "organization scope");
  const membership = memberships.find(
    (row) => row.organization_id === target.organizationId,
  );
  if (!membership)
    throw new Error(
      "Search Intelligence UI prerequisite unavailable: the configured acceptance organization is not present in the operator workspace memberships. The current product workspace cannot select a platform-admin-only organization.",
    );
  expect(
    membership.organization_name.trim().replace(/\s+/g, " ").toLowerCase(),
    "acceptance organization ID/name mismatch",
  ).toBe(target.organizationName.trim().replace(/\s+/g, " ").toLowerCase());

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
  ).toHaveText(membership.organization_name);

  const location = await get<{ id: string; organization_id: string }>(
    page,
    `${base}/locations/${target.locationId}`,
    "location scope",
  );
  expect(location.id, "location identity mismatch").toBe(target.locationId);
  expect(location.organization_id, "location organization mismatch").toBe(
    target.organizationId,
  );
  const website = await get<SEOWebsite>(
    page,
    `${base}/seo/websites/${target.websiteId}`,
    "website identity",
  );
  expect(website.id, "website identity mismatch").toBe(target.websiteId);
  expect(website.location_id, "website location mismatch").toBe(
    target.locationId,
  );
  expect(website.canonical_origin, "website origin missing").toBeTruthy();

  const workspace = await get<SearchIntelligenceWorkspace>(
    page,
    workspacePath(base, target.websiteId, 0),
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
    has: page.getByRole("heading", { name: website.name, exact: true }),
  });
  await expect(
    siteReadiness,
    "website identity absent from UI readiness",
  ).toBeVisible();
  await expect(
    fact(siteReadiness, "Organization/location"),
    "readiness location label mismatch",
  ).toHaveText("Resolved");
  await expect(
    fact(siteReadiness, "GSC mapping and freshness"),
    "GSC readiness label mismatch",
  ).toHaveText(statusLabel(readiness!.gsc));
  await expect(
    fact(siteReadiness, "GA4 mapping and freshness"),
    "GA4 readiness label mismatch",
  ).toHaveText(statusLabel(readiness!.ga4));
  await expect(
    fact(siteReadiness, "Page inventory"),
    "page inventory label mismatch",
  ).toHaveText(statusLabel(readiness!.page_inventory));
  if (workspace.history_truncated) {
    await expect(
      panel.getByText(
        "Older recommendation or implementation history exceeds this bounded view.",
        { exact: false },
      ),
      "history truncation hidden in UI",
    ).toBeVisible();
    throw new Error(
      "Search Intelligence workspace history truncated; live read acceptance cannot complete for this fixture",
    );
  }
  const items: SearchIntelligenceItem[] = [...workspace.items];
  let next = workspace.pagination.next_offset;
  const matchesPage = (item: SearchIntelligenceItem): boolean =>
    item.website.id === target.websiteId &&
    (target.pageId ? item.page?.id === target.pageId : Boolean(item.page));
  for (
    let count = 0;
    next !== null && !items.some(matchesPage) && count < 20;
    count += 1
  ) {
    const batch = await get<SearchIntelligenceWorkspace>(
      page,
      workspacePath(base, target.websiteId, next),
      "workspace pagination",
    );
    if (batch.history_truncated)
      throw new Error(
        `Search Intelligence workspace history truncated at offset ${next}; live read acceptance cannot complete`,
      );
    items.push(...batch.items);
    next = batch.pagination.next_offset;
  }
  if (!items.some(matchesPage) && next !== null)
    throw new Error(
      "Scoped workspace page fixture not found within the bounded 20-page acceptance scan",
    );
  for (const item of items) {
    expect(item.website.id, "workspace returned another website").toBe(
      target.websiteId,
    );
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
  const candidates = items.filter(matchesPage);
  const selected =
    candidates.find((item) => !item.outcome && !item.task?.verified_at) ??
    candidates[0];
  if (!selected?.page) {
    console.log(
      `No page-backed opportunity on website ${target.websiteId}; canonical page inventory is covered by the separate page journey.`,
    );
    expect(blockedWrites).toEqual([]);
    return;
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
    if (evidence.availability === "unavailable")
      expect(
        typeof evidence.limitation === "string"
          ? evidence.limitation.trim()
          : "",
        `${source} unavailable without persisted limitation`,
      ).not.toBe("");
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
  const displayedSummary =
    listSection === "Completed / Learned"
      ? `Observed after this change: ${statusLabel(selected.latest_measured?.outcome.classification)}.`
      : listSection === "Currently Measuring"
        ? `${statusLabel(selected.measurement?.maturity)} · ${selected.measurement?.metric || "Metric unavailable"}`
        : `${statusLabel(selected.opportunity.opportunity_type)} · Priority ${selected.opportunity.priority_score}`;
  const row = panel
    .locator("section.ui-card")
    .filter({
      has: page.getByRole("heading", { name: listSection, exact: true }),
    })
    .locator("ul.ui-record-list > li")
    .filter({
      has: page.getByRole("heading", {
        name: `${website.name} · ${pagePath}`,
        exact: true,
      }),
    })
    .filter({ has: page.getByText(displayedSummary, { exact: true }) });
  let uiOffset = 0;
  for (
    let pageNumber = 0;
    (await row.count()) === 0 && pageNumber < 20;
    pageNumber += 1
  ) {
    const nextButton = panel.getByRole("button", { name: "Next 50" });
    if (!(await nextButton.isVisible())) break;
    const expectedOffset = uiOffset + 50;
    const loading = panel.getByText("Loading Search Intelligence work…", {
      exact: true,
    });
    const loadingVisible = loading.waitFor({ state: "visible" });
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
    await loadingVisible;
    const response = await nextWorkspaceResponse;
    expect(
      response.ok(),
      `Search Intelligence workspace page offset ${expectedOffset} failed: HTTP ${response.status()}`,
    ).toBe(true);
    await loading.waitFor({ state: "hidden" });
    await expect(
      panel.getByRole("navigation", { name: "Search Intelligence work pages" }),
      "workspace pagination did not settle",
    ).toBeVisible();
    uiOffset = expectedOffset;
  }
  const matchingRows = await row.count();
  expect(
    matchingRows,
    "resolved page work item absent from deployed workspace UI",
  ).toBeGreaterThan(0);
  expect(
    matchingRows,
    "resolved page work item is ambiguous in deployed workspace UI",
  ).toBe(1);
  await expect(row).toBeVisible();
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
  const pageIdentity = card(page, panel, "Page identity");
  await expect(
    pageIdentity,
    "Page Intelligence unavailable in UI",
  ).toBeVisible();
  await expect(
    fact(pageIdentity, "Canonical page"),
    "UI/backend page URL mismatch",
  ).toHaveText(selected.page.normalized_url);
  await expect(
    fact(pageIdentity, "Website"),
    "UI/backend website identity mismatch",
  ).toHaveText(target.websiteId);
  await expect(
    fact(pageIdentity, "Page"),
    "UI/backend page identity mismatch",
  ).toHaveText(selected.page.id);
  const opportunityCard = card(page, panel, `${website.name} · ${pagePath}`);
  await expect(
    fact(opportunityCard, "Priority"),
    "browser priority differs from backend",
  ).toHaveText(String(selected.opportunity.priority_score));
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
    const evidenceCard = card(page, panel, heading);
    await expect(
      fact(evidenceCard, source === "GSC" ? "GSC" : "GA4 Organic Landing"),
      `${source} availability differs from backend`,
    ).toHaveText(statusLabel(String(evidence.availability)));
    if (typeof evidence.limitation === "string" && evidence.limitation)
      await expect(evidenceCard, `${source} limitation hidden`).toContainText(
        evidence.limitation,
      );
    const properties =
      (
        evidence.properties as
          { items?: Array<{ freshness?: string }> } | undefined
      )?.items ?? [];
    await expect(
      fact(evidenceCard, source === "GSC" ? "GSC freshness" : "GA4 freshness"),
      `${source} page freshness differs from backend`,
    ).toHaveText(statusLabel(properties[0]?.freshness));
  }
  const queryOnly =
    (intelligence.gsc.website_query_only as { items?: unknown[] } | undefined)
      ?.items ?? [];
  await expect(
    fact(card(page, panel, "Search evidence"), "Query-only demand"),
    "query-only demand attribution differs from backend",
  ).toHaveText(`${queryOnly.length} website-scoped records`);
  const decision = selected.recommendation?.decision_context;
  const decisionCard = card(page, panel, "Decision");
  if (selected.recommendation) {
    await expect(
      fact(decisionCard, "Approval"),
      "recommendation state differs from backend",
    ).toHaveText(statusLabel(selected.recommendation.status));
  } else {
    await expect(
      decisionCard.getByRole("button", {
        name: "Submit recommendation for approval",
      }),
      "missing-recommendation state hidden",
    ).toBeVisible();
    await expect(
      decisionCard.getByText("Approval", { exact: true }),
      "invented recommendation approval",
    ).toHaveCount(0);
  }
  await expect(
    fact(decisionCard, "Business importance"),
    "decision business importance mismatch",
  ).toHaveText(statusLabel(decision?.business_importance_state));
  if (decision) {
    for (const [name, key] of [
      ["Access", "access"],
      ["Competition", "competition"],
      ["Answer Engines", "answer_engines"],
      ["Conversion", "conversion"],
    ] as const) {
      const passCard = card(page, panel, name);
      await expect(
        fact(passCard, "Availability"),
        `Hermes ${name} pass mismatch`,
      ).toHaveText(statusLabel(decision.passes[key].availability));
      if (decision.passes[key].availability === "unavailable") {
        expect(
          decision.passes[key].limitation,
          `Hermes ${name} unavailable without persisted limitation`,
        ).toBeTruthy();
        await expect(
          passCard,
          `Hermes ${name} limitation hidden`,
        ).toContainText(decision.passes[key].limitation!);
      }
    }
  } else {
    for (const name of [
      "Access",
      "Competition",
      "Answer Engines",
      "Conversion",
    ]) {
      const passCard = card(page, panel, name);
      await expect(
        fact(passCard, "Availability"),
        `Hermes ${name} absence mismatch`,
      ).toHaveText("Unavailable");
      await expect(
        passCard,
        `Hermes ${name} absence limitation hidden`,
      ).toContainText(
        "A governed recommendation has not recorded this reasoning pass.",
      );
    }
  }
  const implementationCard = card(page, panel, "Implementation and verification");
  if (selected.task) {
    await expect(
      fact(implementationCard, "Task"),
      "implementation status mismatch",
    ).toHaveText(statusLabel(selected.task.status));
    const verification = selected.task.verification_evidence;
    await expect(
      fact(implementationCard, "Verification result"),
      "verification result differs from backend",
    ).toHaveText(
      typeof verification?.result === "string" && verification.result.trim()
        ? statusLabel(verification.result)
        : "Unavailable",
    );
  } else {
    await expect(
      fact(implementationCard, "Task"),
      "missing implementation task was invented",
    ).toHaveText("Not delegated");
    await expect(
      fact(implementationCard, "Verification result"),
      "missing verification was invented",
    ).toHaveText("Unavailable");
  }
  const measurementCard = card(page, panel, "Measurement and observed outcome");
  const outcome = selected.outcome ?? selected.latest_measured?.outcome;
  await expect(
    fact(measurementCard, "Maturity"),
    "measurement maturity differs from backend",
  ).toHaveText(
    outcome ? "Outcome recorded" : statusLabel(selected.measurement?.maturity),
  );
  await expect(
    fact(measurementCard, "Observed after this change"),
    "outcome state differs from backend",
  ).toHaveText(outcome ? statusLabel(outcome.classification) : "Pending");
  if (!outcome && !selected.measurement)
    await expect(
      fact(measurementCard, "Metric"),
      "missing measurement was invented",
    ).toHaveText("Unavailable");
  expect(
    blockedWrites,
    `production mutation attempted: ${blockedWrites.join(", ")}`,
  ).toEqual([]);
});

test("approved unattributed work and canonical page inventory stay truthful", async ({
  page,
}) => {
  const target = requireFixture();
  if (!fixture.opportunityId || !fixture.recommendationId)
    throw new Error(
      "Set LILOS_SEARCH_ACCEPTANCE_OPPORTUNITY_ID and LILOS_SEARCH_ACCEPTANCE_RECOMMENDATION_ID for the approved read-only journey.",
    );
  const blockedWrites: string[] = [];
  await page.route("**/*", async (route) => {
    const request = route.request();
    if (
      [API_BASE, WEB_BASE].includes(new URL(request.url()).origin) &&
      !SAFE_METHODS.has(request.method())
    ) {
      blockedWrites.push(`${request.method()} ${request.url()}`);
      await route.abort("blockedbyclient");
      return;
    }
    await route.continue();
  });
  await page.goto(`${WEB_BASE}/seo?org=${target.organizationId}`, {
    waitUntil: "domcontentloaded",
  });
  const base = `/api/v1/organizations/${target.organizationId}`;
  const workspace = await get<SearchIntelligenceWorkspace>(
    page,
    workspacePath(base, target.websiteId, 0),
    "approved work scope",
  );
  expect(
    workspace.pagination.next_offset,
    "approved fixture requires pagination",
  ).toBeNull();
  const item = workspace.items.find(
    (candidate) => candidate.opportunity.id === fixture.opportunityId,
  );
  expect(
    item,
    "approved opportunity absent from website workspace",
  ).toBeDefined();
  expect(item!.website.id).toBe(target.websiteId);
  expect(item!.website.location_id).toBe(target.locationId);
  expect(item!.opportunity.page_id).toBeNull();
  expect(item!.page).toBeNull();
  expect(item!.opportunity.priority_score).toBe(89);
  expect(item!.governed_eligibility.eligible).toBe(true);
  expect(item!.recommendation?.id).toBe(fixture.recommendationId);
  expect(item!.recommendation?.revision_number).toBe(2);
  expect(item!.recommendation?.status).toBe("approved");
  expect(item!.recommendation?.decision_context?.page_mapping_state).toBe(
    "unknown",
  );
  expect(
    item!.recommendation?.decision_context?.business_importance_state,
  ).toBe("unavailable");
  const recommendations = await get<
    Array<SearchIntelligenceItem["recommendation"]>
  >(
    page,
    `${base}/seo/opportunities/${fixture.opportunityId}/recommendations`,
    "recommendation history",
  );
  expect(recommendations.map((record) => record?.revision_number)).toEqual([
    2, 1,
  ]);
  expect(recommendations[0]?.id).toBe(fixture.recommendationId);
  expect(recommendations[0]?.approved_by_user_id).toBeTruthy();
  expect(recommendations[1]?.status).toBe("awaiting_approval");
  const handoff = (
    recommendations[0] as (typeof recommendations)[0] & {
      growth_handoff?: {
        opportunity_reference: string;
        target_reference: string;
        website_id: string;
        location_id: string;
        page_mapping_state: string;
        approval_state: string;
      };
    }
  )?.growth_handoff;
  expect(handoff?.opportunity_reference).toBe(
    `seo-opportunity:${fixture.opportunityId}`,
  );
  expect(handoff?.target_reference).toBe(
    `seo-opportunity:${fixture.opportunityId}`,
  );
  expect(handoff?.website_id).toBe(target.websiteId);
  expect(handoff?.location_id).toBe(target.locationId);
  expect(handoff?.page_mapping_state).toBe("unknown");
  expect(handoff?.approval_state).toBe("approved");
  const tasks = await get<Array<NonNullable<SearchIntelligenceItem["task"]>>>(
    page,
    `${base}/seo/recommendations/${fixture.recommendationId}/tasks`,
    "downstream implementation",
  );
  expect(tasks).toHaveLength(1);
  expect(tasks[0].recommendation_revision_id).toBe(fixture.recommendationId);
  expect(tasks[0].target_type).toBe("opportunity");
  expect(tasks[0].target_reference).toBe(
    `seo-opportunity:${fixture.opportunityId}`,
  );
  expect(tasks[0].status).toBe("verification_pending");
  expect(tasks[0].verified_at).toBeNull();
  expect(tasks[0].verification_evidence?.result).toBe("unavailable");
  expect(tasks[0].verification_evidence?.page_id).toBeNull();
  expect(tasks[0].verification_evidence?.actual).toEqual({});
  expect(item!.outcome).toBeNull();
  expect(item!.measurement?.maturity).toBe("unavailable");

  const panel = page.locator("#tab-intelligence");
  await expect(panel.getByText("Acceptance journey readiness")).toBeVisible();
  await expect(page.locator("h1"), "duplicate page heading").toHaveCount(1);
  for (const heading of [
    "Requires Attention",
    "Growth Opportunities",
    "Technical Regressions",
    "Currently Measuring",
    "Completed / Learned",
  ])
    await expect(card(page, panel, heading)).toBeVisible();
  const attention = card(page, panel, "Requires Attention");
  const approvedRow = attention.locator(
    `li[data-opportunity-id="${fixture.opportunityId}"]`,
  );
  await expect(approvedRow).toContainText("Target resolution required");
  await expect(approvedRow).toContainText("authoritative mapped evidence");
  const invalid = workspace.items.find(
    (candidate) => !candidate.governed_eligibility.eligible,
  );
  if (invalid) {
    const invalidRow = attention.locator(
      `li[data-opportunity-id="${invalid.opportunity.id}"]`,
    );
    await expect(invalidRow).toContainText(
      "before requesting a recommendation",
    );
    await invalidRow.getByRole("button", { name: "Review" }).click();
    await expect(
      panel.getByRole("button", { name: "Ask Hermes", exact: true }),
    ).toHaveCount(0);
    await panel.getByRole("button", { name: "Back to workspace" }).click();
  }
  const growthRow = card(page, panel, "Growth Opportunities").locator(
    `li[data-opportunity-id="${fixture.opportunityId}"]`,
  );
  await expect(growthRow).toContainText("Priority 89");
  await expect(growthRow).toContainText("Business importance: Unavailable");
  await expect(growthRow).toContainText("Approved");
  await approvedRow.getByRole("button", { name: "Review" }).click();
  await expect(panel.getByText("Page attribution unavailable")).toBeVisible();
  await expect(
    panel.getByText("Target resolution required", { exact: false }),
  ).toBeVisible();
  await expect(fact(card(page, panel, "Decision"), "Revision")).toHaveText("2");
  await expect(fact(card(page, panel, "Decision"), "Approval")).toHaveText(
    "Approved",
  );
  for (const [name, key] of [
    ["Access", "access"],
    ["Competition", "competition"],
    ["Answer Engines", "answer_engines"],
    ["Conversion", "conversion"],
  ] as const) {
    const pass = item!.recommendation!.decision_context!.passes[key];
    await expect(fact(card(page, panel, name), "Availability")).toHaveText(
      statusLabel(pass.availability),
    );
    if (pass.limitation)
      await expect(card(page, panel, name)).toContainText(pass.limitation);
  }
  await expect(
    fact(card(page, panel, "Implementation and verification"), "Task"),
  ).toHaveText("Verification Pending");
  await expect(
    fact(card(page, panel, "Implementation and verification"), "Verified at"),
  ).toHaveText("Unavailable");
  await expect(
    fact(card(page, panel, "Measurement and observed outcome"), "Maturity"),
  ).toHaveText("Unavailable");
  await expect(
    fact(
      card(page, panel, "Measurement and observed outcome"),
      "Observed after this change",
    ),
  ).toHaveText("Pending");

  const runs = await get<Array<{ id: string; status: string }>>(
    page,
    `${base}/seo/crawl-runs?website_id=${target.websiteId}&limit=20`,
    "canonical crawl inventory",
  );
  const run = runs.find((candidate) => candidate.status === "success");
  expect(run, "no completed crawl for canonical page inventory").toBeDefined();
  const pages = await get<
    Array<{ id: string; website_id: string; normalized_url: string }>
  >(page, `${base}/seo/crawl-runs/${run!.id}/pages`, "canonical pages");
  const selectedPage = target.pageId
    ? pages.find((candidate) => candidate.id === target.pageId)
    : pages[0];
  expect(selectedPage, "no resolved page in completed crawl").toBeDefined();
  const intelligence = await get<SEOPageIntelligence>(
    page,
    `${base}/seo/websites/${target.websiteId}/pages/${selectedPage!.id}/intelligence`,
    "resolved Page Intelligence",
  );
  expect(intelligence.identity.organization_id).toBe(target.organizationId);
  expect(intelligence.identity.website_id).toBe(target.websiteId);
  expect(intelligence.identity.page_id).toBe(selectedPage!.id);
  expect(intelligence.identity.normalized_url).toBe(
    selectedPage!.normalized_url,
  );
  await page
    .locator("#seo-tabs .ui-tabs__tab")
    .filter({ hasText: "Crawl" })
    .click();
  const inspect = page.getByRole("button", {
    name: `Inspect page ${selectedPage!.normalized_url}`,
    exact: true,
  });
  await expect(inspect).toBeVisible();
  await inspect.click();
  const identity = page
    .locator("#tab-crawl")
    .locator("section.ui-card")
    .filter({
      has: page.getByRole("heading", { name: "Page identity", exact: true }),
    });
  await expect(fact(identity, "Canonical page")).toHaveText(
    selectedPage!.normalized_url,
  );
  await expect(fact(identity, "Website")).toHaveText(target.websiteId);
  await expect(fact(identity, "Page")).toHaveText(selectedPage!.id);
  for (const [heading, label, evidence] of [
    ["Search evidence", "GSC", intelligence.gsc],
    [
      "Conversion and content",
      "GA4 Organic Landing",
      intelligence.ga4_organic_landing,
    ],
  ] as const) {
    const evidenceCard = page
      .locator("#tab-crawl")
      .locator("section.ui-card")
      .filter({
        has: page.getByRole("heading", { name: heading, exact: true }),
      });
    await expect(fact(evidenceCard, label)).toHaveText(
      statusLabel(String(evidence.availability)),
    );
    if (evidence.limitation)
      await expect(evidenceCard).toContainText(String(evidence.limitation));
  }
  const wrongId = "00000000-0000-4000-8000-000000000001";
  for (const [scope, route] of [
    [
      "organization",
      `/api/v1/organizations/${wrongId}/seo/opportunities/${fixture.opportunityId}`,
    ],
    ["location", `${base}/locations/${wrongId}`],
    ["website", `${base}/seo/websites/${wrongId}`],
    [
      "page",
      `${base}/seo/websites/${target.websiteId}/pages/${wrongId}/intelligence`,
    ],
    [
      "recommendation",
      `/api/v1/organizations/${wrongId}/seo/recommendations/${fixture.recommendationId}/tasks`,
    ],
  ] as const) {
    const response = await authenticatedFetch(page, route);
    expect([403, 404], `${scope} scope unexpectedly readable`).toContain(
      response.status,
    );
  }
  expect(blockedWrites).toEqual([]);
});
