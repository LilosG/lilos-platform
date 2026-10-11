/**
 * One confirmation dialog for every lifecycle change: it says exactly what will happen, asks
 * for a typed name when the change destroys data, runs the call, and keeps the person in the
 * dialog with a designed message when the call fails.
 */
export interface DialogCopy {
  title: string;
  lines: string[];
  accept: string;
  tone: "normal" | "danger";
  /** The exact text that must be typed before the change is allowed. */
  typedName?: string | null;
}
export interface RunOptions {
  /** The change itself; it throws when it fails. */
  work: (typed: string) => Promise<void>;
  /** A sentence for a failure; never the system's words. */
  failure: (error: unknown) => string;
  /** What to do when the change succeeded; the page reloads by default. */
  done?: () => void;
}
const part = <T extends HTMLElement>(dialog: HTMLElement, name: string) =>
  dialog.querySelector<T>(`[data-confirm-${name}]`)!;
export function openConfirm(
  dialog: HTMLDialogElement,
  copy: DialogCopy,
  options: RunOptions,
) {
  part(dialog, "title").textContent = copy.title;
  const lines = part(dialog, "lines");
  lines.replaceChildren(
    ...copy.lines.map((line) => {
      const p = document.createElement("p");
      p.textContent = line;
      return p;
    }),
  );
  const accept = part<HTMLButtonElement>(dialog, "accept");
  const cancel = part<HTMLButtonElement>(dialog, "cancel");
  const typed = part<HTMLElement>(dialog, "typed");
  const input = part<HTMLInputElement>(dialog, "typed-input");
  const error = part<HTMLElement>(dialog, "error");
  const status = part<HTMLElement>(dialog, "status");
  accept.textContent = copy.accept;
  accept.classList.toggle("danger", copy.tone === "danger");
  error.hidden = true;
  status.textContent = "";
  input.value = "";
  typed.hidden = !copy.typedName;
  part(dialog, "typed-label").textContent = copy.typedName
    ? `Type ${copy.typedName} to confirm`
    : "";
  const ready = () => !copy.typedName || input.value.trim() === copy.typedName;
  const sync = () => {
    accept.disabled = !ready();
  };
  input.oninput = sync;
  sync();
  cancel.onclick = () => dialog.close();
  accept.onclick = async () => {
    if (!ready()) return;
    accept.disabled = true;
    cancel.disabled = true;
    error.hidden = true;
    status.textContent = "Working on it…";
    try {
      await options.work(input.value.trim());
      status.textContent = "Done. Updating…";
      (options.done ?? (() => window.location.reload()))();
    } catch (failed) {
      status.textContent = "";
      part(dialog, "error-text").textContent = options.failure(failed);
      error.hidden = false;
      cancel.disabled = false;
      sync();
    }
  };
  dialog.showModal();
  (copy.typedName ? input : cancel).focus();
}
export const confirmDialog = (id: string) =>
  document.getElementById(id) as HTMLDialogElement | null;
