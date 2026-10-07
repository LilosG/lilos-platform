import { ApiFailure, action } from "./api-client";
import { failureFor } from "./content-view";

const status = () =>
  document.querySelector<HTMLElement>("[data-content-status]");
const say = (text: string) => {
  const node = status();
  if (node) node.textContent = text;
};
/** What a person is told when a call fails; the server's code never reaches them. */
const failureText: Record<string, string> = {
  HTTP_403: "You do not have access to do that.",
  AUTH_AAL2_REQUIRED: "Confirm your sign-in with your authenticator first.",
  AAL2_REQUIRED: "Confirm your sign-in with your authenticator first.",
  CONTENT_CLAIMS_NEED_CONFIRMATION:
    "Some claims still need to be confirmed or removed.",
  CONTENT_COMPOSE_WEBSITE_NOT_FOUND: "That website is no longer available.",
  HTTP_404: "That item is no longer available. Refresh the page.",
};
export const failureMessage = (error: unknown): string =>
  (error instanceof ApiFailure && failureText[error.code]) ||
  "That did not go through. Nothing was changed. Try again.";

const id = () => crypto.randomUUID();
const lockAll = (root: ParentNode, locked: boolean) =>
  root
    .querySelectorAll<HTMLButtonElement>("button")
    .forEach((button) => (button.disabled = locked));

// --- the composer -------------------------------------------------------------------------

function initComposer() {
  const dialog = document.querySelector<HTMLDialogElement>("#content-composer");
  const form = dialog?.querySelector<HTMLFormElement>("[data-compose-form]");
  if (!dialog || !form) return;
  form.removeAttribute("inert");
  const prompt = form.querySelector<HTMLTextAreaElement>(
    "[data-compose-prompt]",
  )!;
  const submit = dialog.querySelector<HTMLButtonElement>(
    "[data-compose-submit]",
  )!;
  const note = form.querySelector<HTMLElement>("[data-compose-status]")!;
  const sync = () => {
    submit.disabled = prompt.value.trim().length === 0;
    form
      .querySelectorAll<HTMLLabelElement>(".typechip")
      .forEach((chip) =>
        chip.classList.toggle(
          "active",
          chip.querySelector<HTMLInputElement>("input")!.checked,
        ),
      );
  };
  // A retry arrives as a link carrying the prompt; open the composer with it filled in.
  const url = new URL(location.href);
  const retry = url.searchParams.get("retry");
  if (retry) {
    url.searchParams.delete("retry");
    history.replaceState(null, "", url);
    window.setTimeout(() => openComposer(retry, null), 0);
  }
  form.addEventListener("input", sync);
  form.addEventListener("change", sync);
  sync();
  // One key per attempt: a double click never writes the piece twice.
  let key = id();
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = new FormData(form);
    const type = String(data.get("content_type") ?? "");
    submit.disabled = true;
    note.textContent = "Starting…";
    try {
      await action(dialog.dataset.composeAction!, {
        website_id: data.get("website_id"),
        prompt: prompt.value.trim(),
        content_type: type || null,
        idempotency_key: key,
      });
      window.location.reload();
    } catch (error) {
      key = id();
      note.textContent = failureMessage(error);
      sync();
    }
  });
}
function openComposer(promptText: string | null, type: string | null) {
  const dialog = document.querySelector<HTMLDialogElement>("#content-composer");
  if (!dialog) return;
  const prompt = dialog.querySelector<HTMLTextAreaElement>(
    "[data-compose-prompt]",
  );
  if (prompt && promptText) prompt.value = promptText;
  if (type) {
    const radio = dialog.querySelector<HTMLInputElement>(
      `input[name="content_type"][value="${CSS.escape(type)}"]`,
    );
    if (radio) radio.checked = true;
  }
  dialog.querySelector("form")?.dispatchEvent(new Event("input"));
  if (!dialog.open) dialog.showModal();
}

// --- draft review --------------------------------------------------------------------------

function initReview() {
  document
    .querySelectorAll<HTMLButtonElement>("[data-toggle]")
    .forEach((button) => {
      button.removeAttribute("inert");
      button.addEventListener("click", () => {
        const form = document.querySelector<HTMLFormElement>(
          button.dataset.toggle === "content-edit"
            ? "[data-edit-form]"
            : "[data-regenerate-form]",
        );
        if (!form) return;
        form.hidden = !form.hidden;
        if (!form.hidden) form.removeAttribute("inert");
      });
    });
  document
    .querySelectorAll<HTMLButtonElement>("[data-open-dialog]")
    .forEach((button) => {
      button.removeAttribute("inert");
      button.addEventListener("click", () =>
        document
          .querySelector<HTMLDialogElement>(`#${button.dataset.openDialog}`)
          ?.showModal(),
      );
    });
  // The approval dialog sits inside the detail dialog; closing it must not close the screen.
  document
    .querySelectorAll<HTMLDialogElement>("#content-approval")
    .forEach((dialog) =>
      dialog.querySelectorAll<HTMLElement>("[data-close]").forEach((button) =>
        button.addEventListener(
          "click",
          (event) => {
            event.stopPropagation();
            dialog.close();
          },
          true,
        ),
      ),
    );
  const regenerate = document.querySelector<HTMLFormElement>(
    "[data-regenerate-form]",
  );
  regenerate?.addEventListener("submit", async (event) => {
    event.preventDefault();
    lockAll(regenerate, true);
    say("Regenerating…");
    const instructions = new FormData(regenerate).get("instructions");
    try {
      await action(regenerate.dataset.action!, {
        brief_id: regenerate.dataset.brief,
        idempotency_key: id(),
        instructions: String(instructions ?? "").trim() || null,
      });
      const url = new URL(location.href);
      url.searchParams.set(
        REGENERATE_PARAM,
        String(document.querySelectorAll("[data-revision]").length),
      );
      history.replaceState(null, "", url);
      say(
        "Claude is writing a new revision. This page updates when it is ready.",
      );
      pollUntilChanged();
    } catch (error) {
      say(failureMessage(error));
      lockAll(regenerate, false);
    }
  });
  const edit = document.querySelector<HTMLFormElement>("[data-edit-form]");
  edit?.addEventListener("submit", async (event) => {
    event.preventDefault();
    lockAll(edit, true);
    say("Saving…");
    const data = new FormData(edit);
    const frontmatter = JSON.parse(edit.dataset.frontmatter ?? "{}") as Record<
      string,
      unknown
    >;
    frontmatter.seo_title = String(data.get("seo_title") ?? "");
    frontmatter.description = String(data.get("description") ?? "");
    try {
      await action(edit.dataset.action!, {
        body: String(data.get("body") ?? ""),
        frontmatter,
        created_by_type: "user",
        approved_fact_revision_ids: JSON.parse(edit.dataset.facts ?? "[]"),
      });
      window.location.reload();
    } catch (error) {
      say(failureMessage(error));
      lockAll(edit, false);
    }
  });
  document
    .querySelectorAll<HTMLButtonElement>("[data-approve]")
    .forEach((button) => {
      button.removeAttribute("inert");
      button.addEventListener("click", async () => {
        button.disabled = true;
        const note = document.querySelector<HTMLElement>(
          "[data-approve-status]",
        );
        if (note) note.textContent = "Approving…";
        try {
          await action(button.dataset.approve!, {
            stage: button.dataset.approveStage,
            approve: true,
          });
          window.location.reload();
        } catch (error) {
          if (note) note.textContent = failureMessage(error);
          button.disabled = false;
        }
      });
    });
}

// --- buttons that post one fixed body -----------------------------------------------------

function initActions() {
  document
    .querySelectorAll<HTMLButtonElement>("[data-content-action]")
    .forEach((button) => {
      button.removeAttribute("inert");
      button.addEventListener("click", async () => {
        const label = button.textContent;
        button.disabled = true;
        say("Working…");
        try {
          await action(
            button.dataset.contentAction!,
            JSON.parse(button.dataset.body ?? "{}"),
          );
          window.location.reload();
        } catch (error) {
          say(failureMessage(error));
          button.disabled = false;
          button.textContent = label;
        }
      });
    });
  document
    .querySelectorAll<HTMLFormElement>("[data-content-form='publish']")
    .forEach((form) => {
      form.removeAttribute("inert");
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const data = new FormData(form);
        lockAll(form, true);
        say("Sending to the website…");
        try {
          await action(form.dataset.action!, {
            idempotency_key: form.dataset.key,
            publishing_target_id: data.get("target"),
            ...(data.get("image") ? { image: data.get("image") } : {}),
            ...(data.get("image_alt")
              ? { image_alt: data.get("image_alt") }
              : {}),
          });
          window.location.reload();
        } catch (error) {
          say(failureMessage(error));
          lockAll(form, false);
        }
      });
    });
  document
    .querySelectorAll<HTMLButtonElement>("[data-compose-retry]")
    .forEach((button) => {
      button.removeAttribute("inert");
      button.addEventListener("click", () =>
        openComposer(button.dataset.composeRetry ?? null, null),
      );
    });
  document
    .querySelectorAll<HTMLButtonElement>("[data-compose-type]")
    .forEach((button) =>
      button.addEventListener("click", () =>
        window.setTimeout(
          () => openComposer(null, button.dataset.composeType ?? null),
          0,
        ),
      ),
    );
}

// --- keep a "Writing" item fresh ----------------------------------------------------------

const POLL_MS = 5000;
let polling = false;
function pollUntilChanged() {
  if (polling) return;
  polling = true;
  window.setTimeout(() => window.location.reload(), POLL_MS);
}
const REGENERATE_PARAM = "regenerating";
/** After a regenerate, wait for the new revision, or stop with the typed reason it failed. */
function initRegeneratePolling(): boolean {
  const url = new URL(location.href);
  const expected = url.searchParams.get(REGENERATE_PARAM);
  if (expected === null) return false;
  const count = document.querySelectorAll("[data-revision]").length;
  const run = document.querySelector<HTMLElement>("[data-draft-run-state]");
  const clear = () => {
    url.searchParams.delete(REGENERATE_PARAM);
    history.replaceState(null, "", url);
  };
  if (count > Number(expected)) {
    clear();
    return false;
  }
  if (run?.dataset.draftRunState === "failed") {
    clear();
    const reason = failureFor(run.dataset.draftRunFailure);
    say(`${reason.title}. ${reason.detail}`);
    return false;
  }
  say("Claude is writing a new revision. This page updates when it is ready.");
  pollUntilChanged();
  return true;
}
function initPolling() {
  if (initRegeneratePolling()) return;
  const writing = document.querySelector(
    "[data-has-writing], [data-content-row][data-writing]",
  );
  if (writing && !document.querySelector("dialog[open]#content-composer"))
    pollUntilChanged();
}

function initialize() {
  initComposer();
  initReview();
  initActions();
  initPolling();
}
// Re-exported for tests: the typed reason a failed item shows.
export { failureFor };
if (typeof document !== "undefined") {
  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", initialize, { once: true });
  else initialize();
}
