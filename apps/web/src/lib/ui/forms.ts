export function formField(
  label: string,
  input: HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement,
  options?: {
    hint?: string;
    error?: string;
    full?: boolean;
    id?: string;
  },
): HTMLDivElement {
  const field = document.createElement("div");
  field.className = `field${options?.full ? " field--full" : ""}`;
  const labelEl = document.createElement("label");
  if (options?.id) {
    labelEl.htmlFor = options.id;
    input.id = options.id;
  }
  labelEl.textContent = label;
  field.append(labelEl);
  if (options?.hint) {
    const hint = document.createElement("p");
    hint.className = "field-hint";
    hint.textContent = options.hint;
    field.append(hint);
  }
  field.append(input);
  if (options?.error) {
    const errorEl = document.createElement("p");
    errorEl.className = "field-error";
    errorEl.textContent = options.error;
    field.append(errorEl);
    field.classList.add("field--invalid");
  }
  return field;
}

export function textInput(
  placeholder?: string,
  type: string = "text",
): HTMLInputElement {
  const input = document.createElement("input");
  input.type = type;
  if (placeholder) input.placeholder = placeholder;
  return input;
}

export function selectInput(
  options: { value: string; label: string }[],
  placeholder?: string,
): HTMLSelectElement {
  const select = document.createElement("select");
  if (placeholder) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = placeholder;
    select.append(opt);
  }
  for (const opt of options) {
    const option = document.createElement("option");
    option.value = opt.value;
    option.textContent = opt.label;
    select.append(option);
  }
  return select;
}

export function textArea(rows = 3): HTMLTextAreaElement {
  const textarea = document.createElement("textarea");
  textarea.rows = rows;
  return textarea;
}

export function formActions(
  primary: HTMLButtonElement | HTMLAnchorElement,
  secondary?: HTMLButtonElement | HTMLAnchorElement,
): HTMLDivElement {
  const actions = document.createElement("div");
  actions.className = "form-actions";
  actions.append(primary);
  if (secondary) actions.append(secondary);
  return actions;
}

export function formSection(
  title: string,
  description?: string,
): HTMLDivElement {
  const section = document.createElement("div");
  section.className = "form-section";
  const titleEl = document.createElement("h3");
  titleEl.className = "form-section__title";
  titleEl.textContent = title;
  section.append(titleEl);
  if (description) {
    const desc = document.createElement("p");
    desc.className = "form-section__desc";
    desc.textContent = description;
    section.append(desc);
  }
  return section;
}

export function confirmInline(
  message: string,
  onConfirm: () => void,
  onCancel: () => void,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
): HTMLDivElement {
  const prompt = document.createElement("div");
  prompt.className = "confirm-inline";
  const msg = document.createElement("p");
  msg.textContent = message;
  const confirmBtn = document.createElement("button");
  confirmBtn.type = "button";
  confirmBtn.className = "button button--danger button--sm";
  confirmBtn.textContent = confirmLabel;
  confirmBtn.addEventListener("click", () => {
    onConfirm();
    prompt.remove();
  });
  const cancelBtn = document.createElement("button");
  cancelBtn.type = "button";
  cancelBtn.className = "button button--secondary button--sm";
  cancelBtn.textContent = cancelLabel;
  cancelBtn.addEventListener("click", () => {
    onCancel();
    prompt.remove();
  });
  prompt.append(msg, confirmBtn, cancelBtn);
  return prompt;
}
