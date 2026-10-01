export function createDialogs(root: HTMLElement) {
  const triggers = new WeakMap<HTMLDialogElement, HTMLElement>();
  const current = () => root.querySelector<HTMLDialogElement>("dialog[open]");
  function close() {
    current()?.close();
  }
  function open(id: string, trigger?: HTMLElement) {
    const dialog = root.querySelector<HTMLDialogElement>(`#${CSS.escape(id)}`);
    if (!dialog) throw new Error(`Unknown dialog: ${id}`);
    const previous = current();
    const origin = previous
      ? triggers.get(previous)
      : (trigger ??
        (document.activeElement instanceof HTMLElement
          ? document.activeElement
          : undefined));
    if (origin) triggers.set(dialog, origin);
    previous?.close();
    dialog.showModal();
  }
  root.querySelectorAll<HTMLDialogElement>("dialog").forEach((dialog) => {
    dialog.addEventListener("close", () => {
      if (!current()) triggers.get(dialog)?.focus();
    });
    dialog.addEventListener("click", (event) => {
      if (event.target !== dialog) return;
      const r = dialog.getBoundingClientRect();
      if (
        event.clientX < r.left ||
        event.clientX > r.right ||
        event.clientY < r.top ||
        event.clientY > r.bottom
      )
        dialog.close();
    });
  });
  return { open, close, current };
}
