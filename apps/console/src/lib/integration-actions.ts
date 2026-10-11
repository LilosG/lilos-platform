import { z } from "zod";
import { action, ApiFailure, call } from "./api-client";
import {
  failureView,
  githubInstallTarget,
  googleAuthTarget,
} from "./integrations-view";
import {
  adaptRepositories,
  type PublishingRepository,
} from "../adapters/publishing";
import { unverifiedFormatChip } from "./status";
const $ = <T extends HTMLElement>(selector: string) =>
  document.querySelector<T>(selector);
const codeOf = (error: unknown) =>
  error instanceof ApiFailure ? error.code : "UNKNOWN";
let retry: (() => void) | null = null;
/** A failure is a designed banner with a next step, never the API's words. */
function showFailure(error: unknown, again?: () => void) {
  const host = $("[data-integration-error]");
  if (!host) return;
  const view = failureView(codeOf(error));
  const title = host.querySelector(".body-title");
  const text = host.querySelector("[data-error-text]");
  if (title) title.textContent = view.title;
  if (text) text.textContent = view.text;
  retry = again ?? null;
  host
    .querySelector<HTMLElement>("[data-error-retry]")!
    .toggleAttribute("hidden", !(view.next === "retry" && again));
  host
    .querySelector<HTMLElement>("[data-error-verify]")!
    .toggleAttribute("hidden", view.next !== "verify");
  host
    .querySelector<HTMLElement>("[data-error-refresh]")!
    .toggleAttribute(
      "hidden",
      view.next === "verify" || (view.next === "retry" && Boolean(again)),
    );
  host.hidden = false;
  host.scrollIntoView({ block: "nearest" });
}
const clearFailure = () => {
  const host = $("[data-integration-error]");
  if (host) host.hidden = true;
};
const say = (text: string) => {
  const node = $("[data-integration-status]");
  if (node) node.textContent = text;
};
/** Ask first; resolves true only on an explicit confirm. */
function confirmFirst(button: HTMLElement): Promise<boolean> {
  const dialog = $<HTMLDialogElement>("#integration-confirm");
  if (!button.dataset.confirmTitle || !dialog) return Promise.resolve(true);
  dialog.querySelector("[data-confirm-heading]")!.textContent =
    button.dataset.confirmTitle;
  dialog.querySelector("[data-confirm-body]")!.textContent =
    button.dataset.confirmText ?? "";
  const accept = dialog.querySelector<HTMLButtonElement>(
    "[data-confirm-accept]",
  )!;
  accept.textContent = button.dataset.confirmLabel ?? "Confirm";
  return new Promise((resolve) => {
    const finish = (answer: boolean) => {
      dialog.close();
      accept.onclick = null;
      dialog.querySelector<HTMLButtonElement>(
        "[data-confirm-cancel]",
      )!.onclick = null;
      resolve(answer);
    };
    accept.onclick = () => finish(true);
    dialog.querySelector<HTMLButtonElement>("[data-confirm-cancel]")!.onclick =
      () => finish(false);
    dialog.addEventListener("cancel", () => resolve(false), { once: true });
    dialog.showModal();
  });
}
function bindButtons() {
  document
    .querySelectorAll<HTMLButtonElement>("button[data-action]")
    .forEach((button) =>
      button.addEventListener("click", async () => {
        if (!(await confirmFirst(button))) return;
        clearFailure();
        button.disabled = true;
        say("Working on it…");
        try {
          const data = await action(
            button.dataset.action!,
            JSON.parse(button.dataset.body ?? "{}"),
            button.dataset.method,
          );
          if (button.hasAttribute("data-oauth")) {
            const target = googleAuthTarget(
              z.object({ authorization_url: z.url() }).parse(data)
                .authorization_url,
            );
            if (!target) throw new ApiFailure("OAUTH_TARGET_INVALID");
            window.location.assign(target);
          } else window.location.reload();
        } catch (error) {
          button.disabled = false;
          say("");
          showFailure(error, () => button.click());
        }
      }),
    );
}
function bindMatching() {
  document.querySelectorAll<HTMLFormElement>("[data-mapping]").forEach((form) =>
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      clearFailure();
      const values = new FormData(form);
      const submit = form.querySelector<HTMLButtonElement>(
        'button[type="submit"]',
      )!;
      submit.disabled = true;
      try {
        const location = z.uuid().parse(values.get("location_id"));
        await action(
          form.dataset.api! +
            `locations/${location}/gbp-mapping/${form.dataset.profile}/confirm/`,
          { location_id: location, write_enabled: values.has("write_enabled") },
        );
        window.location.reload();
      } catch (error) {
        submit.disabled = false;
        showFailure(error);
      }
    }),
  );
  const searchProperty = z.object({
    external_property_id: z.string(),
    property_type: z.enum(["domain", "url_prefix"]),
  });
  const analyticsProperty = z.object({
    external_property_id: z.string(),
    property_number: z.string(),
    display_name: z.string(),
  });
  document
    .querySelectorAll<HTMLFormElement>("[data-discovery]")
    .forEach((form) =>
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        clearFailure();
        const analytics = form.dataset.source === "analytics";
        const api = form.dataset.api!;
        const container = form.querySelector<HTMLElement>("[data-discovered]")!;
        container.replaceChildren();
        const submit = form.querySelector<HTMLButtonElement>(
          'button[type="submit"]',
        )!;
        submit.disabled = true;
        try {
          const website = z.uuid().parse(new FormData(form).get("website_id"));
          const data = await action(
            analytics
              ? api + "insights/analytics/discover/"
              : api + `seo/websites/${website}/search-console/discover/`,
            { website_id: website },
            analytics ? "POST" : "GET",
          );
          const rows = analytics
            ? z.object({ properties: z.array(analyticsProperty) }).parse(data)
                .properties
            : z.object({ properties: z.array(searchProperty) }).parse(data)
                .properties;
          say(
            rows.length
              ? "Choose the property that belongs to this client."
              : "Google shared no properties with this account. Nothing was matched.",
          );
          for (const row of rows) {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "control";
            button.textContent = `Match ${"display_name" in row ? row.display_name : row.external_property_id.replace(/^sc-domain:/, "")}`;
            button.addEventListener("click", async () => {
              button.disabled = true;
              try {
                await action(
                  api +
                    `integrations/google/${analytics ? "analytics" : "search-console"}/properties/map/`,
                  { website_id: website, ...row },
                );
                window.location.reload();
              } catch (error) {
                button.disabled = false;
                showFailure(error);
              }
            });
            container.append(button);
          }
        } catch (error) {
          showFailure(error, () => form.requestSubmit());
        } finally {
          submit.disabled = false;
        }
      }),
    );
}
function bindGitHub() {
  document
    .querySelectorAll<HTMLButtonElement>("[data-github-install]")
    .forEach((button) =>
      button.addEventListener("click", async () => {
        clearFailure();
        button.disabled = true;
        try {
          const data = z
            .object({ authorization_url: z.string(), reconciled: z.boolean() })
            .parse(
              await action(button.dataset.githubInstall!, {
                return_app: "console",
              }),
            );
          // Already installed: the API reconciled it, so this screen only needs to show the result.
          if (data.reconciled) return window.location.reload();
          const target = githubInstallTarget(data.authorization_url);
          if (!target) throw new ApiFailure("OAUTH_TARGET_INVALID");
          window.location.assign(target);
        } catch (error) {
          button.disabled = false;
          showFailure(error, () => button.click());
        }
      }),
    );
}
const newKey = () => crypto.randomUUID();
function bindRepositories() {
  const open = $<HTMLElement>("[data-repository-open]");
  const dialog = $<HTMLDialogElement>("#repository-dialog");
  if (!open || !dialog) return;
  const base = open.dataset.repositoryOpen!;
  const part = (name: string) =>
    dialog.querySelector<HTMLElement>(`[data-repo-${name}]`)!;
  const confirm = part("confirm") as HTMLButtonElement;
  const list = part("list");
  let chosen: PublishingRepository | null = null;
  // One key per chosen repository; kept across an unclear answer so a retry cannot link twice.
  let key = newKey();
  const show = (which: "loading" | "empty" | "error" | "list") => {
    for (const name of ["loading", "empty", "error", "list"])
      part(name).hidden = name !== which;
  };
  const render = (repos: PublishingRepository[]) => {
    list.replaceChildren();
    const ordered = [...repos].sort(
      (a, b) =>
        Number(b.suggested) - Number(a.suggested) ||
        Number(b.format_verified) - Number(a.format_verified) ||
        a.name.localeCompare(b.name),
    );
    for (const repo of ordered) {
      const item = document.createElement("li");
      const pick = document.createElement("button");
      pick.type = "button";
      pick.setAttribute("aria-pressed", "false");
      pick.disabled = !repo.format_verified;
      const label = document.createElement("span");
      const name = document.createElement("b");
      name.textContent = repo.name;
      const sub = document.createElement("small");
      sub.textContent = `${repo.private ? "Private" : "Public"} · Branch ${repo.default_branch}`;
      label.append(name, sub);
      pick.append(label);
      const chips = document.createElement("span");
      if (repo.suggested) chips.append(chip("Suggested", ""));
      if (!repo.format_verified)
        chips.append(
          chip(unverifiedFormatChip.label, unverifiedFormatChip.tone),
        );
      pick.append(chips);
      pick.addEventListener("click", () => {
        chosen = repo;
        key = newKey();
        list
          .querySelectorAll("button")
          .forEach((b) => b.setAttribute("aria-pressed", String(b === pick)));
        confirm.disabled = false;
      });
      item.append(pick);
      list.append(item);
    }
    show(ordered.length ? "list" : "empty");
  };
  const chip = (text: string, tone: string) => {
    const node = document.createElement("span");
    node.className = `badge ${tone}`.trim();
    node.textContent = text;
    return node;
  };
  async function load() {
    chosen = null;
    confirm.disabled = true;
    part("status").textContent = "";
    show("loading");
    try {
      render(adaptRepositories(await call(base + "repositories/", {}, "GET")));
    } catch (error) {
      part("error-text").textContent = failureView(codeOf(error)).text;
      show("error");
    }
  }
  open.addEventListener("click", load);
  part("retry").addEventListener("click", load);
  confirm.addEventListener("click", async () => {
    if (!chosen) return;
    confirm.disabled = true;
    part("status").textContent = "Linking the repository…";
    try {
      await call(
        base + "target/",
        { repository_id: chosen.repository_id },
        "POST",
        { "Idempotency-Key": key },
      );
      window.location.reload();
    } catch (error) {
      part("status").textContent = "";
      const view = failureView(codeOf(error));
      part("error-text").textContent = view.text;
      show("error");
      // A definite refusal means the next try is a new request; an unclear one keeps its key.
      if (error instanceof ApiFailure && !error.code.startsWith("MUTATION_"))
        key = newKey();
    }
  });
}
function initialize() {
  bindButtons();
  bindMatching();
  bindGitHub();
  bindRepositories();
  $("[data-error-retry]")?.addEventListener("click", () => {
    clearFailure();
    retry?.();
  });
  document
    .querySelectorAll<HTMLElement>(
      "[data-action], [data-discovery], [data-mapping], [data-github-install], [data-repository-open]",
    )
    .forEach((node) => node.removeAttribute("inert"));
}
if (document.readyState === "loading")
  document.addEventListener("DOMContentLoaded", initialize, { once: true });
else initialize();
