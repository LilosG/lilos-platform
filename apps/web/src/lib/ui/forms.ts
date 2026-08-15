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
  field.className = `ui-field${options?.full ? " ui-field--full" : ""}`;
  const labelEl = document.createElement("label");
  labelEl.className = "ui-field__label";
  if (options?.id) {
    labelEl.htmlFor = options.id;
    input.id = options.id;
  }
  labelEl.textContent = label;
  field.append(labelEl);
  if (options?.hint) {
    const hint = document.createElement("p");
    hint.className = "ui-field__description";
    hint.textContent = options.hint;
    field.append(hint);
  }
  input.classList.add(
    input instanceof HTMLTextAreaElement ? "ui-textarea" : "ui-input",
  );
  field.append(input);
  if (options?.error) {
    const errorEl = document.createElement("p");
    errorEl.className = "ui-field__error";
    errorEl.textContent = options.error;
    field.append(errorEl);
    field.dataset.state = "error";
  }
  return field;
}

export function textInput(
  placeholder?: string,
  type: string = "text",
): HTMLInputElement {
  const input = document.createElement("input");
  input.className = "ui-input";
  input.type = type;
  if (placeholder) input.placeholder = placeholder;
  return input;
}

export function selectInput(
  options: { value: string; label: string }[],
  placeholder?: string,
): HTMLSelectElement {
  const select = document.createElement("select");
  select.className = "ui-input";
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
  textarea.className = "ui-textarea";
  textarea.rows = rows;
  return textarea;
}

export function formActions(
  primary: HTMLButtonElement | HTMLAnchorElement,
  secondary?: HTMLButtonElement | HTMLAnchorElement,
): HTMLDivElement {
  const actions = document.createElement("div");
  actions.className = "ui-inline ui-inline--center";
  actions.append(primary);
  if (secondary) actions.append(secondary);
  return actions;
}

export function formSection(
  title: string,
  description?: string,
): HTMLDivElement {
  const section = document.createElement("div");
  section.className = "ui-stack ui-stack--2";
  const titleEl = document.createElement("h3");
  titleEl.className = "ui-card__heading";
  titleEl.textContent = title;
  section.append(titleEl);
  if (description) {
    const desc = document.createElement("p");
    desc.className = "ui-card__description";
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
  prompt.className = "ui-notice ui-notice--warning";
  const msg = document.createElement("p");
  msg.textContent = message;
  const confirmBtn = document.createElement("button");
  confirmBtn.type = "button";
  confirmBtn.className = "ui-button ui-button--danger ui-button--sm";
  confirmBtn.textContent = confirmLabel;
  confirmBtn.addEventListener("click", () => {
    onConfirm();
    prompt.remove();
  });
  const cancelBtn = document.createElement("button");
  cancelBtn.type = "button";
  cancelBtn.className = "ui-button ui-button--secondary ui-button--sm";
  cancelBtn.textContent = cancelLabel;
  cancelBtn.addEventListener("click", () => {
    onCancel();
    prompt.remove();
  });
  prompt.append(msg, confirmBtn, cancelBtn);
  return prompt;
}
