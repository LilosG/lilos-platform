import { describe, expect, it, vi } from "vitest";
import {
  LOCATION_STATUSES,
  adaptFacts,
  adaptLocations,
  adaptOrganizations,
  adaptRemoval,
} from "../../src/adapters/administration";
import {
  administrationFailureText,
  confirmCopy,
  nextAction,
  organizationRows,
  removalFailureText,
} from "../../src/lib/administration-view";
import {
  FACT_FIELDS,
  addressText,
  factFormComplete,
  factLabel,
  factProposal,
  factRows,
  factValueText,
  locationActions,
  locationConfirm,
  locationRows,
  retirePlan,
  retireProgress,
  settingsFailureText,
} from "../../src/lib/settings-view";
import {
  factSourceChips,
  locationChip,
  organizationChip,
  removalChips,
} from "../../src/lib/status";
import { forward } from "../../src/server/bff";
import { csrfToken } from "../../src/server/security";
const id = (n: number) =>
  `${String(n).padStart(8, "0")}-0000-4000-8000-000000000000`;
const org = (over: Record<string, unknown> = {}) => ({
  id: id(1),
  name: "Cococabana",
  slug: "cococabana",
  status: "active",
  website_url: "https://www.cococabana.example.test/menu",
  version: 4,
  ...over,
});
const place = (over: Record<string, unknown> = {}) => ({
  id: id(2),
  name: "Main Street",
  status: "active",
  location_type: "physical",
  address_line_1: "100 Main Street",
  address_line_2: null,
  city: "San Diego",
  region: "CA",
  postal_code: "92101",
  service_area_description: null,
  is_primary: false,
  version: 2,
  ...over,
});
describe("organization lifecycle", () => {
  it("offers exactly the next step each state allows", () => {
    for (const status of [
      "prospect",
      "onboarding",
      "active",
      "paused",
      "suspended",
    ] as const)
      expect(nextAction(status, null)).toBe("start_offboarding");
    expect(nextAction("offboarding", null)).toBe("archive");
    expect(nextAction("archived", null)).toBe("remove");
    expect(nextAction("archived", { state: null, failure_code: null })).toBe(
      "remove",
    );
    expect(
      nextAction("archived", { state: "failed", failure_code: null }),
    ).toBe("remove");
    for (const state of ["requested", "in_progress", "completed"] as const)
      expect(nextAction("archived", { state, failure_code: null })).toBeNull();
  });
  it("builds a row with the host, a count that is never 0 when unknown, and the removal chip", () => {
    const [row] = organizationRows(
      adaptOrganizations({ data: { items: [org()] } }),
      new Map(),
      new Map(),
    );
    expect(row.site).toBe("cococabana.example.test");
    expect(row.locations).toBeNull();
    expect(row.chip).toEqual({ label: "Active", tone: "" });
    expect(row.actionLabel).toBe("Start offboarding");
    const [archived] = organizationRows(
      [org({ status: "archived" })].map((o) =>
        adaptOrganizations({ data: { items: [o] } }),
      )[0],
      new Map([[id(1), 0]]),
      new Map([[id(1), { state: "failed", failure_code: "X" } as const]]),
    );
    expect(archived.locations).toBe(0);
    expect(archived.removalChip).toEqual(removalChips.failed);
    expect(archived.actionLabel).toBe("Try removal again");
    expect(archived.removalNote).toContain("contact engineering");
    const [running] = organizationRows(
      adaptOrganizations({ data: { items: [org({ status: "archived" })] } }),
      new Map(),
      new Map([[id(1), { state: "in_progress", failure_code: null } as const]]),
    );
    expect(running.removalRunning).toBe(true);
    expect(running.action).toBeNull();
  });
  it("says exactly what each step does; archive cannot be undone; removal needs the name", () => {
    expect(confirmCopy("start_offboarding", "Cococabana")).toMatchObject({
      title: "Start offboarding Cococabana?",
      typedName: null,
      tone: "normal",
    });
    const archive = confirmCopy("archive", "Cococabana");
    expect(archive.lines.join(" ")).toContain("cannot be undone");
    expect(archive.tone).toBe("danger");
    const remove = confirmCopy("remove", "Cococabana");
    expect(remove.typedName).toBe("Cococabana");
    expect(remove.lines.join(" ")).toContain("cannot be undone");
  });
  it("turns typed failure codes into sentences and never echoes an unknown code", () => {
    expect(
      administrationFailureText("ORGANIZATION_REMOVAL_CONFIRMATION_MISMATCH"),
    ).toContain("does not match");
    expect(
      administrationFailureText("ORGANIZATION_REMOVAL_REQUIRES_ARCHIVED"),
    ).toContain("Archive it first");
    expect(administrationFailureText("SOMETHING_NEW")).not.toContain(
      "SOMETHING_NEW",
    );
    expect(removalFailureText("SOME_WORKER_CODE")).not.toContain(
      "SOME_WORKER_CODE",
    );
    expect(organizationChip("not-a-status").label).toBe("Unknown");
  });
  it("refuses a shape it does not know instead of half-showing it", () => {
    expect(() =>
      adaptOrganizations({ data: { items: [org({ status: "deleted" })] } }),
    ).toThrow();
    expect(() => adaptRemoval({ data: { state: "gone" } })).toThrow();
    expect(adaptRemoval({ data: { state: null, failure_code: null } })).toEqual(
      { state: null, failure_code: null },
    );
  });
});
describe("location lifecycle", () => {
  // The API's own table (apps/api/app/locations/service.py TRANSITIONS).
  const API: Record<string, string[]> = {
    setup_required: ["active", "archived"],
    active: ["paused", "closed_temporarily", "closed_permanently"],
    paused: ["active", "closed_temporarily", "closed_permanently", "archived"],
    closed_temporarily: ["active", "paused", "closed_permanently"],
    closed_permanently: ["archived"],
    archived: [],
  };
  const TARGET: Record<string, string> = {
    activate: "active",
    pause: "paused",
    "close-temporarily": "closed_temporarily",
    "close-permanently": "closed_permanently",
    archive: "archived",
  };
  it("never offers a step the API refuses", () => {
    for (const status of LOCATION_STATUSES) {
      for (const entry of locationActions(status)) {
        const steps =
          entry.action === "retire" ? retirePlan(status) : [entry.action];
        // Walk the steps through the API's table: each must be allowed from where the last left off.
        let current: string = status;
        for (const step of steps) {
          expect(API[current]).toContain(TARGET[step]);
          current = TARGET[step];
        }
      }
    }
  });
  it("retires in the order the lifecycle requires, and never twice", () => {
    expect(retirePlan("active")).toEqual(["close-permanently", "archive"]);
    expect(retirePlan("paused")).toEqual(["close-permanently", "archive"]);
    expect(retirePlan("closed_temporarily")).toEqual([
      "close-permanently",
      "archive",
    ]);
    expect(retirePlan("closed_permanently")).toEqual(["archive"]);
    expect(retirePlan("setup_required")).toEqual(["archive"]);
    expect(retirePlan("archived")).toEqual([]);
    expect(locationActions("archived")).toEqual([]);
  });
  it("labels the same activation by where it starts", () => {
    const label = (status: (typeof LOCATION_STATUSES)[number]) =>
      locationActions(status).find((a) => a.action === "activate")?.label;
    expect(label("setup_required")).toBe("Activate");
    expect(label("paused")).toBe("Resume");
    expect(label("closed_temporarily")).toBe("Reopen");
  });
  it("reads addresses in plain words and lists the primary first", () => {
    const rows = locationRows(
      adaptLocations({
        data: [
          place({ id: id(3), name: "Zed", status: "archived" }),
          place({ id: id(4), name: "Alpha", status: "active" }),
          place({
            id: id(5),
            name: "Area",
            address_line_1: null,
            city: null,
            region: null,
            postal_code: null,
            service_area_description: "Greater San Diego",
          }),
          place({
            id: id(6),
            name: "Nowhere",
            address_line_1: null,
            city: null,
            region: null,
            postal_code: null,
          }),
          place({ id: id(7), name: "Primary", is_primary: true }),
        ],
      }),
    );
    expect(rows.map((r) => r.name)).toEqual([
      "Primary",
      "Alpha",
      "Area",
      "Nowhere",
      "Zed",
    ]);
    expect(rows[0].address).toBe("100 Main Street, San Diego, CA 92101");
    expect(rows.find((r) => r.name === "Area")!.address).toBe(
      "Greater San Diego",
    );
    expect(rows.find((r) => r.name === "Nowhere")!.address).toBe(
      "No address on file",
    );
    expect(rows.at(-1)!.retired).toBe(true);
    expect(
      addressText(
        adaptLocations({
          data: { items: [place({ address_line_2: "Suite 4" })] },
        })[0],
      ),
    ).toBe("100 Main Street, Suite 4, San Diego, CA 92101");
    expect(locationChip("closed_permanently").label).toBe("Permanently closed");
  });
  it("explains retire as stopping automations and hiding the location", () => {
    const retire = locationConfirm("retire", "DONT USE");
    expect(retire.lines.join(" ")).toContain("stops all of its automations");
    expect(retire.lines.join(" ")).toContain("hidden from reports");
    expect(retire.tone).toBe("danger");
  });
  it("says which step a stopped retirement reached", () => {
    expect(retireProgress(["close-permanently"], "archive")).toBe(
      "It was closed permanently, but archiving it did not go through.",
    );
    expect(retireProgress([], "close-permanently")).toBe(
      "Closing it permanently did not go through, so nothing changed.",
    );
    expect(settingsFailureText("LOCATION_VERSION_CONFLICT")).toContain(
      "changed since",
    );
    expect(settingsFailureText("LOCATION_NEW_CODE")).not.toContain(
      "LOCATION_NEW_CODE",
    );
  });
});
describe("business facts", () => {
  const fact = (over: Record<string, unknown>) => ({
    fact_key: "business.name",
    fact_identity: id(10),
    value: "Cococabana",
    value_type: "string",
    location_id: null,
    authority: "operator_verified",
    revision: 1,
    ...over,
  });
  it("shows plain labels and values, never keys or raw objects", () => {
    expect(factLabel("business.name")).toBe("Business name");
    expect(factLabel("claim.operator_ab12")).toBe("Approved claim");
    expect(factLabel("tax.registration_number")).toBe("Other detail");
    expect(
      factValueText("business.address", {
        address_line_1: "1 A St",
        address_line_2: null,
        city: "Town",
        region: "CA",
        postal_code: "90000",
      }),
    ).toBe("1 A St, Town, CA 90000");
    expect(factValueText("brand.approved_claims", ["One", "Two"])).toBe(
      "One · Two",
    );
    expect(
      factValueText("business.hours", {
        periods: [
          { openDay: "MONDAY" },
          { openDay: "MONDAY" },
          { openDay: "TUESDAY" },
        ],
      }),
    ).toBe("Open 2 days a week");
    expect(factValueText("business.hours", { periods: [] })).toBeNull();
    expect(factValueText("x.y", { nested: { a: 1 } })).toBeNull();
    expect(factValueText("x.y", true)).toBe("Yes");
    expect(factValueText("x.y", "   ")).toBeNull();
  });
  it("lists proposals waiting for approval first, with a chip for where each came from", () => {
    const facts = adaptFacts(
      {
        data: [
          fact({}),
          fact({
            fact_key: "business.website",
            value: "https://a.example.test",
            authority: "system_derived",
            fact_identity: id(11),
          }),
          fact({
            fact_key: "business.hours",
            value: { periods: [] },
            fact_identity: id(12),
          }),
        ],
      },
      { data: [fact({ value: "Cococabana Kitchen" })] },
    );
    const rows = factRows(facts.effective, facts.waiting);
    // A value with nothing sensible to say is left out rather than shown as blank or as raw data.
    expect(rows.map((r) => r.value)).toEqual([
      "Cococabana Kitchen",
      "Cococabana",
      "https://a.example.test",
    ]);
    expect(rows[0].chip.label).toBe("Waiting for approval");
    expect(rows[0].waiting).toBe(true);
    expect(rows[1].chip).toEqual(factSourceChips.operator_verified);
    expect(rows[2].chip.label).toBe("Found by LILOs");
    expect(rows.every((r) => !/\./.test(r.label))).toBe(true);
  });
  it("builds a typed proposal and chains a change to the fact it replaces", () => {
    const name = FACT_FIELDS.find((f) => f.id === "name")!;
    expect(
      factProposal(
        name,
        { value: "  New Name " },
        { identity: id(10), locationId: null },
      ),
    ).toEqual({
      fact_identity: id(10),
      location_id: null,
      fact_key: "business.name",
      value_type: "string",
      value: "New Name",
      source: "console",
      authority: "operator_verified",
      change_reason: "Updated from client settings",
    });
    const claims = FACT_FIELDS.find((f) => f.id === "claims")!;
    expect(
      factProposal(claims, {
        value: "One\n\n  Two  \n",
        reason: "Menu change",
      }),
    ).toMatchObject({
      value_type: "string_list",
      value: ["One", "Two"],
      change_reason: "Menu change",
    });
    const address = FACT_FIELDS.find((f) => f.id === "address")!;
    const proposal = factProposal(
      address,
      {
        address_line_1: "1 A St",
        city: "Town",
        region: "CA",
        postal_code: "90000",
      },
      undefined,
      id(2),
    );
    expect(proposal).toMatchObject({
      value_type: "object",
      location_id: id(2),
      value: {
        address_line_1: "1 A St",
        address_line_2: null,
        country_code: "US",
      },
    });
    expect("fact_identity" in proposal).toBe(false);
    expect(factFormComplete(address, { address_line_1: "1 A St" })).toBe(false);
    expect(factFormComplete(name, { value: " " })).toBe(false);
    expect(factFormComplete(name, { value: "Yes" })).toBe(true);
  });
});
describe("administration BFF allow-list", () => {
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
    userId: id(1),
    token: "server-only",
    binding: "synthetic-binding",
    csrf: "",
    correlationId: "admin-test",
    auth: {} as App.Locals["auth"],
  };
  const request = (path: string, method: string, body?: unknown) =>
    new Request(settings.origin + "/api/" + path, {
      method,
      headers: {
        origin: settings.origin,
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfToken(locals.binding, id(1), settings.csrfSecret),
      },
      ...(method === "GET" ? {} : { body: JSON.stringify(body) }),
    });
  const upstream = () =>
    vi.fn(
      async (_url: RequestInfo | URL, _init?: RequestInit) =>
        new Response(JSON.stringify({ data: {} }), {
          headers: { "Content-Type": "application/json" },
        }),
    );
  const status = async (
    path: string,
    method: string,
    body?: unknown,
    fetcher = upstream(),
  ) =>
    (
      await forward(
        request(path, method, body),
        path.split("?", 1)[0],
        locals,
        fetcher,
      )
    ).status;
  const platform = `platform/organizations`;
  const client = `organizations/${id(1)}`;
  it("forwards each lifecycle call with exactly its body to the exact route", async () => {
    const fetcher = upstream();
    const calls: [string, string, unknown][] = [
      [
        `${platform}/${id(1)}/start-offboarding/`,
        "POST",
        { expected_version: 3 },
      ],
      [`${platform}/${id(1)}/archive/`, "POST", { expected_version: 3 }],
      [`${platform}/${id(1)}/remove/`, "POST", { confirm_name: "Cococabana" }],
      [
        `${platform}/${id(1)}/remove/`,
        "POST",
        { confirm_name: "Cococabana", reason: "Duplicate" },
      ],
      ...[
        "activate",
        "pause",
        "close-temporarily",
        "close-permanently",
        "archive",
      ].map((step): [string, string, unknown] => [
        `${client}/locations/${id(2)}/${step}/`,
        "POST",
        { expected_version: 2 },
      ]),
      [
        `${client}/business-facts/${id(3)}/decision/`,
        "POST",
        { decision: "approve" },
      ],
    ];
    for (const [path, method, body] of calls)
      expect(await status(path, method, body, fetcher)).toBe(200);
    expect(fetcher).toHaveBeenCalledTimes(calls.length);
    const urls = fetcher.mock.calls.map((call) => String(call[0]));
    expect(urls[0]).toBe(
      `https://api.test/api/v1/platform/organizations/${id(1)}/start-offboarding`,
    );
    expect(urls[4]).toBe(
      `https://api.test/api/v1/organizations/${id(1)}/locations/${id(2)}/activate`,
    );
  });
  it("forwards the reads, with only their own query", async () => {
    const fetcher = upstream();
    for (const path of [
      `${platform}/`,
      `${platform}/${id(1)}/removal/`,
      `${platform}/${id(1)}/locations/`,
      `${client}/locations/`,
      `${client}/business-facts/effective/`,
      `${client}/business-facts/candidates/`,
    ])
      expect(await status(path, "GET", undefined, fetcher)).toBe(200);
    expect(await status(`${platform}/?limit=100&offset=0`, "GET")).toBe(200);
    expect(await status(`${platform}/?limit=101`, "GET")).toBe(400);
    expect(await status(`${platform}/?sort=name`, "GET")).toBe(400);
  });
  it("refuses wrong methods, loose bodies and invented routes", async () => {
    const fetcher = upstream();
    const bad = async (path: string, method: string, body?: unknown) =>
      expect(await status(path, method, body, fetcher)).not.toBe(200);
    // A read cannot be written, and a write cannot be read.
    await bad(`${platform}/`, "POST", {});
    await bad(`${platform}/${id(1)}/archive/`, "GET");
    await bad(`${client}/locations/`, "POST", {});
    await bad(`${platform}/${id(1)}/`, "DELETE");
    // Bodies are strict: no extra field, no missing one, no wrong type.
    await bad(`${platform}/${id(1)}/archive/`, "POST", {
      expected_version: 3,
      force: true,
    });
    await bad(`${platform}/${id(1)}/archive/`, "POST", {});
    await bad(`${platform}/${id(1)}/archive/`, "POST", {
      expected_version: "3",
    });
    await bad(`${platform}/${id(1)}/archive/`, "POST", { expected_version: 0 });
    await bad(`${platform}/${id(1)}/remove/`, "POST", { confirm_name: "" });
    await bad(`${platform}/${id(1)}/remove/`, "POST", { expected_version: 1 });
    await bad(`${client}/locations/${id(2)}/pause/`, "POST", {
      status: "paused",
    });
    await bad(`${client}/business-facts/${id(3)}/decision/`, "POST", {
      decision: "delete",
    });
    // Routes that do not exist stay closed.
    await bad(`${client}/locations/${id(2)}/delete/`, "POST", {
      expected_version: 1,
    });
    await bad(`${client}/locations/${id(2)}/set-primary/`, "POST", {
      expected_version: 1,
    });
    await bad(`${platform}/${id(1)}/activate/`, "POST", {
      expected_version: 1,
    });
    await bad(`${platform}/not-a-uuid/archive/`, "POST", {
      expected_version: 1,
    });
    await bad(`${client}/business-facts/resolve/x/`, "GET");
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("accepts only a typed business fact proposal", async () => {
    const fetcher = upstream();
    const proposal = {
      fact_key: "business.name",
      value_type: "string",
      value: "Cococabana",
      source: "console",
      authority: "operator_verified",
      change_reason: "Updated from client settings",
    };
    expect(
      await status(`${client}/business-facts/`, "POST", proposal, fetcher),
    ).toBe(200);
    expect(
      await status(
        `${client}/business-facts/`,
        "POST",
        { ...proposal, fact_identity: id(4), location_id: null },
        fetcher,
      ),
    ).toBe(200);
    for (const bad of [
      { ...proposal, fact_key: "tax.registration_number" },
      { ...proposal, authority: "client_approved" },
      { ...proposal, source: "somewhere" },
      { ...proposal, value_type: "boolean" },
      { ...proposal, status: "active" },
      { ...proposal, value: { nested: { deeper: 1 } } },
      { ...proposal, value: "" },
      { ...proposal, change_reason: "" },
    ])
      expect(
        await status(`${client}/business-facts/`, "POST", bad, fetcher),
      ).toBe(400);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });
  it("keeps the CSRF and origin boundary on every write", async () => {
    const fetcher = upstream();
    const path = `${platform}/${id(1)}/archive/`;
    const forged = new Request(settings.origin + "/api/" + path, {
      method: "POST",
      headers: {
        origin: "https://evil.test",
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfToken(locals.binding, id(1), settings.csrfSecret),
      },
      body: JSON.stringify({ expected_version: 1 }),
    });
    expect((await forward(forged, path, locals, fetcher)).status).toBe(403);
    expect(fetcher).not.toHaveBeenCalled();
  });
});
