import { z } from "zod";
import { reviewFailure } from "./review-actions";
async function send(url: string, body: unknown, createdBase?: string) {
  const node = document.querySelector<HTMLElement>("[data-content-status]");
  if (node)
    node.textContent =
      "Request in progress. Deployment and live verification are not confirmed.";
  try {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token":
          document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')
            ?.content ?? "",
      },
      body: JSON.stringify(body),
    });
    const raw: unknown = await response.json();
    if (!response.ok) {
      if (node)
        node.textContent = `Action unavailable (${reviewFailure(raw, response.status)}). Refresh canonical state before trying again.`;
      return;
    }
    if (createdBase && raw && typeof raw === "object" && "data" in raw) {
      const data = raw.data as { id?: unknown };
      if (typeof data.id === "string" && /^[0-9a-f-]{36}$/i.test(data.id)) {
        window.location.assign(createdBase + data.id + "/");
        return;
      }
    }
    window.location.reload();
  } catch {
    if (node)
      node.textContent =
        "Outcome uncertain. Refresh canonical state before trying again.";
  }
}
function initialize() {
  document
    .querySelectorAll<HTMLButtonElement>("[data-content-action]")
    .forEach((button) => {
      button.removeAttribute("inert");
      button.addEventListener("click", () => {
        button.disabled = true;
        void send(
          button.dataset.contentAction!,
          JSON.parse(button.dataset.body ?? "{}"),
        );
      });
    });
  document
    .querySelectorAll<HTMLFormElement>("[data-content-form]")
    .forEach((form) => {
      form.removeAttribute("inert");
      form.addEventListener("submit", (event) => {
        event.preventDefault();
        const data = new FormData(form);
        let body: Record<string, unknown>;
        try {
          switch (form.dataset.contentForm) {
            case "create":
              body = {
                title: data.get("title"),
                slug: data.get("slug"),
                content_type: data.get("content_type"),
              };
              break;
            case "brief":
              body = {
                audience: data.get("audience"),
                intent: data.get("intent"),
                target_reference: data.get("target_reference"),
                approved_fact_revision_ids: data.getAll("fact"),
              };
              break;
            case "revision":
              body = {
                body: data.get("body"),
                frontmatter: JSON.parse(String(data.get("frontmatter"))),
                created_by_type: "user",
                approved_fact_revision_ids: data.getAll("fact"),
              };
              break;
            case "publish":
              body = {
                idempotency_key: form.dataset.key,
                publishing_target_id: data.get("target"),
                ...(data.get("image") ? { image: data.get("image") } : {}),
                ...(data.get("image_alt")
                  ? { image_alt: data.get("image_alt") }
                  : {}),
              };
              break;
            default:
              return;
          }
        } catch {
          const node = document.querySelector<HTMLElement>(
            "[data-content-status]",
          );
          if (node) node.textContent = "Enter valid JSON frontmatter.";
          return;
        }
        form
          .querySelectorAll<HTMLButtonElement>("button")
          .forEach((b) => (b.disabled = true));
        void send(
          form.dataset.action!,
          body,
          form.dataset.contentForm === "create"
            ? form.dataset.detailBase
            : undefined,
        );
      });
    });
  document
    .querySelectorAll<HTMLButtonElement>("[data-content-assets]")
    .forEach((button) => {
      button.removeAttribute("inert");
      button.addEventListener("click", async () => {
        const form = button.closest("form")!;
        const target =
          form.querySelector<HTMLSelectElement>('[name="target"]')!.value;
        const output = form.querySelector<HTMLElement>("[data-assets-result]")!;
        output.textContent = "Loading assets…";
        try {
          const response = await fetch(
            `${button.dataset.contentAssets}?target_id=${encodeURIComponent(target)}`,
          );
          const raw: unknown = await response.json();
          if (!response.ok) throw new Error();
          const assets = z
            .object({
              data: z
                .array(
                  z.object({
                    path: z.string().max(1000),
                    name: z.string().max(500),
                  }),
                )
                .max(250),
            })
            .parse(raw).data;
          output.textContent =
            assets.map((a) => a.path).join(" · ") ||
            "No image assets returned.";
        } catch {
          output.textContent =
            "Assets unavailable. No sample assets substituted.";
        }
      });
    });
}
if (typeof document !== "undefined") {
  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", initialize, { once: true });
  else initialize();
}
