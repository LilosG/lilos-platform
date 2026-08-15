export function card(title?: string, description?: string): HTMLDivElement {
  const card = document.createElement("div");
  card.className = "ui-card";
  if (title) {
    const header = document.createElement("div");
    header.className = "ui-card__header";
    const titleEl = document.createElement("h3");
    titleEl.className = "ui-card__heading";
    titleEl.textContent = title;
    const identity = document.createElement("div");
    identity.append(titleEl);
    if (description) {
      const desc = document.createElement("p");
      desc.className = "ui-card__description";
      desc.textContent = description;
      identity.append(desc);
    }
    header.append(identity);
    card.append(header);
  }
  return card;
}

export function cardBody(): HTMLDivElement {
  const body = document.createElement("div");
  body.className = "ui-card__body";
  return body;
}

export function sectionCard(title: string, description?: string): HTMLElement {
  const section = document.createElement("section");
  section.className = "ui-card";
  const header = document.createElement("div");
  header.className = "ui-card__header";
  const titleElement = document.createElement("h3");
  titleElement.className = "ui-card__heading";
  titleElement.textContent = title;
  const identity = document.createElement("div");
  identity.append(titleElement);
  if (description) {
    const descriptionElement = document.createElement("p");
    descriptionElement.className = "ui-card__description";
    descriptionElement.textContent = description;
    identity.append(descriptionElement);
  }
  header.append(identity);
  section.append(header, cardBody());
  return section;
}

export function detailFact(label: string, value: string): HTMLDivElement {
  const row = document.createElement("div");
  row.className = "ui-inline ui-inline--center ui-inline--spread";
  const labelElement = document.createElement("strong");
  labelElement.textContent = label;
  const valueElement = document.createElement("span");
  valueElement.textContent = value;
  row.append(labelElement, valueElement);
  return row;
}

export function liveStatus(): HTMLParagraphElement {
  const status = document.createElement("p");
  status.className = "ui-text-secondary";
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "polite");
  return status;
}

export function metricCard(
  label: string,
  value: string | null,
  meta?: string,
  trend?: string,
): HTMLDivElement {
  const card = document.createElement("div");
  card.className = "ui-card ui-metric-card";
  const body = document.createElement("div");
  body.className = "ui-card__body";
  const labelEl = document.createElement("p");
  labelEl.className = "ui-metric-card__label";
  labelEl.textContent = label;
  const valueEl = document.createElement("p");
  valueEl.className = "ui-metric-card__value";
  valueEl.textContent = value ?? "—";
  body.append(labelEl, valueEl);
  if (meta) {
    const metaEl = document.createElement("p");
    metaEl.className = "ui-metric-card__meta";
    metaEl.textContent = meta;
    body.append(metaEl);
  }
  if (trend) {
    const trendEl = document.createElement("p");
    trendEl.className = "ui-metric-card__meta";
    trendEl.textContent = trend;
    body.append(trendEl);
  }
  card.append(body);
  return card;
}

export function metricGrid(
  metrics: { label: string; value: string | null; meta?: string }[],
): HTMLDivElement {
  const grid = document.createElement("div");
  grid.className = "ui-card-grid ui-card-grid--sm";
  for (const m of metrics) {
    grid.append(metricCard(m.label, m.value, m.meta));
  }
  return grid;
}

export function sectionHeader(
  eyebrow: string,
  title: string,
  description?: string,
): HTMLDivElement {
  const header = document.createElement("div");
  header.className = "ui-page-section__header";
  const left = document.createElement("div");
  const eyebrowEl = document.createElement("p");
  eyebrowEl.className = "ui-overline";
  eyebrowEl.textContent = eyebrow;
  const titleEl = document.createElement("h2");
  titleEl.textContent = title;
  left.append(eyebrowEl, titleEl);
  header.append(left);
  if (description) {
    const desc = document.createElement("p");
    desc.className = "ui-page-section__description";
    desc.textContent = description;
    left.append(desc);
  }
  return header;
}

export function actionButton(
  label: string,
  onClick: () => void,
  variant: "primary" | "secondary" | "danger" = "primary",
  size: "sm" | "md" = "md",
): HTMLButtonElement {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `ui-button ui-button--${variant} ui-button--${size}`;
  button.textContent = label;
  button.addEventListener("click", onClick);
  return button;
}

export function linkButton(
  label: string,
  href: string,
  variant: "primary" | "secondary" = "secondary",
  size: "sm" | "md" = "md",
): HTMLAnchorElement {
  const link = document.createElement("a");
  link.className = `ui-button ui-button--${variant} ui-button--${size}`;
  link.href = href;
  link.textContent = label;
  return link;
}
