export function card(title?: string, description?: string): HTMLDivElement {
  const card = document.createElement("div");
  card.className = "card";
  if (title) {
    const header = document.createElement("div");
    header.className = "card__header";
    const titleEl = document.createElement("h3");
    titleEl.className = "card__title";
    titleEl.textContent = title;
    header.append(titleEl);
    if (description) {
      const desc = document.createElement("p");
      desc.className = "card__description";
      desc.textContent = description;
      header.append(desc);
    }
    card.append(header);
  }
  return card;
}

export function cardBody(): HTMLDivElement {
  const body = document.createElement("div");
  body.className = "card__body";
  return body;
}

export function metricCard(
  label: string,
  value: string | null,
  meta?: string,
  trend?: string,
): HTMLDivElement {
  const card = document.createElement("div");
  card.className = "metric-card";
  const labelEl = document.createElement("p");
  labelEl.className = "metric-card__label";
  labelEl.textContent = label;
  const valueEl = document.createElement("p");
  valueEl.className = "metric-card__value";
  valueEl.textContent = value ?? "—";
  card.append(labelEl, valueEl);
  if (meta) {
    const metaEl = document.createElement("p");
    metaEl.className = "metric-card__meta";
    metaEl.textContent = meta;
    card.append(metaEl);
  }
  if (trend) {
    const trendEl = document.createElement("p");
    trendEl.className = "metric-card__trend";
    trendEl.textContent = trend;
    card.append(trendEl);
  }
  return card;
}

export function metricGrid(
  metrics: { label: string; value: string | null; meta?: string }[],
): HTMLDivElement {
  const grid = document.createElement("div");
  grid.className = "metric-grid";
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
  header.className = "section-heading";
  const left = document.createElement("div");
  const eyebrowEl = document.createElement("p");
  eyebrowEl.className = "eyebrow";
  eyebrowEl.textContent = eyebrow;
  const titleEl = document.createElement("h2");
  titleEl.textContent = title;
  left.append(eyebrowEl, titleEl);
  header.append(left);
  if (description) {
    const desc = document.createElement("p");
    desc.className = "section-heading__desc";
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
  button.className = `button${variant !== "primary" ? ` button--${variant}` : ""}${size === "sm" ? " button--sm" : ""}`;
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
  link.className = `button${variant !== "primary" ? ` button--${variant}` : ""}${size === "sm" ? " button--sm" : ""}`;
  link.href = href;
  link.textContent = label;
  return link;
}
