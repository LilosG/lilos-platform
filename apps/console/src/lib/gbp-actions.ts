import { z } from "zod";
import { action, failureText } from "./api-client";
const root = document.querySelector<HTMLElement>("[data-gbp]");
const org = root?.dataset.org ?? "";
const location = root?.dataset.location ?? "";
const profile = root?.dataset.profile ?? "";
const ops = `/api/organizations/${org}/locations/${location}/gbp/operations/`;
const status = () => root?.querySelector<HTMLElement>("[data-gbp-status]");
const show = (text: string) => {
  const node = status();
  if (node) node.textContent = text;
};
const key = () => crypto.randomUUID();
const decision = (approve: boolean) => ({ approve });
type Call = (id: string, publication: string) => Promise<unknown>;
const calls: Record<string, Call> = {
  "post-approve": (id) => action(`${ops}posts/${id}/decision/`, decision(true)),
  "post-reject": (id) => action(`${ops}posts/${id}/decision/`, decision(false)),
  "post-publish": (id) =>
    action(`${ops}posts/${id}/dispatch/`, { idempotency_key: key() }),
  "post-recover": (_id, publication) =>
    action(`${ops}posts/publications/${publication}/recover/`, {}),
  "post-repost": (_id, publication) =>
    action(`${ops}posts/publications/${publication}/repost/`, {}),
  "post-discard": (_id, publication) =>
    action(`${ops}posts/publications/${publication}/discard/`, {}),
  reconcile: () => action(`${ops}locations/${profile}/posts/reconcile/`, {}),
  "photo-approve": (id) => action(`${ops}media/${id}/decide/`, decision(true)),
  "photo-reject": (id) => action(`${ops}media/${id}/decide/`, decision(false)),
  // A photo is published by a workflow run, so one is reserved for this photo first.
  "photo-publish": async (id) => {
    const run = z.object({ workflow_run_id: z.uuid() }).parse(
      await action(
        `/api/organizations/${org}/workflows/gbp.upload_media/runs/`,
        {
          location_id: location,
          idempotency_key: key(),
          input_document: {},
          execute: false,
        },
      ),
    );
    return action(`${ops}media/${id}/publish/`, {
      workflow_run_id: run.workflow_run_id,
      idempotency_key: key(),
    });
  },
  "hours-approve": (id) =>
    action(`${ops}special-hours/${id}/decision/`, decision(true)),
  "hours-reject": (id) =>
    action(`${ops}special-hours/${id}/decision/`, decision(false)),
  "change-approve": (id) =>
    action(`${ops}change-sets/${id}/decision/`, decision(true)),
  "change-reject": (id) =>
    action(`${ops}change-sets/${id}/decision/`, decision(false)),
};
root
  ?.querySelectorAll<HTMLButtonElement>("button[data-gbp-action]")
  .forEach((button) =>
    button.addEventListener("click", async () => {
      const call = calls[button.dataset.gbpAction ?? ""];
      if (!call) return;
      button.disabled = true;
      show("Working…");
      try {
        await call(button.dataset.id ?? "", button.dataset.publication ?? "");
        window.location.reload();
      } catch (error) {
        show(failureText(error));
        button.disabled = false;
      }
    }),
  );
const dialogOf = (name: string) =>
  root?.querySelector<HTMLDialogElement>(`dialog[data-gbp-dialog="${name}"]`) ??
  document.querySelector<HTMLDialogElement>(
    `dialog[data-gbp-dialog="${name}"]`,
  );
/** Wires one form: validate, send, and reload on success; a failure stays in the dialog. */
function form(
  name: string,
  send: (data: FormData, form: HTMLFormElement) => Promise<unknown> | string,
) {
  const dialog = dialogOf(name);
  const element = dialog?.querySelector<HTMLFormElement>("form");
  if (!dialog || !element) return;
  const message = element.querySelector<HTMLElement>("[data-form-status]");
  element.addEventListener("submit", async (event) => {
    event.preventDefault();
    const submit = element.querySelector<HTMLButtonElement>(
      'button[type="submit"]',
    )!;
    if (message) message.textContent = "";
    submit.disabled = true;
    try {
      const outcome = send(new FormData(element), element);
      if (typeof outcome === "string") {
        if (message) message.textContent = outcome;
        submit.disabled = false;
        return;
      }
      await outcome;
      window.location.reload();
    } catch (error) {
      if (message) message.textContent = failureText(error);
      submit.disabled = false;
    }
  });
}
// Posts: one dialog writes a new post or a new version of an existing one.
const postDialog = dialogOf("post");
const content = postDialog?.querySelector<HTMLTextAreaElement>(
  "[data-post-content]",
);
const count = postDialog?.querySelector<HTMLElement>("[data-post-count]");
let postKey = "";
const updateCount = () => {
  if (count && content) count.textContent = String(content.value.length);
};
content?.addEventListener("input", updateCount);
root?.querySelectorAll<HTMLElement>("[data-post-open]").forEach((button) =>
  button.addEventListener("click", () => {
    const edit = button.dataset.postOpen === "edit";
    postKey = edit ? (button.dataset.postKey ?? "") : "";
    if (content) content.value = edit ? (button.dataset.postContent ?? "") : "";
    const eyebrow = postDialog?.querySelector("[data-post-eyebrow]");
    if (eyebrow) eyebrow.textContent = edit ? "Edit post" : "New post";
    updateCount();
    postDialog?.showModal();
    content?.focus();
  }),
);
form("post", (data) => {
  const text = String(data.get("content") ?? "").trim();
  if (!text) return "Write the post before saving it.";
  return action(`${ops}locations/${profile}/posts/`, {
    post_type: "standard",
    content: text,
    ...(postKey ? { post_key: postKey } : {}),
  });
});
// Profile: each field maps to the one exact change that will be approved.
const profileDialog = dialogOf("profile");
const field = profileDialog?.querySelector<HTMLSelectElement>(
  "[data-profile-field]",
);
const showPane = () =>
  profileDialog
    ?.querySelectorAll<HTMLElement>("[data-profile-pane]")
    .forEach(
      (pane) => (pane.hidden = pane.dataset.profilePane !== field?.value),
    );
field?.addEventListener("change", showPane);
root?.querySelector("[data-profile-open]")?.addEventListener("click", () => {
  showPane();
  profileDialog?.showModal();
});
const edits = {
  description: { capability_key: "profile", field: "description" },
  phone: { capability_key: "phoneNumbers", field: "phoneNumbers" },
  website: { capability_key: "websiteUri", field: "websiteUri" },
} as const;
form("profile", (data) => {
  const chosen = z
    .enum(["description", "phone", "website"])
    .parse(data.get("field"));
  const value = String(data.get(chosen) ?? "").trim();
  if (!value) return "Enter the new value first.";
  const edit = edits[chosen];
  return action(`${ops}locations/${profile}/change-sets/`, {
    capability_key: edit.capability_key,
    field_changes: [{ field: edit.field, value }],
    evidence: {},
    risk: "low",
    idempotency_key: key(),
  });
});
form("photo", (data) => {
  const address = String(data.get("source_reference") ?? "").trim();
  if (!address.startsWith("https://"))
    return "Use a secure photo address that starts with https://.";
  return action(`${ops}locations/${profile}/media/`, {
    media_type: z
      .enum(["photo", "cover", "logo"])
      .parse(data.get("media_type")),
    source_reference: address,
    rights_authority: String(data.get("rights_authority") ?? ""),
    idempotency_key: key(),
  });
});
form("hours", (data) => {
  const date = String(data.get("service_date") ?? "");
  const opens = String(data.get("opens") ?? "");
  const closes = String(data.get("closes") ?? "");
  if (!date) return "Choose the date first.";
  if (!opens || !closes || opens >= closes)
    return "Closing time must be after opening time.";
  return action(`${ops}locations/${profile}/special-hours/`, {
    service_date: date,
    periods: [{ opens, closes }],
    source: "console",
  });
});
root?.setAttribute("data-ready", "true");
