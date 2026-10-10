// Synthetic website-publishing feeds for browser tests only. Never imported by the app.
export const modes = [
  "not_linked",
  "linked",
  "github_not_connected",
  "format_unverified",
  "no_access",
  "repositories_fail",
  "repositories_empty",
  "link_unverified",
];
export const state = { mode: "not_linked", requests: [], created: new Map() };
export function reset(mode) {
  state.mode = mode;
  state.requests = [];
  state.created = new Map();
}
const repositories = [
  {
    repository_id: "LilosG/other-site",
    name: "other-site",
    default_branch: "main",
    private: true,
    format_verified: true,
    suggested: false,
  },
  {
    repository_id: "LilosG/unchecked-site",
    name: "unchecked-site",
    default_branch: "trunk",
    private: false,
    format_verified: false,
    suggested: false,
  },
  {
    repository_id: "LilosG/synthetic-site",
    name: "synthetic-site",
    default_branch: "main",
    private: true,
    format_verified: true,
    suggested: true,
  },
];
const setup = (state_, repository, branch) => ({
  state: state_,
  repository,
  branch,
  can_manage: true,
});
export function publishing() {
  switch (state.mode) {
    case "linked":
      return setup("linked", "LilosG/synthetic-site", "main");
    case "format_unverified":
      return setup("format_unverified", "LilosG/unchecked-site", "trunk");
    case "github_not_connected":
      return setup("github_not_connected", null, null);
    case "no_access":
      return null;
    default:
      return setup("not_linked", null, null);
  }
}
/** Returns {status, body} for a publishing route, or null for any other path. */
export function handle(path, method, headers, parsed, claims) {
  if (path === "integrations/github/install" && method === "POST") {
    state.requests.push({ path, method });
    return {
      status: 200,
      body: {
        data: {
          authorization_url:
            "https://github.com/apps/lilos-growth-operations/installations/new?state=synthetic",
          reconciled: false,
        },
      },
    };
  }
  if (!path.startsWith("command-center/integrations/publishing/")) return null;
  const aal2 = claims.aal === "aal2";
  if (!aal2)
    return { status: 403, body: { error: { code: "PERMISSION_DENIED" } } };
  if (path.endsWith("/repositories") && method === "GET") {
    if (state.mode === "repositories_fail")
      return {
        status: 502,
        body: { error: { code: "PUBLISHING_REPOSITORIES_UNAVAILABLE" } },
      };
    return {
      status: 200,
      body: {
        repositories: state.mode === "repositories_empty" ? [] : repositories,
      },
    };
  }
  if (path.endsWith("/target") && method === "POST") {
    const key = headers["idempotency-key"];
    state.requests.push({ path, method, key, body: parsed });
    if (!key)
      return { status: 422, body: { error: { code: "VALIDATION_FAILED" } } };
    if (state.created.has(key))
      return {
        status: 200,
        body: { ...state.created.get(key), replayed: true },
      };
    const repo = repositories.find(
      (r) => r.repository_id === parsed.repository_id,
    );
    if (!repo)
      return {
        status: 404,
        body: { error: { code: "PUBLISHING_REPOSITORY_NOT_ACCESSIBLE" } },
      };
    if (!repo.format_verified || state.mode === "link_unverified")
      return {
        status: 409,
        body: { error: { code: "PUBLISHING_FORMAT_UNVERIFIED" } },
      };
    const result = {
      repository: repo.repository_id,
      branch: repo.default_branch,
      replayed: false,
    };
    state.created.set(key, result);
    state.mode = "linked";
    return { status: 201, body: result };
  }
  return null;
}
