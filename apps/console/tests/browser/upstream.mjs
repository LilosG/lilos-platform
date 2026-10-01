// Isolated HTTP simulator. Production loaders/session/BFF remain the code under test.
import { createServer } from "node:http";
const ids = {
  a: "11111111-1111-4111-8111-111111111111",
  b: "22222222-2222-4222-8222-222222222222",
  opp: "33333333-3333-4333-8333-333333333333",
  page: "44444444-4444-4444-8444-444444444444",
  rev: "55555555-5555-4555-8555-555555555555",
  next: "66666666-6666-4666-8666-666666666666",
  factor: "77777777-7777-4777-8777-777777777777",
  run: "88888888-8888-4888-8888-888888888888",
};
const raceCounts = new Map();
let revision = ids.rev;
let approved = false;
let factors = [];
let proposal =
  "A protected synthetic description proposed for this exact page.";
const user = (id) => ({
  id,
  aud: "authenticated",
  role: "authenticated",
  email: id === ids.a ? "a@example.test" : "b@example.test",
  app_metadata: {},
  user_metadata: {},
  factors,
  created_at: "2026-09-30T00:00:00Z",
});
const token = (id, aal = "aal1", expired = false) =>
  [
    Buffer.from(JSON.stringify({ alg: "HS256", typ: "JWT" })).toString(
      "base64url",
    ),
    Buffer.from(
      JSON.stringify({
        sub: id,
        aud: "authenticated",
        role: "authenticated",
        aal,
        session_id: ids.run,
        iat: Math.floor(Date.now() / 1000) - 10,
        exp: Math.floor(Date.now() / 1000) + (expired ? -5 : 3600),
      }),
    ).toString("base64url"),
    "c3ludGhldGljLXNpZ25hdHVyZQ",
  ].join(".");
const session = (id, aal = "aal1") => ({
  access_token: token(id, aal),
  refresh_token: `refresh-${id}`,
  token_type: "bearer",
  expires_in: 3600,
  user: user(id),
});
createServer(async (req, res) => {
  const url = new URL(req.url, "http://127.0.0.1:4455");
  let body = "";
  for await (const chunk of req) body += chunk;
  const parsed = body ? JSON.parse(body) : {};
  let claims;
  try {
    claims = JSON.parse(
      Buffer.from(
        (req.headers.authorization ?? "").split(" ")[1].split(".")[1],
        "base64url",
      ).toString(),
    );
  } catch {
    claims = {};
  }
  const reply = (data, status = 200) => {
    res.writeHead(status, { "Content-Type": "application/json" });
    res.end(JSON.stringify(data));
  };
  if (url.pathname === "/health") return reply({ ok: true });
  if (url.pathname === "/auth/v1/token") {
    if (parsed.refresh_token?.startsWith("race-")) {
      const key = parsed.refresh_token;
      const count = raceCounts.get(key) ?? 0;
      raceCounts.set(key, count + 1);
      const success = count === 0;
      const successFirst = key.endsWith("fast");
      await new Promise((resolve) =>
        setTimeout(resolve, success === successFirst ? 20 : 100),
      );
      return success
        ? reply(session(ids.a))
        : reply(
            { msg: "Refresh Token Not Found", code: "refresh_token_not_found" },
            400,
          );
    }

    if (url.searchParams.get("grant_type") === "refresh_token")
      return reply(
        session(parsed.refresh_token?.includes(ids.b) ? ids.b : ids.a),
      );
    if (parsed.password !== "synthetic-password")
      return reply(
        { msg: "Invalid login credentials", code: "invalid_credentials" },
        400,
      );
    revision = ids.rev;
    approved = false;
    factors = [];
    return reply(session(parsed.email === "a@example.test" ? ids.a : ids.b));
  }
  if (url.pathname === "/auth/v1/user")
    return claims.sub
      ? reply(user(claims.sub))
      : reply({ msg: "Unauthorized" }, 401);
  if (url.pathname === "/auth/v1/logout") return reply({});
  if (url.pathname === "/auth/v1/factors" && req.method === "GET")
    return reply({
      all: factors,
      totp: factors.filter((f) => f.status === "verified"),
      phone: [],
    });
  if (url.pathname === "/auth/v1/factors" && req.method === "POST") {
    const factor = {
      id: ids.factor,
      factor_type: "totp",
      status: "unverified",
      friendly_name: "Synthetic authenticator",
    };
    factors = [factor];
    return reply({
      ...factor,
      totp: {
        secret: "SYNTHETICSETUPKEY",
        qr_code:
          '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"></svg>',
        uri: "otpauth://totp/synthetic",
      },
    });
  }
  if (url.pathname.endsWith("/challenge"))
    return reply({
      id: ids.run,
      expires_at: Math.floor(Date.now() / 1000) + 300,
    });
  if (url.pathname.endsWith("/verify")) {
    if (parsed.code !== "123456")
      return reply(
        { msg: "Invalid TOTP", code: "mfa_verification_failed" },
        422,
      );
    factors = factors.map((f) => ({ ...f, status: "verified" }));
    return reply(session(claims.sub, "aal2"));
  }
  if (req.method === "DELETE" && url.pathname.startsWith("/auth/v1/factors/")) {
    factors = [];
    return reply({ id: ids.factor });
  }
  if (url.pathname === "/api/v1/me/organizations")
    return reply({
      data: [
        {
          organization_id: claims.sub,
          organization_name:
            claims.sub === ids.a ? "Synthetic Alpha" : "Synthetic Beta",
          organization_slug:
            claims.sub === ids.a ? "synthetic-alpha" : "synthetic-beta",
          organization_status: "active",
          membership_id: ids.run,
          membership_status: "active",
          membership_type: "client",
        },
      ],
      meta: { correlation_id: req.headers["x-correlation-id"] },
    });
  const scoped = url.pathname.match(
    /^\/api\/v1\/organizations\/([^/]+)\/(.+)$/,
  );
  if (!scoped || scoped[1] !== claims.sub)
    return reply({ code: "NOT_FOUND" }, 404);
  const path = scoped[2];
  const opportunity = {
    id: `seo_opportunity:${ids.opp}`,
    source_kind: "seo_opportunity",
    source_id: ids.opp,
    organization_id: claims.sub,
    location_id: null,
    website_id: claims.sub,
    page_id: ids.page,
    classification: "Issue",
    source_type: "missing_meta_description",
    status: "identified",
    priority: 70,
    evidence: {
      issue: "missing_meta_description",
      quality: "valid",
      period: null,
      source: "crawl",
      observed_at: "2026-09-30T00:00:00Z",
    },
    score_explanation: { reason: "Persisted synthetic crawl finding" },
    observed_at: "2026-09-30T00:00:00Z",
    evidence_context: {
      source: "crawl",
      quality: "issues_detected",
      freshness_at: "2026-09-30T00:00:00Z",
      period_start: null,
      period_end: null,
      limitation_code: null,
    },
  };
  const recommendation = {
    id: revision,
    revision_number: revision === ids.rev ? 1 : 2,
    proposed_action: "Repair the exact description",
    expected_result_hypothesis: "A clearer result snippet",
    risk: "low",
    effort: "low",
    status: approved ? "approved" : "awaiting_approval",
    change_set: [
      {
        page_id: ids.page,
        field: "meta_description",
        current_value: "",
        proposed_value: proposal,
        rationale: "Repair persisted issue",
      },
    ],
    change_set_limitation_code: null,
    decision_context: { evidence_quality: "valid" },
    approved_fingerprint: approved ? "synthetic-fingerprint" : null,
    quality: {
      state: "passed",
      problems: [],
      target_query: null,
      top_queries: [],
      location_terms: ["Synthetic City"],
      repository_verification: "executor_rechecks_before_write",
    },
    site_change: {
      mapping_state: "mapped",
      blocked_code: null,
      publication_status: approved ? "verified" : null,
      publication_id: approved ? ids.run : null,
      workflow_run_id: approved ? ids.run : null,
      deployment_status: approved ? "ready" : null,
      approved_head_sha: approved ? "synthetic-approved-head" : null,
      external_revision_id: approved ? "synthetic-merge" : null,
      published_url: null,
      verified_at: approved ? "2026-09-30T00:00:00Z" : null,
      pull_request_url: approved
        ? "https://github.com/synthetic/test/pull/1"
        : null,
      build_gate: approved ? "checks" : null,
      build_state: approved ? "passed" : null,
      verification_state: approved ? "verified" : null,
      live_checks: approved
        ? [
            {
              field: "meta_description",
              expected: proposal,
              observed: proposal,
              state: "matched",
            },
          ]
        : [],
    },
  };
  if (path === "command-center/opportunities")
    return reply({ data: [opportunity], next_offset: null });
  if (path === "command-center/attention")
    return reply({
      data: approved
        ? []
        : [
            {
              id: `seo_revision:${revision}:waiting_approval`,
              source_id: revision,
              opportunity_id: ids.opp,
              reason: "waiting_approval",
              status: "awaiting_approval",
              code: null,
            },
          ],
      next_offset: null,
    });
  if (path === `command-center/opportunities/${ids.opp}`)
    return reply({
      data: opportunity,
      page_url: "https://synthetic.invalid/page",
      recommendations: [recommendation],
      runs: approved
        ? [
            {
              id: ids.run,
              task_id: ids.run,
              task_status: "verified",
              status: "completed",
              correlation_id: req.headers["x-correlation-id"],
              output_reference: "publication:synthetic",
            },
          ]
        : [],
      can_recommend: true,
      can_approve: claims.aal === "aal2",
      correlation_id: req.headers["x-correlation-id"],
    });
  if (path.endsWith("/revise") && req.method === "POST") {
    if (approved || !path.includes(revision))
      return reply({ code: "REVISION_STALE" }, 409);
    revision = ids.next;
    proposal = parsed.edits[0].proposed_value;
    return reply({ data: { id: revision } }, 201);
  }
  if (path.endsWith("/decision") && req.method === "POST") {
    if (claims.aal !== "aal2") return reply({ code: "MFA_REQUIRED" }, 403);
    if (!path.includes(revision)) return reply({ code: "REVISION_STALE" }, 409);
    approved = parsed.approve;
    return reply({
      data: { id: revision },
      meta: { workflow_run_id: ids.run },
    });
  }
  return reply({ code: "NOT_FOUND" }, 404);
}).listen(4455, "127.0.0.1");
