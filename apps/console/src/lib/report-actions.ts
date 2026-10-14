import { z } from "zod";
import { ApiFailure, call } from "./api-client";
import { confirmDialog, openConfirm } from "./confirm-dialog";
import {
  approveCopy,
  draftFailureText,
  reportFailureText,
  sendCopy,
} from "./report-view";
import { FAILURE_CODES } from "../adapters/reports";
const codeOf = (error: unknown) =>
  error instanceof ApiFailure ? error.code : "UNKNOWN";
const failure = z.enum(FAILURE_CODES);
const drafted = z.object({
  outcome: z.enum(["drafted", "not_used"]),
  failure: failure.nullable().optional(),
});
function say(text: string, error = false) {
  const status = document.querySelector<HTMLElement>("[data-report-status]");
  if (!status) return;
  status.textContent = text;
  status.classList.toggle("error", error);
}
function bindGenerate() {
  document
    .querySelectorAll<HTMLButtonElement>("[data-generate-report]")
    .forEach((button) => {
      button.removeAttribute("inert");
      button.addEventListener("click", async () => {
        button.disabled = true;
        say("Generating the report…");
        try {
          await call(button.dataset.api!, { month: button.dataset.month });
          window.location.assign(button.dataset.href!);
        } catch (error) {
          say(reportFailureText(codeOf(error)), true);
          button.disabled = false;
        }
      });
    });
}
function bindPage() {
  const page = document.querySelector<HTMLElement>("[data-report-page]");
  if (!page) return;
  const api = page.dataset.api!;
  const one = `${api}${page.dataset.slug}/${page.dataset.revision}/`;
  const client = page.dataset.client!;
  const month = page.dataset.month!;
  const field = (name: string) =>
    page.querySelector<HTMLTextAreaElement>(`textarea[name="${name}"]`);
  const body = () => ({
    what_changed: field("what_changed")?.value ?? "",
    next_work: field("next_work")?.value ?? "",
  });
  const buttons = (selector: string) =>
    page.querySelectorAll<HTMLButtonElement>(selector);
  buttons("[inert]").forEach((button) => button.removeAttribute("inert"));
  buttons("[data-report-print]").forEach((button) =>
    button.addEventListener("click", () => window.print()),
  );
  buttons("[data-report-save]").forEach((button) =>
    button.addEventListener("click", async () => {
      button.disabled = true;
      say("Saving…");
      try {
        await call(`${one}narrative/`, body(), "PUT");
        say("Narrative saved.");
      } catch (error) {
        say(reportFailureText(codeOf(error)), true);
      }
      button.disabled = false;
    }),
  );
  buttons("[data-report-draft]").forEach((button) =>
    button.addEventListener("click", async () => {
      button.disabled = true;
      say("Drafting with Hermes…");
      try {
        const result = drafted.parse(await call(`${one}draft-narrative/`, {}));
        if (result.outcome === "drafted") window.location.reload();
        else {
          say(
            result.failure
              ? draftFailureText[result.failure]
              : draftFailureText.draft_failed,
            true,
          );
          button.disabled = false;
        }
      } catch (error) {
        say(reportFailureText(codeOf(error)), true);
        button.disabled = false;
      }
    }),
  );
  buttons("[data-report-regenerate]").forEach((button) =>
    button.addEventListener("click", async () => {
      button.disabled = true;
      say("Recomputing from the latest data…");
      try {
        await call(`${api}generate/`, { month });
        window.location.assign(
          `/clients/${page.dataset.clientSlug}/reports/${page.dataset.slug}/`,
        );
      } catch (error) {
        say(reportFailureText(codeOf(error)), true);
        button.disabled = false;
      }
    }),
  );
  const dialog = confirmDialog("report-confirm");
  if (!dialog) return;
  buttons("[data-report-approve]").forEach((button) =>
    button.addEventListener("click", () =>
      openConfirm(
        dialog,
        { ...approveCopy(client, month), tone: "normal" },
        {
          work: async () => {
            // A narrative typed but not yet saved is approved as shown on screen.
            await call(`${one}narrative/`, body(), "PUT").catch(
              () => undefined,
            );
            await call(`${one}approve/`, {});
          },
          failure: (error) => reportFailureText(codeOf(error)),
        },
      ),
    ),
  );
  buttons("[data-report-send]").forEach((button) =>
    button.addEventListener("click", () => {
      const sentOn =
        page.querySelector<HTMLInputElement>("input[name=sent_on]")?.value ??
        "";
      if (!sentOn) {
        say("Choose the day you sent it first.", true);
        return;
      }
      openConfirm(
        dialog,
        { ...sendCopy(client, month, sentOn), tone: "normal" },
        {
          work: async () => {
            await call(`${one}mark-sent/`, { sent_on: sentOn });
          },
          failure: (error) => reportFailureText(codeOf(error)),
        },
      );
    }),
  );
}
bindGenerate();
bindPage();
if (new URLSearchParams(window.location.search).has("print"))
  window.addEventListener("load", () => window.print());
