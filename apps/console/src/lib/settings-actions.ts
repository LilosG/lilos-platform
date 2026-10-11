import { z } from "zod";
import { action, ApiFailure } from "./api-client";
import { confirmDialog, openConfirm } from "./confirm-dialog";
import {
  FACT_FIELDS,
  factFailureText,
  factFormComplete,
  factProposal,
  locationConfirm,
  retirePlan,
  retireProgress,
  settingsFailureText,
  type FactField,
  type LocationAction,
  type LocationStep,
} from "./settings-view";
import type { LocationStatus } from "../adapters/administration";
const codeOf = (error: unknown) =>
  error instanceof ApiFailure ? error.code : "UNKNOWN";
/** A retirement that stopped part way: which step it reached, and the reason in plain words. */
class RetireFailure extends Error {
  constructor(
    public done: LocationStep[],
    public step: LocationStep,
    public cause_: unknown,
  ) {
    super("RETIRE_FAILED");
  }
}
const newVersion = z.object({ version: z.number().int().min(1) });
function bindLocations() {
  const dialog = confirmDialog("settings-confirm");
  const section = document.querySelector<HTMLElement>(
    '[data-settings="locations"]',
  );
  if (!dialog || !section) return;
  const api = section.dataset.api!;
  const call = async (id: string, step: LocationStep, version: number) =>
    newVersion.parse(
      await action(`${api}locations/${id}/${step}/`, {
        expected_version: version,
      }),
    ).version;
  section
    .querySelectorAll<HTMLButtonElement>("button[data-location-action]")
    .forEach((button) => {
      button.removeAttribute("inert");
      button.addEventListener("click", () => {
        const kind = button.dataset.locationAction as LocationAction;
        const id = button.dataset.locationId!;
        const name = button.dataset.name!;
        const status = button.dataset.status as LocationStatus;
        let version = Number(button.dataset.version);
        // A retry after a partial retirement starts from the step not yet done.
        const finished: LocationStep[] = [];
        openConfirm(dialog, locationConfirm(kind, name), {
          failure: (error) =>
            error instanceof RetireFailure
              ? `${retireProgress(error.done, error.step)} ${settingsFailureText(codeOf(error.cause_))}`
              : settingsFailureText(codeOf(error)),
          work: async () => {
            const steps: LocationStep[] =
              kind === "retire" ? retirePlan(status) : [kind];
            for (const step of steps) {
              if (finished.includes(step)) continue;
              try {
                // Each call carries the version the previous one returned.
                version = await call(id, step, version);
                finished.push(step);
              } catch (error) {
                if (kind === "retire")
                  throw new RetireFailure([...finished], step, error);
                throw error;
              }
            }
          },
        });
      });
    });
}
const fieldOf = (id: string): FactField =>
  FACT_FIELDS.find((field) => field.id === id) ?? FACT_FIELDS[0];
function bindFacts() {
  const dialog = document.querySelector<HTMLDialogElement>("#fact-dialog");
  const section = document.querySelector<HTMLElement>(
    '[data-settings="facts"]',
  );
  if (!dialog || !section) return;
  const api = section.dataset.api!;
  const form = dialog.querySelector<HTMLFormElement>("[data-fact-form]")!;
  const select = form.querySelector<HTMLSelectElement>("select[name=field]")!;
  const save = form.querySelector<HTMLButtonElement>("[data-fact-save]")!;
  const cancel = form.querySelector<HTMLButtonElement>("[data-fact-cancel]")!;
  const hint = form.querySelector<HTMLElement>("[data-fact-hint]")!;
  const errorBox = form.querySelector<HTMLElement>("[data-fact-error]")!;
  const status = form.querySelector<HTMLElement>("[data-fact-status]")!;
  const existing = () =>
    [
      ...section.querySelectorAll<HTMLButtonElement>(
        "tr[data-waiting=false] button[data-fact-identity]",
      ),
    ].find((button) => button.dataset.factField === select.value);
  const values = (): Record<string, string> =>
    Object.fromEntries(
      [...new FormData(form).entries()].map(([k, v]) => [k, String(v)]),
    );
  const show = () => {
    const field = fieldOf(select.value);
    hint.textContent = field.hint;
    form
      .querySelectorAll<HTMLElement>("[data-fact-input]")
      .forEach((node) => (node.hidden = node.dataset.factInput !== field.type));
    const label = form.querySelector<HTMLElement>("[data-fact-input-label]")!;
    label.textContent = field.label;
    save.disabled = !complete();
  };
  const complete = () => {
    const field = fieldOf(select.value);
    const data = values();
    return factFormComplete(field, {
      ...data,
      value: field.type === "string_list" ? (data.list ?? "") : data.value,
    });
  };
  /** Start the form on one fact, filled with what it says today when it says anything. */
  const prefill = (fieldId: string, raw: unknown) => {
    form.reset();
    select.value = fieldId;
    const set = (name: string, value: unknown) => {
      const input = form.elements.namedItem(name);
      if (
        input instanceof HTMLInputElement ||
        input instanceof HTMLTextAreaElement
      )
        input.value = typeof value === "string" ? value : "";
    };
    if (typeof raw === "string") set("value", raw);
    else if (Array.isArray(raw)) set("list", raw.join("\n"));
    else if (raw && typeof raw === "object")
      for (const [key, value] of Object.entries(raw)) set(key, value);
    show();
  };
  const rawOf = (button: HTMLElement | undefined): unknown =>
    button?.dataset.factRaw ? JSON.parse(button.dataset.factRaw) : undefined;
  const open = (fieldId: string, raw?: unknown) => {
    prefill(fieldId, raw);
    errorBox.hidden = true;
    status.textContent = "";
    dialog.showModal();
    select.focus();
  };
  section
    .querySelectorAll<HTMLButtonElement>("button[data-fact-open]")
    .forEach((button) => {
      button.removeAttribute("inert");
      button.addEventListener("click", () =>
        open(button.dataset.factField ?? FACT_FIELDS[0].id, rawOf(button)),
      );
    });
  // Switching to a fact that already has a value starts from what it says today.
  select.addEventListener("change", () =>
    prefill(select.value, rawOf(existing())),
  );
  form.addEventListener("input", () => (save.disabled = !complete()));
  cancel.addEventListener("click", () => dialog.close());
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!complete()) return;
    const field = fieldOf(select.value);
    const current = existing();
    const data = values();
    const body = factProposal(
      field,
      {
        ...data,
        value: field.type === "string_list" ? (data.list ?? "") : data.value,
      },
      current
        ? {
            identity: current.dataset.factIdentity!,
            locationId: current.dataset.factLocation || null,
          }
        : undefined,
      dialog.dataset.primaryLocation || null,
    );
    save.disabled = true;
    cancel.disabled = true;
    errorBox.hidden = true;
    status.textContent = "Saving…";
    try {
      const created = z
        .object({ id: z.uuid() })
        .parse(await action(`${api}business-facts/`, body));
      try {
        // Approved in the same step when this person is allowed to; otherwise it waits.
        await action(`${api}business-facts/${created.id}/decision/`, {
          decision: "approve",
        });
      } catch {
        // The proposal exists and shows as waiting for approval after the page reloads.
      }
      status.textContent = "Saved. Updating…";
      window.location.reload();
    } catch (error) {
      status.textContent = "";
      form.querySelector<HTMLElement>("[data-fact-error-text]")!.textContent =
        factFailureText(codeOf(error));
      errorBox.hidden = false;
      cancel.disabled = false;
      save.disabled = !complete();
    }
  });
}
bindLocations();
bindFacts();
