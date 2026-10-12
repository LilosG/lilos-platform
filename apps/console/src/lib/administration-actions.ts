import { action, ApiFailure } from "./api-client";
import {
  activateConfirm,
  administrationFailureText,
  cancelInvitationConfirm,
  confirmCopy,
} from "./administration-view";
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
/** Activating a client that is ready, after asking first. */
function bindActivation() {
  const dialog = confirmDialog("admin-confirm");
  if (!dialog) return;
  document
    .querySelectorAll<HTMLButtonElement>("button[data-activate]")
    .forEach((button) => {
      button.removeAttribute("inert");
      button.addEventListener("click", () => {
        const { orgId, orgName, version } = button.dataset;
        openConfirm(dialog, activateConfirm(orgName!), {
          failure,
          work: async () => {
            await action(`/api/platform/organizations/${orgId}/activate/`, {
              expected_version: Number(version),
            });
          },
        });
      });
    });
}
/** Cancelling a pending invitation, after asking first. */
function bindInvitations() {
  const dialog = confirmDialog("admin-confirm");
  if (!dialog) return;
  document
    .querySelectorAll<HTMLButtonElement>("button[data-cancel-invitation]")
    .forEach((button) => {
      button.removeAttribute("inert");
      button.addEventListener("click", () => {
        const { orgId, invitationId, version, person, clientName } =
          button.dataset;
        openConfirm(dialog, cancelInvitationConfirm(person!, clientName!), {
          failure,
          work: async () => {
            await action(
              `/api/platform/organizations/${orgId}/invitations/${invitationId}/cancel/`,
              { expected_version: Number(version) },
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
  // The chip is being followed from here on; a test (or a person) can tell it is no longer static.
  chips.forEach((chip) => (chip.dataset.following = "true"));
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
bindActivation();
bindInvitations();
followRemovals();
