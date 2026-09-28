import { expect, test } from "@playwright/test";

const organization = "11111111-1111-4111-8111-111111111111";
const opportunity = "22222222-2222-4222-8222-222222222222";

test("selected opportunity shows Hermes completion, review, and a failed revision run", async ({
  page,
}) => {
  test.skip(
    process.env.PUBLIC_LILOS_API_BASE_URL !== "http://127.0.0.1:8765" ||
      process.env.PUBLIC_LILOS_SUPABASE_URL !== "http://127.0.0.1:8766" ||
      process.env.PUBLIC_LILOS_SUPABASE_ANON_KEY !== "browser-fixture-key",
    "This mocked operator journey runs only with its isolated local browser fixture.",
  );
  await page.addInitScript(() => {
    const now = Math.floor(Date.now() / 1000);
    localStorage.setItem(
      "sb-127-auth-token",
      JSON.stringify({
        access_token: "browser-fixture-token",
        refresh_token: "browser-fixture-refresh",
        token_type: "bearer",
        expires_in: 3600,
        expires_at: now + 3600,
        user: {
          id: "33333333-3333-4333-8333-333333333333",
          app_metadata: {},
          user_metadata: {},
          aud: "authenticated",
          created_at: new Date().toISOString(),
        },
      }),
    );
  });
  let submissions = 0;
  let reads = 0;
  await page.route("http://127.0.0.1:8765/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    let data: unknown = [];
    if (path === "/api/v1/me")
      data = {
        platform_user_id: "user",
        auth_user_id: "user",
        user_status: "active",
        assurance_level: "aal2",
      };
    else if (path === "/api/v1/me/organizations")
      data = [
        {
          organization_id: organization,
          organization_name: "Example",
          organization_slug: "example",
          organization_status: "active",
          membership_id: "membership",
          membership_status: "active",
          membership_type: "internal",
        },
      ];
    else if (path.endsWith("/platform-administrator"))
      data = {
        is_platform_administrator: false,
        meets_required_assurance: false,
      };
    else if (path.endsWith("/products"))
      data = [{ product_key: "seo", entitled: true }];
    else if (path.endsWith("/seo/summary")) data = { crawl_run_count: 0 };
    else if (path.endsWith("/seo/websites")) data = [];
    else if (path.endsWith("/seo/opportunities")) data = [];
    else if (path.endsWith(`/opportunities/${opportunity}/recommendations`))
      data = [
        {
          id: "revision",
          revision_number: 1,
          proposed_action: "Investigate local service demand",
          expected_result_hypothesis: "Clarify the right landing page",
          risk: "low",
          effort: "medium",
          status: "awaiting_approval",
          approved_by_user_id: null,
          evidence_references: [],
          decision_context: null,
        },
      ];
    else if (path.endsWith("/seo/workspace"))
      data = {
        items: [
          {
            opportunity: {
              id: opportunity,
              website_id: "site",
              page_id: null,
              opportunity_type: "gsc_query_demand",
              recommendation_class: "growth_change",
              priority_score: 65,
              score_explanation: {},
              evidence: {
                query: "local services",
                page_mapping_state: "unknown",
              },
              status: "identified",
            },
            website: {
              id: "site",
              location_id: "location",
              key: "site",
              name: "Example",
              canonical_origin: "https://example.test",
              status: "active",
              ownership_status: "verified",
              verified_at: null,
            },
            page: null,
            recommendation: null,
            task: null,
            outcome: null,
            measurement: null,
            active_change: null,
            latest_measured: null,
          },
        ],
        readiness: [
          {
            website_id: "site",
            website_name: "Example",
            location_id: "location",
            gsc: "fresh",
            ga4: "unavailable",
            page_inventory: "unavailable",
          },
        ],
        readiness_has_more: false,
        history_truncated: false,
        pagination: {
          limit: 50,
          offset: 0,
          next_offset: null,
          has_more: false,
        },
      };
    else if (path.endsWith(`/opportunities/${opportunity}/hermes-run`)) {
      if (route.request().method() === "POST") {
        submissions += 1;
        reads = 0;
        data = {
          workflow_run_id: `workflow-${submissions}`,
          agent_run_id: null,
          status: "queued",
          safe_error_code: null,
          proposal_references: [],
        };
      } else {
        reads += 1;
        data =
          submissions === 0
            ? null
            : {
                workflow_run_id: `workflow-${submissions}`,
                agent_run_id: "agent",
                status:
                  reads === 1
                    ? "running"
                    : submissions === 1
                      ? "completed"
                      : "failed",
                safe_error_code:
                  submissions === 2 && reads > 1
                    ? "SEO_RECOMMENDATION_MISSING"
                    : null,
                proposal_references:
                  submissions === 1 && reads > 1
                    ? ["seo-recommendation:revision"]
                    : [],
              };
      }
    }
    await route.fulfill({
      status: 200,
      headers: {
        "access-control-allow-origin": "*",
        "content-type": "application/json",
      },
      body: JSON.stringify({ data }),
    });
  });
  await page.goto("/seo");
  await page
    .locator("#tab-intelligence")
    .getByRole("button", { name: "Review" })
    .first()
    .click();
  const ask = page.getByRole("button", { name: "Ask Hermes", exact: true });
  await expect(ask).toBeEnabled();
  await ask.click();
  await expect(
    page.getByRole("status").filter({ hasText: "Hermes reasoning: Queued" }),
  ).toBeVisible();
  await expect(ask).toBeDisabled();
  await expect(
    page.getByRole("status").filter({ hasText: "Hermes reasoning: Running" }),
  ).toBeVisible();
  expect(submissions).toBe(1);
  await expect(
    page.getByRole("button", { name: "Ask Hermes to revise" }),
  ).toBeVisible({ timeout: 10_000 });
  await expect(
    page.getByText("Investigate local service demand"),
  ).toBeVisible();
  await expect(page.getByText("Clarify the right landing page")).toBeVisible();
  await expect(page.getByText("Revision", { exact: true })).toBeVisible();
  await expect(page.getByText("Awaiting approval")).toBeVisible();
  const revise = page.getByRole("button", { name: "Ask Hermes to revise" });
  await revise.click();
  await expect(revise).toBeDisabled();
  await expect(
    page
      .getByRole("status")
      .filter({ hasText: "Hermes reasoning Needs attention" }),
  ).toContainText("No valid recommendation was created", { timeout: 10_000 });
  expect(submissions).toBe(2);
});
