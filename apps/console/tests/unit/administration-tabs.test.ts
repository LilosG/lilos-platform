import { describe, expect, it, vi } from "vitest";
import {
  adaptOnboarding,
  adaptSystem,
  adaptUsers,
  type OrganizationRecord,
  type SystemRecord,
} from "../../src/adapters/administration";
import {
  activateConfirm,
  administrationFailureText,
  blockerRows,
  cancelInvitationConfirm,
  componentRows,
  deadLetterReasonText,
  isOnboarding,
  onboardingRows,
  personRows,
  personState,
  roleText,
  systemDetails,
  userPaging,
} from "../../src/lib/administration-view";
import {
  healthChips,
  onboardingChips,
  personChips,
} from "../../src/lib/status";
import { forward } from "../../src/server/bff";
import { csrfToken } from "../../src/server/security";
const id = (n: number) =>
  `${String(n).padStart(8, "0")}-0000-4000-8000-000000000000`;
const org = (over: Partial<OrganizationRecord> = {}): OrganizationRecord => ({
  id: id(1),
  name: "Juniper Living",
  slug: "juniper-living",
  status: "onboarding",
  website_url: "https://www.juniper.example.test/menu",
  version: 3,
  ...over,
});
const state = (over: Record<string, unknown> = {}) => ({
  data: {
    organization_id: id(1),
    organization_version: 5,
    progress_percent: 40,
    activation_eligible: false,
    blockers: ["A sentence that must never be kept."],
    blocker_details: [
      {
        message: "A sentence that must never be kept.",
        resolution: {
          step_key: "locations",
          route: "/onboarding",
          control: "locations",
          permission: "locations.create",
          label: "A label that must never be kept",
        },
        product_name: null,
      },
    ],
    ...over,
  },
});

describe("onboarding adapter", () => {
  it("keeps the control and route, never the sentences", () => {
    const record = adaptOnboarding(state());
    expect(record).toEqual({
      progress_percent: 40,
      activation_eligible: false,
      version: 5,
      blockers: [{ control: "locations", route: "/onboarding" }],
    });
    expect(JSON.stringify(record)).not.toContain("never be kept");
  });
  it("refuses a state it does not understand", () => {
    expect(() => adaptOnboarding(state({ progress_percent: 140 }))).toThrow();
    expect(() => adaptOnboarding(state({ blocker_details: [{}] }))).toThrow();
    expect(() => adaptOnboarding({ data: {} })).toThrow();
  });
});

describe("onboarding rows", () => {
  it("lists only clients that are not live", () => {
    expect(isOnboarding("prospect")).toBe(true);
    expect(isOnboarding("onboarding")).toBe(true);
    for (const live of ["active", "paused", "offboarding", "archived"] as const)
      expect(isOnboarding(live)).toBe(false);
    const rows = onboardingRows(
      [org(), org({ id: id(2), status: "active" })],
      new Map(),
    );
    expect(rows).toHaveLength(1);
  });
  it("shows progress, links each blocker to the screen that fixes it, and activates only when eligible", () => {
    const blocked = onboardingRows(
      [org()],
      new Map([[id(1), adaptOnboarding(state())]]),
    )[0];
    expect(blocked).toMatchObject({
      percent: 40,
      canActivate: false,
      readiness: null,
      site: "juniper.example.test",
      version: 5,
    });
    expect(blocked.blockers).toEqual([
      {
        label: "Add or finish a location",
        href: "/clients/juniper-living/settings/",
        hrefLabel: "Open settings",
      },
    ]);
    const ready = onboardingRows(
      [org()],
      new Map([
        [
          id(1),
          adaptOnboarding(
            state({
              progress_percent: 100,
              activation_eligible: true,
              blocker_details: [],
            }),
          ),
        ],
      ]),
    )[0];
    expect(ready).toMatchObject({
      percent: 100,
      canActivate: true,
      readiness: onboardingChips.ready,
    });
  });
  it("never shows an unreadable or unstarted client as 0%", () => {
    const [unreadable, prospect] = onboardingRows(
      [org(), org({ id: id(2), status: "prospect" })],
      new Map([[id(1), null]]),
    );
    expect(unreadable).toMatchObject({
      percent: null,
      unavailable: true,
      canActivate: false,
      readiness: onboardingChips.unavailable,
    });
    expect(prospect).toMatchObject({
      percent: null,
      unavailable: false,
      canActivate: false,
      readiness: onboardingChips.not_started,
    });
    // A client absent from the map was never read: unknown, not "fine".
    expect(onboardingRows([org()], new Map())[0].unavailable).toBe(true);
  });
  it("sends a blocker to a console screen only when one can fix it", () => {
    const rows = blockerRows(
      [
        { control: "locations", route: "/onboarding" },
        { control: "connections", route: "/integrations" },
        { control: "business-facts", route: "/onboarding" },
        { control: "organization-profile", route: "/onboarding" },
        { control: "locations", route: "/onboarding" },
        { control: "something-new", route: "/elsewhere" },
      ],
      "harbor-grill",
    );
    expect(rows.map((r) => r.href)).toEqual([
      "/clients/harbor-grill/settings/",
      "/clients/harbor-grill/integrations/",
      "/clients/harbor-grill/settings/",
      null,
      null,
    ]);
    expect(rows.at(-1)?.label).toBe("Finish a setup step");
    for (const row of rows) expect(row.label).not.toMatch(/[-_/]|\bcontrol\b/);
  });
  it("words activation and its refusals for a person", () => {
    const copy = activateConfirm("Juniper Living");
    expect(copy).toMatchObject({
      title: "Activate Juniper Living?",
      accept: "Activate client",
      typedName: null,
      tone: "normal",
    });
    expect(administrationFailureText("ONBOARDING_INCOMPLETE")).toContain(
      "Setup is not complete",
    );
    expect(administrationFailureText("NO_PRIMARY_DOMAIN")).toContain(
      "website address",
    );
    expect(administrationFailureText("ORGANIZATION_VERSION_CONFLICT")).toMatch(
      /changed since/,
    );
    for (const code of [
      "ONBOARDING_INCOMPLETE",
      "NO_PRIMARY_DOMAIN",
      "INVITATION_VERSION_CONFLICT",
      "INVITATION_CONFLICT",
      "INVITATION_NOT_FOUND",
      "ACCESS_PARENT_STATE_CONFLICT",
      "SOMETHING_UNSEEN",
    ])
      expect(administrationFailureText(code)).not.toMatch(/[A-Z]+_[A-Z]+/);
  });
});

const access = (over: Record<string, unknown> = {}) => ({
  organization_id: id(10),
  organization_name: "Synthetic Alpha",
  membership_type: "client",
  membership_status: "active",
  roles: ["organization_owner"],
  invitation: null,
  ...over,
});
const user = (over: Record<string, unknown> = {}) => ({
  id: id(20),
  display_name: "Dana Rivera",
  email: "dana@example.test",
  status: "active",
  platform_administrator: false,
  access: [access()],
  access_total: 1,
  ...over,
});
const page = (items: unknown[], next: number | null = null) => ({
  data: { items, limit: 50, offset: 0, next_offset: next, has_more: !!next },
});

describe("users", () => {
  it("parses people and refuses an unknown status or role", () => {
    expect(adaptUsers(page([user()], 50))).toMatchObject({
      next_offset: 50,
      people: [{ display_name: "Dana Rivera" }],
    });
    expect(() =>
      adaptUsers(page([user({ access: [access({ roles: ["root"] })] })])),
    ).toThrow();
    expect(() =>
      adaptUsers(
        page([user({ access: [access({ membership_status: "?" })] })]),
      ),
    ).toThrow();
    expect(() => adaptUsers(page([user({ status: "gone" })]))).toThrow();
  });
  it("shows name and email, role labels, clients and a status chip", () => {
    const [dana] = personRows(adaptUsers(page([user()])).people);
    expect(dana).toMatchObject({
      name: "Dana Rivera",
      email: "dana@example.test",
      roles: "Owner",
      clients: [{ name: "Synthetic Alpha", chip: null }],
      moreClients: 0,
      chip: personChips.active,
      invitations: [],
    });
  });
  it("falls back to the email when there is no name, and never shows it twice", () => {
    const [row] = personRows(
      adaptUsers(page([user({ display_name: null })])).people,
    );
    expect(row.name).toBe("dana@example.test");
    expect(row.email).toBeNull();
    const [nobody] = personRows(
      adaptUsers(page([user({ display_name: null, email: null })])).people,
    );
    expect(nobody.name).toBe("Unnamed person");
  });
  it("derives one standing from every client a person reaches", () => {
    const standing = (over: Record<string, unknown>) =>
      personState(adaptUsers(page([user(over)])).people[0]);
    const withStatus = (...statuses: string[]) => ({
      access: statuses.map((membership_status, n) =>
        access({ organization_id: id(30 + n), membership_status }),
      ),
    });
    expect(standing(withStatus("active", "invited"))).toBe("active");
    expect(standing(withStatus("invited"))).toBe("invited");
    expect(standing(withStatus("suspended", "invited"))).toBe("invited");
    expect(standing(withStatus("suspended"))).toBe("suspended");
    expect(standing({ access: [] })).toBe("no_access");
    expect(standing({ access: [], platform_administrator: true })).toBe(
      "active",
    );
    expect(standing({ status: "deactivated", ...withStatus("active") })).toBe(
      "deactivated",
    );
  });
  it("lists roles in a fixed order, administrators first", () => {
    const person = adaptUsers(
      page([
        user({
          platform_administrator: true,
          access: [
            access({ roles: ["organization_viewer", "organization_manager"] }),
            access({ organization_id: id(11), roles: ["organization_owner"] }),
          ],
        }),
      ]),
    ).people[0];
    expect(roleText(person)).toBe(
      "Platform administrator, Owner, Manager, Viewer",
    );
    expect(roleText(adaptUsers(page([user({ access: [] })])).people[0])).toBe(
      "No role yet",
    );
  });
  it("caps the clients shown and counts the rest", () => {
    const many = Array.from({ length: 5 }, (_, n) =>
      access({ organization_id: id(40 + n), organization_name: `Client ${n}` }),
    );
    const [row] = personRows(
      adaptUsers(page([user({ access: many, access_total: 30 })])).people,
    );
    expect(row.clients.map((c) => c.name)).toEqual([
      "Client 0",
      "Client 1",
      "Client 2",
    ]);
    expect(row.moreClients).toBe(27);
  });
  it("offers to cancel exactly the pending invitations, with their versions", () => {
    const invited = access({
      membership_status: "invited",
      invitation: {
        id: id(50),
        version: 4,
        status: "pending",
        expires_at: "2026-10-19T19:00:00Z",
      },
    });
    const [row] = personRows(
      adaptUsers(page([user({ access: [invited] })])).people,
    );
    expect(row.invitations).toEqual([
      {
        invitationId: id(50),
        organizationId: id(10),
        client: "Synthetic Alpha",
        version: 4,
        expires: "Oct 19, 2026",
      },
    ]);
    expect(row.clients[0].chip).toBe(personChips.invited);
    const copy = cancelInvitationConfirm("Pat Lee", "Synthetic Alpha");
    expect(copy).toMatchObject({
      title: "Cancel Pat Lee's invitation?",
      accept: "Cancel invitation",
      dismiss: "Keep invitation",
    });
    expect(copy.lines.join(" ")).toContain("join Synthetic Alpha");
  });
  it("pages forward and back without inventing a page", () => {
    expect(userPaging(0, null, 50)).toEqual({ previous: null, next: null });
    expect(userPaging(0, 50, 50)).toEqual({
      previous: null,
      next: "/administration/users/?offset=50",
    });
    expect(userPaging(50, null, 50)).toEqual({
      previous: "/administration/users/",
      next: null,
    });
    expect(userPaging(100, 150, 50).previous).toBe(
      "/administration/users/?offset=50",
    );
  });
});

const healthy: SystemRecord = {
  overall: "healthy",
  evaluated_at: "2026-10-12T15:00:00Z",
  database: "healthy",
  scheduler: {
    status: "healthy",
    active_schedules: 12,
    last_dispatch_at: "2026-10-12T14:58:00Z",
    overdue: false,
  },
  queue: {
    status: "healthy",
    dead_letter_count: 0,
    groups: [],
    oldest_pending_at: null,
    backlogged: false,
  },
  failed_runs: { status: "healthy", failed_last_24h: 0 },
  integrations: { status: "healthy", needing_attention: 0 },
};
const raw = (over: Record<string, unknown> = {}) => ({
  data: {
    overall: "attention",
    evaluated_at: "2026-10-12T15:00:00Z",
    database: { status: "healthy" },
    scheduler: {
      status: "healthy",
      active_schedules: 1,
      last_dispatch_at: null,
      overdue: false,
    },
    worker_queue: {
      status: "attention",
      dead_letter_count: 3,
      dead_letter_groups: [{ reason: "permanent_failure", count: 3 }],
      oldest_pending_at: null,
      backlogged: false,
    },
    failed_runs: { status: "healthy", failed_last_24h: 0 },
    integrations: { status: "healthy", needing_attention: 0 },
    ...over,
  },
});

describe("system status", () => {
  it("parses typed facts and refuses an unknown state or reason", () => {
    expect(adaptSystem(raw()).queue.groups).toEqual([
      { reason: "permanent_failure", count: 3 },
    ]);
    expect(() => adaptSystem(raw({ overall: "fine" }))).toThrow();
    expect(() =>
      adaptSystem(
        raw({
          worker_queue: {
            status: "attention",
            dead_letter_count: 1,
            dead_letter_groups: [{ reason: "gremlins", count: 1 }],
            oldest_pending_at: null,
            backlogged: false,
          },
        }),
      ),
    ).toThrow();
  });
  it("describes a healthy platform in plain words", () => {
    const rows = componentRows(healthy);
    expect(rows.map((r) => r.chip)).toEqual(Array(5).fill(healthChips.healthy));
    expect(rows.map((r) => r.sentence)).toEqual([
      "The database is reachable.",
      "Scheduled work is being dispatched on time.",
      "Nothing has given up and nothing is waiting too long.",
      "No workflow runs failed in the last 24 hours.",
      "Every connection is working.",
    ]);
  });
  it("counts what needs attention, with the right plural", () => {
    const rows = componentRows({
      ...healthy,
      scheduler: { ...healthy.scheduler, status: "attention", overdue: true },
      queue: {
        ...healthy.queue,
        status: "attention",
        dead_letter_count: 1,
        backlogged: true,
      },
      failed_runs: { status: "attention", failed_last_24h: 1 },
      integrations: { status: "attention", needing_attention: 2 },
    });
    expect(rows[1].sentence).toBe("Scheduled work is running late.");
    expect(rows[2].sentence).toBe(
      "1 job gave up after failing, and due work is waiting longer than expected.",
    );
    expect(rows[3].sentence).toBe(
      "1 workflow run failed in the last 24 hours.",
    );
    expect(rows[4].sentence).toBe("2 connections need attention.");
    expect(rows[4].integrations).toBe(true);
    expect(rows[2].details).toBe(true);
    expect(rows[0].integrations).toBe(false);
  });
  it("says a part is unknown instead of healthy or zero, and offers no details of it", () => {
    const unknown = componentRows({
      ...healthy,
      overall: "unknown",
      scheduler: {
        status: "unknown",
        active_schedules: null,
        last_dispatch_at: null,
        overdue: null,
      },
      queue: {
        status: "unknown",
        dead_letter_count: null,
        groups: [],
        oldest_pending_at: null,
        backlogged: null,
      },
      failed_runs: { status: "unknown", failed_last_24h: null },
      integrations: { status: "unknown", needing_attention: null },
    });
    for (const row of unknown.slice(1)) {
      expect(row.chip).toBe(healthChips.unknown);
      expect(row.sentence).toMatch(/^We could not check/);
      expect(row.sentence).not.toMatch(/\d/);
      expect(row.details).toBe(false);
      expect(row.integrations).toBe(false);
    }
  });
  it("says so when no scheduled work exists rather than claiming it is on time", () => {
    const rows = componentRows({
      ...healthy,
      scheduler: { ...healthy.scheduler, active_schedules: 0 },
    });
    expect(rows[1].sentence).toBe("No scheduled work is set up yet.");
  });
  it("formats technical detail for the dialog only, never as ISO text", () => {
    const now = new Date("2026-10-12T15:10:00Z");
    const details = systemDetails(
      {
        ...healthy,
        queue: {
          ...healthy.queue,
          groups: [
            { reason: "lease_expired", count: 2 },
            { reason: "unrecorded", count: 1 },
          ],
          oldest_pending_at: "2026-10-12T14:00:00Z",
        },
      },
      now,
    );
    expect(details.checked).toBe("10 minutes ago");
    expect(details.oldestWaiting).toBe("1 hour ago");
    expect(details.lastDispatch).toMatch(/^Today · \d{1,2}:\d{2} [AP]M$/);
    expect(details.reasons).toEqual([
      { text: "The worker stopped responding", count: 2 },
      { text: "No reason was recorded", count: 1 },
    ]);
    expect(JSON.stringify(details)).not.toMatch(/\d{4}-\d{2}-\d{2}T|_/);
    expect(deadLetterReasonText("outcome_uncertain")).toBe(
      "The outcome could not be confirmed",
    );
    expect(systemDetails(healthy, now).oldestWaiting).toBeNull();
  });
});

describe("administration tabs BFF allow-list", () => {
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
    correlationId: "admin-tabs-test",
    auth: {} as App.Locals["auth"],
  };
  const upstream = () =>
    vi.fn(
      async (_url: RequestInfo | URL, _init?: RequestInit) =>
        new Response(JSON.stringify({ data: {} }), {
          headers: { "Content-Type": "application/json" },
        }),
    );
  const call = async (
    path: string,
    method: string,
    body?: unknown,
    fetcher = upstream(),
  ) =>
    (
      await forward(
        new Request(settings.origin + "/api/" + path, {
          method,
          headers: {
            origin: settings.origin,
            "Content-Type": "application/json",
            "X-CSRF-Token": csrfToken(
              locals.binding,
              id(1),
              settings.csrfSecret,
            ),
          },
          ...(method === "GET" ? {} : { body: JSON.stringify(body) }),
        }),
        path.split("?", 1)[0],
        locals,
        fetcher,
      )
    ).status;
  const platform = "platform/organizations";
  it("forwards the new reads and writes to the exact routes", async () => {
    const fetcher = upstream();
    expect(
      await call(
        `${platform}/${id(1)}/onboarding-state/`,
        "GET",
        undefined,
        fetcher,
      ),
    ).toBe(200);
    expect(
      await call("platform/system-status/", "GET", undefined, fetcher),
    ).toBe(200);
    expect(
      await call(
        "platform/users/?limit=50&offset=50",
        "GET",
        undefined,
        fetcher,
      ),
    ).toBe(200);
    expect(
      await call(
        `${platform}/${id(1)}/activate/`,
        "POST",
        { expected_version: 5 },
        fetcher,
      ),
    ).toBe(200);
    expect(
      await call(
        `${platform}/${id(1)}/invitations/${id(2)}/cancel/`,
        "POST",
        { expected_version: 1 },
        fetcher,
      ),
    ).toBe(200);
    expect(fetcher.mock.calls.map((c) => String(c[0]))).toEqual([
      `https://api.test/api/v1/platform/organizations/${id(1)}/onboarding-state`,
      "https://api.test/api/v1/platform/system-status",
      "https://api.test/api/v1/platform/users?limit=50&offset=50",
      `https://api.test/api/v1/platform/organizations/${id(1)}/activate`,
      `https://api.test/api/v1/platform/organizations/${id(1)}/invitations/${id(2)}/cancel`,
    ]);
  });
  it("refuses a wrong method, a loose body, a bad query and an invented route", async () => {
    const fetcher = upstream();
    const bad = async (path: string, method: string, body?: unknown) =>
      expect(await call(path, method, body, fetcher)).not.toBe(200);
    await bad(`${platform}/${id(1)}/activate/`, "GET");
    await bad(`${platform}/${id(1)}/onboarding-state/`, "POST", {});
    await bad(`${platform}/${id(1)}/activate/`, "POST", {});
    await bad(`${platform}/${id(1)}/activate/`, "POST", {
      expected_version: 1,
      force: true,
    });
    await bad(`${platform}/${id(1)}/invitations/${id(2)}/cancel/`, "GET");
    await bad(`${platform}/${id(1)}/invitations/${id(2)}/cancel/`, "POST", {
      expected_version: "1",
    });
    await bad(`${platform}/${id(1)}/invitations/not-a-uuid/cancel/`, "POST", {
      expected_version: 1,
    });
    await bad(`${platform}/${id(1)}/invitations/${id(2)}/resend/`, "POST", {
      expected_version: 1,
    });
    await bad("platform/users/", "POST", {});
    await bad("platform/users/?limit=101", "GET");
    await bad("platform/users/?email=a@b.test", "GET");
    await bad("platform/system-status/", "POST", {});
    await bad("platform/system-status/?refresh=1", "GET");
    expect(fetcher).not.toHaveBeenCalled();
  });
});
