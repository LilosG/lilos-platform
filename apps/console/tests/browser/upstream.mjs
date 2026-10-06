// Isolated HTTP simulator. Production loaders/session/BFF remain the code under test.
import { readFileSync } from "node:fs";
const phase2 = JSON.parse(
  readFileSync(new URL("../fixtures/phase2.json", import.meta.url), "utf8"),
);
const phase3 = JSON.parse(
  readFileSync(new URL("../fixtures/phase3.json", import.meta.url), "utf8"),
);
const phase4 = JSON.parse(
  readFileSync(new URL("../fixtures/phase4.json", import.meta.url), "utf8"),
);
const phase5 = JSON.parse(
  readFileSync(new URL("../fixtures/phase5.json", import.meta.url), "utf8"),
);
const leadStates = new Map();
let leadScenario = "inventory";
const contentStates = new Map();
const reviewStates = new Map();
const growthStates = new Map();
const contentOpportunityStates = new Map();
import { createServer } from "node:http";
import { commandCenter, liveChange, unified } from "./command-center-sim.mjs";
import {
  handle as beta,
  notConnected,
  reset as resetBeta,
  clearMedia,
} from "./local-search-sim.mjs";
const ids = {
  a: "11111111-1111-4111-8111-111111111111",
  b: "22222222-2222-4222-8222-222222222222",
  admin: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  opp: "33333333-3333-4333-8333-333333333333",
  page: "44444444-4444-4444-8444-444444444444",
  rev: "55555555-5555-4555-8555-555555555555",
  next: "66666666-6666-4666-8666-666666666666",
  older: "88888888-8888-4888-8888-888888888888",
  factor: "77777777-7777-4777-8777-777777777777",
  run: "88888888-8888-4888-8888-888888888888",
};
const raceCounts = new Map();
let revision = ids.rev;
let approved = false;
const factorsByUser = new Map();
const factorsFor = (id) => factorsByUser.get(id) ?? [];
let proposal =
  "A protected synthetic description proposed for this exact page.";
const user = (id) => ({
  id,
  aud: "authenticated",
  role: "authenticated",
  email:
    id === ids.a
      ? "a@example.test"
      : id === ids.admin
        ? "admin@example.test"
        : "b@example.test",
  app_metadata: {},
  user_metadata: {},
  factors: factorsFor(id),
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
function readMultipart(raw) {
  const text = raw.toString("latin1");
  const fields = {};
  let fileBytes = 0;
  for (const part of text.split(/--[^\r\n]+\r?\n/).slice(1)) {
    const name = /name="([^"]+)"/.exec(part)?.[1];
    const [head, ...rest] = part.split("\r\n\r\n");
    const content = rest.join("\r\n\r\n").replace(/\r\n(--[^\r\n]+)?$/, "");
    if (name === "file") fileBytes = Buffer.byteLength(content, "latin1");
    else if (name && !head.includes("filename")) fields[name] = content;
  }
  return { fields, fileBytes };
}
createServer(async (req, res) => {
  const url = new URL(req.url, "http://127.0.0.1:4455");
  const chunks = [];
  for await (const chunk of req) chunks.push(chunk);
  const raw = Buffer.concat(chunks);
  const multipart = (req.headers["content-type"] ?? "").startsWith(
    "multipart/form-data",
  );
  // An upload is read as its text fields and the file's size; the file itself is not kept.
  const parsed = multipart
    ? readMultipart(raw)
    : raw.length
      ? JSON.parse(raw.toString())
      : {};
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
  if (url.pathname === "/test/leads-scenario") {
    leadScenario = parsed.mode;
    leadStates.clear();
    return reply({ ok: true });
  }
  if (url.pathname === "/test/gbp-reset") {
    resetBeta();
    return reply({ ok: true });
  }
  if (url.pathname === "/test/gbp-clear-media") {
    clearMedia();
    return reply({ ok: true });
  }
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
        parsed.refresh_token?.includes(ids.admin)
          ? session(ids.admin, "aal2")
          : session(parsed.refresh_token?.includes(ids.b) ? ids.b : ids.a),
      );
    reviewStates.delete(ids.run);
    growthStates.clear();
    contentOpportunityStates.clear();
    contentStates.delete(ids.run);
    if (parsed.password !== "synthetic-password")
      return reply(
        { msg: "Invalid login credentials", code: "invalid_credentials" },
        400,
      );
    revision = ids.rev;
    approved = false;
    const loginId =
      parsed.email === "stepup@example.test" ||
      parsed.email === "admin@example.test"
        ? ids.admin
        : parsed.email === "a@example.test"
          ? ids.a
          : ids.b;
    factorsByUser.delete(loginId);
    if (parsed.email === "stepup@example.test") {
      factorsByUser.set(loginId, [
        {
          id: ids.factor,
          factor_type: "totp",
          status: "verified",
          friendly_name: "Synthetic authenticator",
        },
      ]);
      return reply(session(ids.admin, "aal1"));
    }
    if (parsed.email === "admin@example.test")
      return reply(session(ids.admin, "aal2"));
    return reply(session(parsed.email === "a@example.test" ? ids.a : ids.b));
  }
  if (url.pathname === "/auth/v1/user")
    return claims.sub
      ? reply(user(claims.sub))
      : reply({ msg: "Unauthorized" }, 401);
  if (url.pathname === "/auth/v1/logout") return reply({});
  if (url.pathname === "/auth/v1/factors" && req.method === "GET")
    return reply({
      all: factorsFor(claims.sub),
      totp: factorsFor(claims.sub).filter((f) => f.status === "verified"),
      phone: [],
    });
  if (url.pathname === "/auth/v1/factors" && req.method === "POST") {
    const factor = {
      id: ids.factor,
      factor_type: "totp",
      status: "unverified",
      friendly_name: "Synthetic authenticator",
    };
    factorsByUser.set(claims.sub, [factor]);
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
    factorsByUser.set(
      claims.sub,
      factorsFor(claims.sub).map((f) => ({ ...f, status: "verified" })),
    );
    return reply(session(claims.sub, "aal2"));
  }
  if (req.method === "DELETE" && url.pathname.startsWith("/auth/v1/factors/")) {
    factorsByUser.delete(claims.sub);
    return reply({ id: ids.factor });
  }
  const feed = commandCenter(url, claims, ids);
  if (feed) return reply(feed.body, feed.status ?? 200);
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
  // Synthetic Beta has the rich Local Search and Business Profile feeds.
  if (claims.sub === ids.b) {
    const result = beta(path, req.method, parsed, url, claims.sub);
    if (result) return reply(result.body, result.status);
  }
  if (
    path === "command-center/leads" ||
    path === `command-center/leads/${phase5.detail.lead.id}`
  ) {
    if (leadScenario === "error")
      return reply({ code: "SOURCE_UNAVAILABLE" }, 503);
    const data = structuredClone(
      path === "command-center/leads" ? phase5.workspace : phase5.detail,
    );
    if (
      path === "command-center/leads" &&
      ["zero", "unavailable"].includes(leadScenario)
    ) {
      data.items = [];
      data.inventory_count = leadScenario === "zero" ? 0 : null;
      data.recorded_conversions = leadScenario === "zero" ? 0 : null;
      if (leadScenario === "unavailable") {
        data.sources = [];
        data.quality = "unavailable";
      }
    }
    const location = url.searchParams.get("location_id");
    if (location && location !== phase5.detail.lead.location_id)
      return reply({ code: "NOT_FOUND" }, 404);
    if (claims.sub !== ids.a) return reply({ code: "NOT_FOUND" }, 404);
    if (path === "command-center/leads") {
      data.location_id = location;
      const saved = leadStates.get(claims.sub);
      if (saved) {
        data.items[0] = { ...data.items[0], ...saved.lead };
        data.recorded_conversions = saved.lead.converted_at ? 1 : 0;
      }
    } else {
      Object.assign(data, leadStates.get(claims.sub) ?? {});
      data.capabilities.can_manage_consent = claims.aal === "aal2";
    }
    return reply(data);
  }
  if (
    req.method === "POST" &&
    path.startsWith(`leads/${phase5.detail.lead.id}/`)
  ) {
    const data = leadStates.get(claims.sub) ?? structuredClone(phase5.detail);
    if (path.endsWith("/notes"))
      data.notes.push({
        id: ids.next,
        body: parsed.body,
        author_user_id: claims.sub,
        created_at: "2026-10-01T00:00:00Z",
      });
    if (path.endsWith("/assign"))
      data.lead.assigned_to_user_id = parsed.assigned_to_user_id;
    if (path.endsWith("/tasks"))
      data.tasks.push({
        id: ids.next,
        title: parsed.title,
        description: parsed.description ?? null,
        due_at: null,
        assigned_to_user_id: null,
        status: "open",
        completed_at: null,
      });
    if (path.endsWith(`/tasks/${ids.next}/complete`)) {
      data.tasks[0].status = "completed";
      data.tasks[0].completed_at = "2026-10-01T00:00:00Z";
    }
    if (path.endsWith("/consents") && claims.aal === "aal2")
      data.consents.push({ ...parsed, id: ids.next, withdrawn_at: null });
    if (path.endsWith("/status")) data.lead.status = parsed.to_status;
    if (path.endsWith("/convert")) {
      data.lead.status = "converted";
      data.lead.converted_at = "2026-10-01T00:00:00Z";
      data.lead.outcome = "recorded_conversion";
      data.capabilities.can_record_outcome = false;
      data.capabilities.allowed_statuses = ["archived"];
    }
    if (path.endsWith("/communications"))
      data.communications.push({
        ...phase5.detail.communications[0],
        id: ids.next,
      });
    if (path.endsWith("/consents") && claims.aal !== "aal2")
      return reply({ code: "AUTH_AAL2_REQUIRED" }, 403);
    leadStates.set(claims.sub, data);
    return reply({ data: { id: ids.next } }, 200);
  }
  if (path === "command-center/website-content") {
    const data = structuredClone(phase4.workspace);
    data.organization_id = claims.sub;
    if (
      url.searchParams.has("website_id") &&
      url.searchParams.get("website_id") !== data.website_id
    )
      return reply({ code: "NOT_FOUND" }, 404);
    return reply(data);
  }
  if (path.startsWith("command-center/website-content/websites/")) {
    const data = structuredClone(phase4.page);
    if (
      path !==
      `command-center/website-content/websites/${data.evidence.identity.website_id}/pages/${data.evidence.identity.page_id}`
    )
      return reply({ code: "NOT_FOUND" }, 404);
    data.evidence.identity.organization_id = claims.sub;
    return reply(data);
  }
  if (path === `command-center/website-content/content/${phase4.detail.id}`) {
    const data = structuredClone(phase4.detail);
    data.organization_id = claims.sub;
    const state = contentStates.get(claims.session_id) ?? "awaiting_editorial";
    data.revisions[0].status = state;
    data.can_approve = claims.aal === "aal2";
    data.can_publish = claims.aal === "aal2";
    if (state === "approved") data.stage = "ready_to_publish";
    if (state === "publishing") {
      data.stage = "publishing";
      data.revisions[0].status = "approved";
      data.publications = [
        {
          id: ids.run,
          status: "pull_request_created",
          target_path: "src/content/blog/synthetic-article.mdx",
          external_pull_request_id: "1",
          published_url: null,
          build_status: "checks_running",
          deployment_status: null,
          verified_at: null,
          safe_error_code: null,
          revision_id: ids.rev,
          workflow_id: ids.run,
          workflow_status: "queued",
          workflow_failure: null,
          correlation_id: req.headers["x-correlation-id"],
          approved_head_sha: null,
          external_revision_id: null,
          verification_status: null,
          verification_evidence: null,
          can_recover: true,
        },
      ];
    }
    return reply(data);
  }
  const growthDecision = path.match(/^growth\/([^/]+)\/decision$/);
  if (growthDecision && req.method === "POST") {
    if (claims.aal !== "aal2") return reply({ code: "AAL2_REQUIRED" }, 403);
    growthStates.set(
      claims.session_id,
      parsed.approve ? "approved" : "rejected",
    );
    return reply({ data: { status: growthStates.get(claims.session_id) } });
  }
  if (
    /^content\/opportunities\/[^/]+\/decision$/.test(path) &&
    req.method === "POST"
  ) {
    contentOpportunityStates.set(
      claims.session_id,
      parsed.accept ? "accepted" : "rejected",
    );
    return reply({
      data: { status: contentOpportunityStates.get(claims.session_id) },
    });
  }
  if (path === "content" && req.method === "POST")
    return reply({ data: { id: phase4.detail.id } }, 201);
  if (path.includes("content-operations/") && req.method === "POST") {
    if (claims.aal !== "aal2") return reply({ code: "AAL2_REQUIRED" }, 403);
    if (path.endsWith("/decision"))
      contentStates.set(
        claims.session_id,
        parsed.stage === "editorial" ? "awaiting_client" : "approved",
      );
    if (path.endsWith("/publish"))
      contentStates.set(claims.session_id, "publishing");
    return reply(
      { data: { id: ids.run, status: contentStates.get(claims.session_id) } },
      202,
    );
  }
  if (
    path.includes("content-operations/") &&
    path.endsWith("/publishing-assets")
  )
    return reply({
      data: [{ path: "/synthetic.webp", name: "synthetic.webp" }],
    });
  if (path.startsWith("content/") && req.method === "POST")
    return reply({ data: { id: ids.next, status: "awaiting_editorial" } }, 201);
  if (path === "command-center/reviews") {
    const data = structuredClone(phase3.workspace);
    data.organization_id = claims.sub;
    if (
      url.searchParams.has("location_id") &&
      url.searchParams.get("location_id") !== data.location_id
    )
      return reply({ code: "NOT_FOUND" }, 404);
    // Synthetic Beta has never imported reviews: nothing is counted, and it can import.
    if (claims.sub === ids.b) {
      Object.assign(data, {
        items: [],
        inventory_count: null,
        average_rating: null,
        open_restricted_cases: null,
        awaiting_response_count: null,
        can_ingest: true,
        source: {
          ...data.source,
          connection_status: "connected",
          last_ingested_at: null,
          freshness: "unavailable",
          quality: "unavailable",
        },
      });
      return reply(data);
    }
    const reviewTabs = {
      needs_response: ["classified-open"],
      draft: ["draft"],
      awaiting_approval: ["awaiting_approval"],
      published: ["published"],
    };
    const wanted = url.searchParams.get("status");
    if (wanted) {
      if (!(wanted in reviewTabs)) return reply({ code: "VALIDATION" }, 422);
      data.items = data.items.filter((r) => {
        const open = r.response_status === null;
        const key = open ? "classified-open" : r.response_status;
        return reviewTabs[wanted].includes(key);
      });
    }
    return reply(data);
  }
  if (path.startsWith("command-center/reviews/locations/")) {
    const data = structuredClone(phase3.detail);
    data.organization_id = claims.sub;
    if (
      path !==
      `command-center/reviews/locations/${data.location_id}/${data.review.id}`
    )
      return reply({ code: "NOT_FOUND" }, 404);
    const state = reviewStates.get(claims.session_id) ?? "awaiting_approval";
    const r = data.responses[0];
    r.status = state;
    r.can_approve = state === "awaiting_approval" && claims.aal === "aal2";
    r.can_publish = state === "approved" && claims.aal === "aal2";
    if (state === "publishing") {
      r.workflow_status = "queued";
      r.workflow_id = data.review.id;
    }
    return reply(data);
  }
  if (path.includes("/reviews/") && req.method === "POST") {
    if (path.endsWith("/approve") || path.endsWith("/publish")) {
      if (claims.aal !== "aal2") return reply({ code: "AAL2_REQUIRED" }, 403);
      reviewStates.set(
        claims.session_id,
        path.endsWith("/approve") ? "approved" : "publishing",
      );
      return reply(
        { data: { status: reviewStates.get(claims.session_id) } },
        path.endsWith("/publish") ? 202 : 200,
      );
    }
    return reply(
      {
        data: {
          id: phase3.detail.responses[0].id,
          status: "awaiting_approval",
        },
      },
      201,
    );
  }
  const phase2Payload = (key) => {
    const data = structuredClone(phase2[key]);
    data.organization_id = claims.sub;
    if (key === "profile") data.can_approve = claims.aal === "aal2";
    return data;
  };
  if (path === "command-center/gbp/performance")
    return reply(notConnected(claims.sub, url.searchParams));
  if (path === "command-center/integrations")
    return reply(phase2Payload("integration"));
  if (path === "command-center/local-search")
    return reply(phase2Payload("search"));
  if (path.startsWith("command-center/local-search/websites/"))
    return reply(phase2Payload("page"));
  if (path.startsWith("command-center/local-search/locations/"))
    return reply(phase2Payload("profile"));
  if (path.endsWith("search-console/discover"))
    return reply({
      data: {
        properties: [
          {
            external_property_id: "sc-domain:synthetic.example.invalid",
            property_type: "domain",
            permission_level: "siteOwner",
          },
        ],
      },
    });
  if (path.endsWith("insights/analytics/discover"))
    return reply({ data: { properties: [] } });
  if (path.endsWith("properties/map"))
    return reply({ data: { mapping_status: "mapped" } }, 201);
  if (path.endsWith("/check"))
    return reply({ data: { id: ids.run, status: "queued" } }, 202);
  if (path.endsWith("/sync"))
    return reply({ data: { workflow_run_id: ids.run, status: "queued" } }, 202);
  if (path.includes("gbp-mapping/") && path.endsWith("/confirm"))
    return reply({
      data: {
        id: ids.factor,
        mapping_status: "confirmed",
        write_enabled: parsed.write_enabled,
      },
    });
  if (path.endsWith("gbp/operations/locations/" + ids.factor + "/posts"))
    return reply({ data: { id: ids.rev, status: "awaiting_approval" } }, 201);
  const opportunity = unified("seo", claims.sub, ids, {
    evidence: {
      issue: "missing_meta_description",
      quality: "valid",
      period: null,
      source: "crawl",
      observed_at: "2026-09-30T00:00:00Z",
    },
    evidence_context: {
      source: "crawl",
      quality: "issues_detected",
      freshness_at: "2026-09-30T00:00:00Z",
      period_start: null,
      period_end: null,
      limitation_code: null,
    },
    latest_revision_status: approved ? "approved" : "awaiting_approval",
    // A verified change is live: the next step is to measure it, not to follow it.
    lifecycle: approved ? "live" : "open",
    verified_at: approved ? "2026-09-30T00:00:00Z" : null,
    next_action: approved ? "measure_impact" : "review_recommendation",
    evidence_context: {
      source: "gsc",
      quality: "issues_detected",
      freshness_at: "2026-09-30T00:00:00Z",
      period_start: "2026-09-27",
      period_end: "2026-10-04",
      limitation_code: null,
    },
  });
  const earlierRevision = {
    id: ids.older,
    created_at: "2026-09-27T12:00:00Z",
    revision_number: 1,
    proposed_action: "Superseded wording",
    expected_result_hypothesis: "Earlier hypothesis",
    risk: "low",
    effort: "low",
    status: "superseded",
    change_set: [],
    change_set_limitation_code: null,
    decision_context: null,
    approved_fingerprint: null,
    quality: {
      state: "unavailable",
      problems: [],
      target_query: null,
      top_queries: [],
      location_terms: [],
      repository_verification: "executor_rechecks_before_write",
    },
    site_change: null,
  };
  const recommendation = {
    id: revision,
    created_at: "2026-09-28T12:00:00Z",
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
  if (path === "command-center/opportunities") {
    const wanted = url.searchParams.get("kind");
    const band = url.searchParams.get("priority");
    const done = url.searchParams.get("state") === "done";
    return reply({
      data: (done
        ? [approved ? opportunity : liveChange(claims.sub, ids)]
        : [
            ...(approved ? [] : [opportunity]),
            unified("growth", claims.sub, ids),
            unified("content", claims.sub, ids),
          ]
      )
        .filter((row) => !wanted || row.kind === wanted)
        .filter((row) => !band || row.priority_band === band),
      next_offset: null,
      kinds_unavailable: [],
    });
  }
  if (
    path ===
    `command-center/opportunities/${unified("growth", claims.sub, ids).source_id}`
  )
    return reply({
      kind: "growth",
      data: unified("growth", claims.sub, ids, {
        status: growthStates.get(claims.session_id) ?? "proposed",
        next_action: growthStates.has(claims.session_id)
          ? "monitor_execution"
          : "review_growth_plan",
      }),
      page_url: null,
      recommendations: [],
      runs: [],
      growth: {
        objective: "Win brunch searches",
        rationale: "Demand exists for brunch queries",
        confidence: 0.8,
        actions: [
          {
            id: ids.run,
            action_key: "a1",
            product_key: "seo",
            action_type: "site_implementation",
            execution_mode: "manual",
            status: "proposed",
            risk: "low",
            effort: "low",
            expected_result_hypothesis: "More clicks on brunch queries",
            safe_error_code: null,
          },
        ],
      },
      content: null,
      history: [],
      live_check: null,
      can_recommend: false,
      can_approve: claims.aal === "aal2",
      correlation_id: req.headers["x-correlation-id"],
    });
  if (
    path ===
    `command-center/opportunities/${unified("content", claims.sub, ids).source_id}`
  )
    return reply({
      kind: "content",
      data: unified("content", claims.sub, ids, {
        status: contentOpportunityStates.get(claims.session_id) ?? "identified",
      }),
      page_url: null,
      recommendations: [],
      runs: [],
      growth: null,
      content: {
        target_reference: "/blog/brunch",
        opportunity_type: "seo",
        items: [],
      },
      history: null,
      live_check: null,
      can_recommend: false,
      can_approve: true,
      correlation_id: req.headers["x-correlation-id"],
    });
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
      kind: "seo",
      growth: null,
      content: null,
      history: [],
      live_check: approved
        ? {
            state: "verified",
            verified_at: "2026-09-30T00:00:00Z",
            checks: recommendation.site_change.live_checks,
          }
        : null,
      data: opportunity,
      page_url: "https://synthetic.invalid/page",
      recommendations:
        revision === ids.rev
          ? [recommendation]
          : [recommendation, earlierRevision],
      runs: approved
        ? [
            {
              id: ids.run,
              task_id: ids.run,
              task_status: "pending",
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
