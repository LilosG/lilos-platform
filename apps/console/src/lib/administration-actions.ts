import { action, ApiFailure } from "./api-client";
import { confirmCopy, administrationFailureText } from "./administration-view";
import type { OrganizationAction } from "./administration-view";
import { confirmDialog, openConfirm } from "./confirm-dialog";
import { removalChips } from "./status";
import { REMOVAL_STATES, type RemovalState } from "../adapters/administration";
const paths: Record<OrganizationAction, string> = {
  start_offboarding: "start-offboarding",
  archive: "archive",
  remove: "remove",
};
const failure = (error: unknown) =>
  administrationFailureText(
    error instanceof ApiFailure ? error.code : "UNKNOWN",
  );
function bindActions() {
  const dialog = confirmDialog("admin-confirm");
  if (!dialog) return;
  document
    .querySelectorAll<HTMLButtonElement>("button[data-org-action]")
    .forEach((button) => {
      button.removeAttribute("inert");
      button.addEventListener("click", () => {
        const kind = button.dataset.orgAction as OrganizationAction;
        const id = button.dataset.orgId!;
        const name = button.dataset.orgName!;
        const version = Number(button.dataset.version);
        openConfirm(dialog, confirmCopy(kind, name), {
          failure,
          work: async (typed) => {
            await action(
              `/api/platform/organizations/${id}/${paths[kind]}/`,
              kind === "remove"
                ? { confirm_name: typed }
                : { expected_version: version },
            );
          },
        });
      });
    });
}
/** A removal runs in the background; its chip follows it until it finishes. */
function followRemovals() {
  const chips = document.querySelectorAll<HTMLElement>("[data-removal-poll]");
  if (!chips.length) return;
  const settled = (state: RemovalState | null) =>
    state === "completed" || state === "failed";
  const timer = window.setInterval(async () => {
    let finished = false;
    for (const chip of chips) {
      try {
        const data = (await action(
          `/api/platform/organizations/${chip.dataset.removalPoll}/removal/`,
          null,
          "GET",
        )) as { state: string | null };
        const state = REMOVAL_STATES.find((s) => s === data.state) ?? null;
        if (!state) continue;
        const label = removalChips[state].label;
        if (chip.textContent !== label) chip.textContent = label;
        finished ||= settled(state);
      } catch {
        // The next check tries again; a missed check changes nothing on screen.
      }
    }
    if (finished) {
      window.clearInterval(timer);
      window.location.reload();
    }
  }, 5000);
}
bindActions();
followRemovals();
