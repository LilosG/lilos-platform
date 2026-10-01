import { z } from "zod";
const status = () =>
  document.querySelector<HTMLElement>("[data-search-status]");
function message(text: string) {
  const node = status();
  if (node) node.textContent = text;
}
async function action(url: string, body: unknown, method = "POST") {
  const response = await fetch(url, {
    method,
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token":
        document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')
          ?.content ?? "",
    },
    ...(method === "GET" || method === "DELETE"
      ? {}
      : { body: JSON.stringify(body) }),
  });
  const data: unknown = await response.json();
  const envelope = z
    .object({
      data: z.unknown().optional(),
      error: z.object({ code: z.string() }).loose().optional(),
      code: z.string().optional(),
    })
    .loose()
    .parse(data);
  if (!response.ok || envelope.error || envelope.code)
    throw new Error(
      envelope.code ?? envelope.error?.code ?? `HTTP_${response.status}`,
    );
  return envelope.data;
}
function failure(error: unknown) {
  message(
    `Action unavailable (${error instanceof Error ? error.message : "UNKNOWN"}). Refresh to inspect current state before trying again.`,
  );
}
function initialize() {
  document
    .querySelectorAll<HTMLButtonElement>("button[data-action]")
    .forEach((button) =>
      button.addEventListener("click", async () => {
        if (button.dataset.confirm && !window.confirm(button.dataset.confirm))
          return;
        button.disabled = true;
        message(
          "Request in progress. Provider completion is not yet confirmed.",
        );
        try {
          const body = button.hasAttribute("data-key")
            ? { idempotency_key: crypto.randomUUID() }
            : JSON.parse(button.dataset.body ?? "{}");
          const data = await action(
            button.dataset.action!,
            body,
            button.dataset.method,
          );
          if (button.hasAttribute("data-oauth")) {
            const parsed = z.object({ authorization_url: z.url() }).parse(data);
            const url = new URL(parsed.authorization_url);
            if (
              url.origin !== "https://accounts.google.com" ||
              url.pathname !== "/o/oauth2/v2/auth"
            )
              throw new Error("OAUTH_TARGET_INVALID");
            window.location.assign(url.href);
          } else window.location.reload();
        } catch (error) {
          failure(error);
        }
      }),
    );
  document
    .querySelectorAll<HTMLFormElement>("[data-post-form]")
    .forEach((form) =>
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const button = form.querySelector<HTMLButtonElement>(
          'button[type="submit"]',
        )!;
        button.disabled = true;
        try {
          await action(form.dataset.action!, {
            post_type: "standard",
            content: new FormData(form).get("content"),
          });
          window.location.reload();
        } catch (error) {
          failure(error);
        }
      }),
    );
  document.querySelectorAll<HTMLFormElement>("[data-mapping]").forEach((form) =>
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const values = new FormData(form);
      const location = z.uuid().parse(values.get("location_id"));
      form.querySelector<HTMLButtonElement>('button[type="submit"]')!.disabled =
        true;
      try {
        await action(
          form.dataset.api +
            `locations/${location}/gbp-mapping/${form.dataset.profile}/confirm/`,
          { location_id: location, write_enabled: values.has("write_enabled") },
        );
        window.location.reload();
      } catch (error) {
        failure(error);
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
        const website = z.uuid().parse(new FormData(form).get("website_id"));
        const analytics = form.dataset.source === "analytics";
        const api = form.dataset.api!;
        const container = form.querySelector<HTMLElement>("[data-discovered]")!;
        container.replaceChildren();
        const submit = form.querySelector<HTMLButtonElement>(
          'button[type="submit"]',
        )!;
        submit.disabled = true;
        try {
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
          message(
            rows.length
              ? "Select an exact discovered property to confirm its mapping."
              : "No accessible properties discovered. No mapping has been created.",
          );
          for (const row of rows) {
            const button = document.createElement("button");
            button.type = "button";
            button.textContent = `Confirm ${row.external_property_id}`;
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
                failure(error);
              }
            });
            container.append(button);
          }
        } catch (error) {
          failure(error);
        } finally {
          submit.disabled = false;
        }
      }),
    );
  document
    .querySelectorAll<HTMLElement>(
      "[data-action], [data-discovery], [data-mapping]",
    )
    .forEach((node) => node.removeAttribute("inert"));
}
if (document.readyState === "loading")
  document.addEventListener("DOMContentLoaded", initialize, { once: true });
else initialize();
