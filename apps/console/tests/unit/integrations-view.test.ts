import { describe, it, expect } from "vitest";
import {
  failureView,
  githubInstallTarget,
  googleAuthTarget,
  propertyName,
  publishingRow,
} from "../../src/lib/integrations-view";
import { adaptRepositories } from "../../src/adapters/publishing";
import { filterAssets, folderOf } from "../../src/lib/image-picker";
import { ago } from "../../src/lib/present";
import type { IntegrationsView } from "../../src/adapters/local-search";
const view = (publishing: IntegrationsView["publishing"]) =>
  ({ publishing, github_status: "connected" }) as IntegrationsView;
const setup = (
  state: NonNullable<IntegrationsView["publishing"]>["state"],
  can_manage = true,
) => ({ state, repository: "LilosG/site", branch: "main", can_manage });
describe("publishing row", () => {
  it("says ready, with repository and branch", () => {
    const row = publishingRow(view(setup("linked")));
    expect(row.chip.label).toBe("Ready to publish");
    expect(row.detail).toBe("LilosG/site · Branch main");
    expect(row.action).toBe("none");
  });
  it("offers Select repository only to a verified manager", () => {
    expect(publishingRow(view(setup("not_linked"))).action).toBe("select");
    expect(publishingRow(view(setup("not_linked", false))).action).toBe(
      "verify",
    );
  });
  it("connects GitHub, pauses on an unchecked format, and hides without access", () => {
    expect(publishingRow(view(setup("github_not_connected"))).action).toBe(
      "connect_github",
    );
    expect(publishingRow(view(setup("format_unverified"))).chip.label).toBe(
      "Blog format not checked yet",
    );
    expect(publishingRow(view(null)).chip.label).toBe("No access");
  });
});
describe("names and targets", () => {
  it("reads a property as the site it names", () => {
    expect(propertyName("sc-domain:example.test", null)).toBe("example.test");
    expect(propertyName("https://www.example.test/", null)).toBe(
      "example.test",
    );
    expect(propertyName("x", "Main site")).toBe("Main site");
  });
  it("follows only GitHub's and Google's own addresses", () => {
    expect(
      githubInstallTarget("https://github.com/apps/lilos/installations/new"),
    ).toContain("github.com/apps/");
    expect(githubInstallTarget("https://evil.test/apps/x")).toBeNull();
    expect(githubInstallTarget("https://github.com/evil")).toBeNull();
    expect(
      googleAuthTarget("https://accounts.google.com/o/oauth2/v2/auth?x=1"),
    ).not.toBeNull();
    expect(
      googleAuthTarget("https://accounts.google.com.evil.test/"),
    ).toBeNull();
  });
  it("turns every code into words and a next step, never the code", () => {
    expect(failureView("AAL2_REQUIRED").next).toBe("verify");
    expect(failureView("PUBLISHING_FORMAT_UNVERIFIED").text).not.toMatch(
      /PUBLISHING_/,
    );
    expect(failureView("SOMETHING_NEW").next).toBe("retry");
  });
});
describe("repositories adapter", () => {
  const repo = (id: string, suggested = false) => ({
    repository_id: id,
    name: id,
    default_branch: "main",
    private: true,
    format_verified: true,
    suggested,
  });
  it("accepts a list and fails closed on duplicates or two suggestions", () => {
    expect(adaptRepositories({ repositories: [repo("a")] })).toHaveLength(1);
    expect(() =>
      adaptRepositories({ repositories: [repo("a"), repo("a")] }),
    ).toThrow();
    expect(() =>
      adaptRepositories({
        repositories: [repo("a", true), repo("b", true)],
      }),
    ).toThrow();
    expect(() => adaptRepositories({ repositories: "x" })).toThrow();
  });
});
describe("image picker helpers", () => {
  const list = [
    { path: "/synthetic.webp", name: "synthetic.webp" },
    { path: "/images/blog/wings.jpg", name: "wings.jpg" },
  ];
  it("shows the folder and filters by every word", () => {
    expect(folderOf("/images/blog/wings.jpg")).toBe("/images/blog/");
    expect(folderOf("/synthetic.webp")).toBe("Top level");
    expect(filterAssets(list, "blog WINGS")).toHaveLength(1);
    expect(filterAssets(list, "")).toHaveLength(2);
    expect(filterAssets(list, "zzz")).toHaveLength(0);
  });
});
describe("ago", () => {
  const now = new Date("2026-10-09T12:00:00Z");
  it("reads relative times and never an ISO string", () => {
    expect(ago("2026-10-09T11:59:40Z", now)).toBe("just now");
    expect(ago("2026-10-09T11:55:00Z", now)).toBe("5 minutes ago");
    expect(ago("2026-10-09T09:00:00Z", now)).toBe("3 hours ago");
    expect(ago("2026-10-07T12:00:00Z", now)).toBe("2 days ago");
    expect(ago("2026-10-08T12:00:00Z", now)).toBe("1 day ago");
    expect(ago("2026-07-01T12:00:00Z", now)).toBe("Jul 1, 2026");
    expect(ago(null, now)).toBe("");
  });
});
