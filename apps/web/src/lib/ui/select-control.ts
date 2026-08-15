export type ControlledSelectOption = {
  value: string;
  label: string;
  disabled?: boolean;
};

export type RuntimeSelectControl = {
  root: HTMLDivElement;
  input: HTMLInputElement;
};

export function createSelectControl(
  id: string,
  label: string,
  options: ControlledSelectOption[],
  value = "",
  placeholder = "Select an option",
): RuntimeSelectControl {
  const root = document.createElement("div");
  root.className = "ui-field ui-select";
  root.dataset.selectRoot = "";

  const labelElement = document.createElement("label");
  labelElement.className = "ui-field__label";
  labelElement.id = `${id}-label`;
  labelElement.textContent = label;

  const input = document.createElement("input");
  input.type = "hidden";
  input.id = id;
  input.value = value;
  input.dataset.selectInput = "";

  const trigger = document.createElement("button");
  trigger.type = "button";
  trigger.className = "ui-select__trigger";
  trigger.id = `${id}-trigger`;
  trigger.setAttribute("role", "combobox");
  trigger.setAttribute("aria-controls", `${id}-listbox`);
  trigger.setAttribute("aria-expanded", "false");
  trigger.setAttribute("aria-haspopup", "listbox");
  trigger.setAttribute("aria-labelledby", `${id}-label ${id}-value`);

  const valueElement = document.createElement("span");
  valueElement.id = `${id}-value`;
  valueElement.dataset.selectValue = "";
  trigger.append(valueElement);

  const listbox = document.createElement("ul");
  listbox.className = "ui-select__listbox";
  listbox.id = `${id}-listbox`;
  listbox.setAttribute("role", "listbox");
  listbox.setAttribute("aria-labelledby", `${id}-label`);
  listbox.hidden = true;

  const selected = options.find((option) => option.value === value);
  valueElement.textContent = selected?.label ?? placeholder;
  if (!selected) valueElement.dataset.placeholder = "true";

  const close = (restoreFocus = false): void => {
    listbox.hidden = true;
    trigger.setAttribute("aria-expanded", "false");
    delete root.dataset.active;
    if (restoreFocus) trigger.focus();
  };
  const choose = (option: HTMLLIElement): void => {
    if (option.getAttribute("aria-disabled") === "true") return;
    for (const candidate of listbox.querySelectorAll<HTMLElement>("[role='option']")) {
      candidate.setAttribute("aria-selected", String(candidate === option));
    }
    input.value = option.dataset.value ?? "";
    valueElement.textContent = option.dataset.label ?? placeholder;
    if (input.value) delete valueElement.dataset.placeholder;
    else valueElement.dataset.placeholder = "true";
    input.dispatchEvent(new Event("change", { bubbles: true }));
    close(true);
  };

  for (const [index, option] of options.entries()) {
    const item = document.createElement("li");
    item.id = `${id}-option-${index}`;
    item.className = "ui-select__option";
    item.tabIndex = -1;
    item.setAttribute("role", "option");
    item.setAttribute("aria-selected", String(option.value === value));
    if (option.disabled) item.setAttribute("aria-disabled", "true");
    item.dataset.value = option.value;
    item.dataset.label = option.label;
    item.textContent = option.label;
    item.addEventListener("click", () => choose(item));
    listbox.append(item);
  }

  const focusOption = (offset: number): void => {
    const enabled = Array.from(
      listbox.querySelectorAll<HTMLLIElement>("[role='option']:not([aria-disabled='true'])"),
    );
    if (enabled.length === 0) return;
    const current = enabled.findIndex((option) => option === document.activeElement);
    enabled[(Math.max(current, 0) + offset + enabled.length) % enabled.length]?.focus();
  };
  trigger.addEventListener("click", () => {
    const opening = listbox.hidden;
    listbox.hidden = !opening;
    trigger.setAttribute("aria-expanded", String(opening));
    if (opening) {
      root.dataset.active = "true";
      listbox.querySelector<HTMLLIElement>("[aria-selected='true']")?.focus();
    } else delete root.dataset.active;
  });
  root.addEventListener("keydown", (event) => {
    if (event.key === "Escape") return close(true);
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (listbox.hidden) trigger.click();
      focusOption(event.key === "ArrowDown" ? 1 : -1);
    }
    if ((event.key === "Enter" || event.key === " ") && document.activeElement?.getAttribute("role") === "option") {
      event.preventDefault();
      choose(document.activeElement as HTMLLIElement);
    }
  });
  document.addEventListener("pointerdown", (event) => {
    if (!root.contains(event.target as Node)) close();
  });

  root.append(labelElement, input, trigger, listbox);
  return { root, input };
}

function selectRoot(id: string): HTMLElement | null {
  return document.getElementById(id)?.closest<HTMLElement>("[data-select-root]") ?? null;
}

export function setSelectOptions(
  id: string,
  options: ControlledSelectOption[],
  value?: string,
): void {
  selectRoot(id)?.dispatchEvent(
    new CustomEvent("ui:set-options", { detail: { options, value } }),
  );
}

export function setSelectValue(id: string, value: string): void {
  selectRoot(id)?.dispatchEvent(
    new CustomEvent("ui:set-value", { detail: { value } }),
  );
}

export function setSelectDisabled(id: string, disabled: boolean): void {
  selectRoot(id)?.dispatchEvent(
    new CustomEvent("ui:set-disabled", { detail: { disabled } }),
  );
}

export function selectValue(id: string): string {
  return (document.getElementById(id) as HTMLInputElement | null)?.value ?? "";
}
