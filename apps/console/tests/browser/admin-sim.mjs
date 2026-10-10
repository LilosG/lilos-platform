// Synthetic Administration and Settings feeds for browser tests only. Never imported by the app.
const tag = (n) => `${String(n).padStart(8, "0")}-0000-4000-8000-000000000000`;
export const modes = [
  "default",
  "error",
  "no_clients",
  "removal_failed",
  "retire_archive_fails",
  "locations_error",
  "locations_empty",
  "facts_empty",
  "facts_error",
];
const gamma = "99999999-9999-4999-8999-999999999999";
// The lifecycle table of apps/api/app/locations/service.py, restated for the simulator.
const TRANSITIONS = {
  setup_required: ["active", "archived"],
  active: ["paused", "closed_temporarily", "closed_permanently"],
  paused: ["active", "closed_temporarily", "closed_permanently", "archived"],
  closed_temporarily: ["active", "paused", "closed_permanently"],
  closed_permanently: ["archived"],
  archived: [],
};
const TARGET = {
  activate: "active",
  pause: "paused",
  "close-temporarily": "closed_temporarily",
  "close-permanently": "closed_permanently",
  archive: "archived",
};
export const state = {
  mode: "default",
  requests: [],
  orgs: [],
  locations: [],
  facts: [],
  waiting: [],
  removalPolls: new Map(),
  /** Clients that no longer appear in the switcher. */
  hidden: new Set(),
};
const org = (id, name, slug, status, site) => ({
  id,
  name,
  slug,
  organization_type: "client",
  status,
  timezone: "America/Los_Angeles",
  default_currency: "USD",
  legal_name: null,
  website_url: site,
  version: 3,
  archived_at: null,
  removed_at: null,
});
const place = (n, name, status, extra = {}) => ({
  id: tag(n),
  organization_id: "",
  name,
  slug: name.toLowerCase().replace(/[^a-z]+/g, "-"),
  location_type: "physical",
  status,
  timezone: "America/Los_Angeles",
  address_line_1: null,
  address_line_2: null,
  city: null,
  region: null,
  postal_code: null,
  country_code: "US",
  service_area_description: null,
  is_primary: false,
  version: 2,
  ...extra,
});
export function reset(mode, ids) {
  state.mode = mode;
  state.requests = [];
  state.removalPolls = new Map();
  state.hidden = new Set();
  state.waiting = [];
  state.orgs =
    mode === "no_clients"
      ? []
      : [
          org(
            ids.a,
            "Synthetic Alpha",
            "synthetic-alpha",
            "active",
            "https://www.synthetic-alpha.example.test",
          ),
          org(ids.b, "Synthetic Beta", "synthetic-beta", "active", null),
          org(gamma, "Synthetic Gamma", "synthetic-gamma", "paused", null),
          org(
            tag(41),
            "Maple Street Cafe",
            "maple-street-cafe",
            "offboarding",
            null,
          ),
          org(tag(42), "Old Test Client", "old-test-client", "archived", null),
          org(
            tag(43),
            "Duplicate Cococabana",
            "duplicate-cococabana",
            "archived",
            null,
          ),
        ];
  state.locations = [
    place(1, "Main Street", "active", {
      organization_id: ids.a,
      is_primary: true,
      address_line_1: "100 Main Street",
      city: "San Diego",
      region: "CA",
      postal_code: "92101",
    }),
    place(2, "DONT USE", "active", {
      organization_id: ids.a,
      address_line_1: "9 Closed Lane",
      city: "San Diego",
      region: "CA",
      postal_code: "92102",
    }),
    place(3, "Pop-up Patio", "paused", {
      organization_id: ids.a,
      address_line_1: "5 Beach Way",
      city: "Encinitas",
      region: "CA",
      postal_code: "92024",
    }),
    place(4, "Winter Lodge", "closed_temporarily", {
      organization_id: ids.a,
      service_area_description: "Greater San Diego",
    }),
    place(5, "Old Harbor", "closed_permanently", {
      organization_id: ids.a,
      address_line_1: "1 Harbor Drive",
      city: "Coronado",
      region: "CA",
      postal_code: "92118",
    }),
    place(6, "New Kitchen", "setup_required", { organization_id: ids.a }),
    place(7, "Retired Cart", "archived", { organization_id: ids.a }),
  ];
  state.facts =
    mode === "facts_empty"
      ? []
      : [
          fact(
            "business.name",
            "string",
            "Synthetic Alpha",
            "operator_verified",
            null,
            11,
          ),
          fact(
            "business.website",
            "string",
            "https://synthetic-alpha.example.test",
            "system_derived",
            null,
            12,
          ),
          fact(
            "business.address",
            "object",
            {
              address_line_1: "100 Main Street",
              address_line_2: null,
              city: "San Diego",
              region: "CA",
              postal_code: "92101",
              country_code: "US",
            },
            "provider_observed",
            tag(1),
            13,
          ),
          fact(
            "business.hours",
            "object",
            {
              periods: [
                "MONDAY",
                "TUESDAY",
                "WEDNESDAY",
                "THURSDAY",
                "FRIDAY",
              ].map((openDay) => ({ openDay })),
            },
            "provider_observed",
            tag(1),
            14,
          ),
          fact(
            "brand.approved_claims",
            "string_list",
            ["Family owned since 1998", "Fresh tortillas made daily"],
            "client_approved",
            null,
            15,
          ),
          fact(
            "tax.registration_number",
            "string",
            "12-345",
            "imported",
            null,
            16,
          ),
        ];
}
const fact = (key, type, value, authority, location, n) => ({
  id: tag(n + 100),
  fact_key: key,
  fact_identity: tag(n),
  value,
  value_type: type,
  location_id: location,
  authority,
  revision: 1,
  source: "synthetic",
  approved_at: "2026-09-01T00:00:00Z",
});
const json = (status, body) => ({ status, body });
const denied = () => json(403, { error: { code: "AUTHORIZATION_DENIED" } });
const conflict = (code) => json(409, { error: { code } });
export function handle(req, url, claims, ids, parsed) {
  const platform = url.pathname.match(
    /^\/api\/v1\/platform\/organizations(?:\/([^/]+)(?:\/([^/]+))?)?$/,
  );
  const scoped = url.pathname.match(
    /^\/api\/v1\/organizations\/([^/]+)\/(locations|business-facts)(?:\/(.+))?$/,
  );
  if (!platform && !scoped) return null;
  const administrator = claims.sub === ids.admin && claims.aal === "aal2";
  if (platform) {
    if (!administrator) return denied();
    const [, id, tail] = platform;
    if (state.mode === "error")
      return json(503, { error: { code: "DATABASE_UNAVAILABLE" } });
    if (!id && req.method === "GET")
      return json(200, {
        data: {
          items: state.orgs,
          limit: 100,
          offset: 0,
          next_offset: null,
          has_more: false,
        },
      });
    const found = state.orgs.find((o) => o.id === id);
    if (!found) return json(404, { error: { code: "ORGANIZATION_NOT_FOUND" } });
    if (tail === "locations" && found.id === gamma)
      return json(503, { error: { code: "DATABASE_UNAVAILABLE" } });
    if (tail === "locations")
      return json(200, {
        data: {
          items: state.locations
            .map((l) => ({ ...l, organization_id: found.id }))
            .filter(() => found.id === ids.a),
          has_more: false,
        },
      });
    if (tail === "removal") {
      if (found.status !== "archived")
        return json(200, {
          data: { state: null, failure_code: null, workflow_run_id: null },
        });
      if (state.mode === "removal_failed" && found.id === tag(43))
        return json(200, {
          data: {
            state: "failed",
            failure_code: "ORGANIZATION_REMOVAL_FAILED",
            workflow_run_id: tag(900),
          },
        });
      const polls = state.removalPolls.get(found.id);
      if (polls === undefined)
        return json(200, {
          data: { state: null, failure_code: null, workflow_run_id: null },
        });
      state.removalPolls.set(found.id, polls + 1);
      const progress =
        polls >= 2 ? "completed" : polls >= 1 ? "in_progress" : "requested";
      if (progress === "completed")
        state.orgs = state.orgs.filter((o) => o.id !== found.id);
      return json(200, {
        data: {
          state: progress,
          failure_code: null,
          workflow_run_id: tag(901),
        },
      });
    }
    if (req.method !== "POST") return null;
    state.requests.push({
      path: `${tail}`,
      organization_id: found.id,
      body: parsed,
    });
    if (tail === "remove") {
      if (found.status !== "archived")
        return conflict("ORGANIZATION_REMOVAL_REQUIRES_ARCHIVED");
      if (parsed.confirm_name.trim().toLowerCase() !== found.name.toLowerCase())
        return conflict("ORGANIZATION_REMOVAL_CONFIRMATION_MISMATCH");
      state.removalPolls.set(found.id, 0);
      return json(202, {
        data: {
          organization: found,
          state: "requested",
          workflow_run_id: tag(901),
        },
      });
    }
    const next = {
      "start-offboarding": [
        "offboarding",
        ["prospect", "onboarding", "active", "paused", "suspended"],
      ],
      archive: ["archived", ["offboarding"]],
    }[tail];
    if (!next) return null;
    if (parsed.expected_version !== found.version)
      return conflict("ORGANIZATION_VERSION_CONFLICT");
    if (!next[1].includes(found.status))
      return conflict("ORGANIZATION_TRANSITION_CONFLICT");
    found.status = next[0];
    found.version += 1;
    state.hidden.add(found.id);
    return json(200, { data: found });
  }
  const [, id, area, rest] = scoped;
  if (!administrator && id !== claims.sub)
    return json(404, { code: "NOT_FOUND" });
  if (area === "locations") {
    if (state.mode === "locations_error")
      return json(503, { error: { code: "DATABASE_UNAVAILABLE" } });
    const mine =
      state.mode === "locations_empty"
        ? []
        : state.locations.filter(() => id === ids.a);
    if (!rest && req.method === "GET")
      return json(200, {
        data: mine,
        pagination: {
          limit: 100,
          offset: 0,
          next_offset: null,
          has_more: false,
        },
      });
    const step = rest?.match(/^([^/]+)\/([^/]+)$/);
    if (!step || req.method !== "POST") return null;
    const location = state.locations.find((l) => l.id === step[1]);
    if (!location) return json(404, { error: { code: "LOCATION_NOT_FOUND" } });
    state.requests.push({
      path: step[2],
      location_id: location.id,
      body: parsed,
    });
    if (parsed.expected_version !== location.version)
      return conflict("LOCATION_VERSION_CONFLICT");
    const target = TARGET[step[2]];
    if (!target || !TRANSITIONS[location.status].includes(target))
      return conflict("LOCATION_TRANSITION_CONFLICT");
    if (state.mode === "retire_archive_fails" && target === "archived")
      return conflict("LOCATION_TRANSITION_CONFLICT");
    location.status = target;
    location.version += 1;
    return json(200, { data: location, meta: {} });
  }
  if (state.mode === "facts_error")
    return json(503, { error: { code: "DATABASE_UNAVAILABLE" } });
  if (rest === "effective" && req.method === "GET")
    return json(200, { data: state.facts });
  if (rest === "candidates" && req.method === "GET")
    return json(200, { data: state.waiting });
  if (!rest && req.method === "POST") {
    state.requests.push({ path: "business-facts", body: parsed });
    const revision = {
      id: tag(200 + state.requests.length),
      fact_key: parsed.fact_key,
      fact_identity: parsed.fact_identity ?? tag(300 + state.requests.length),
      value: parsed.value,
      value_type: parsed.value_type,
      location_id: parsed.location_id ?? null,
      authority: parsed.authority,
      revision: 2,
      status: "proposed",
    };
    state.waiting.push(revision);
    return json(201, { data: revision });
  }
  const decision = rest?.match(/^([^/]+)\/decision$/);
  if (decision && req.method === "POST") {
    state.requests.push({ path: "decision", body: parsed });
    // Approving needs a verified second factor, as it does in the API.
    if (claims.aal !== "aal2") return denied();
    const revision = state.waiting.find((w) => w.id === decision[1]);
    if (!revision)
      return json(404, {
        error: { code: "ADMINISTRATION_RESOURCE_NOT_FOUND" },
      });
    state.waiting = state.waiting.filter((w) => w !== revision);
    if (parsed.decision === "approve")
      state.facts = [
        ...state.facts.filter(
          (f) => f.fact_identity !== revision.fact_identity,
        ),
        { ...revision, status: "active" },
      ];
    return json(200, { data: revision });
  }
  return null;
}
