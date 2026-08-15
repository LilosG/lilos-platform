export function errorAlert(
  message: string,
  recoveryLabel = "Try again",
  onRecovery: () => void = () => window.location.reload(),
): HTMLDivElement {
  const alert = document.createElement("div");
  alert.className = "ui-notice ui-notice--danger";
  alert.setAttribute("role", "alert");
  const text = document.createElement("p");
  text.textContent = message;
  const recovery = document.createElement("button");
  recovery.type = "button";
  recovery.className = "ui-button ui-button--secondary ui-button--sm";
  recovery.textContent = recoveryLabel;
  recovery.addEventListener("click", onRecovery);
  alert.append(text, recovery);
  return alert;
}

export function infoAlert(message: string): HTMLDivElement {
  const alert = document.createElement("div");
  alert.className = "ui-notice ui-notice--info";
  const text = document.createElement("p");
  text.textContent = message;
  alert.append(text);
  return alert;
}

export function successAlert(message: string): HTMLDivElement {
  const alert = document.createElement("div");
  alert.className = "ui-notice ui-notice--success";
  const text = document.createElement("p");
  text.textContent = message;
  alert.append(text);
  return alert;
}

export function emptyState(
  heading: string,
  description: string,
  actionLabel?: string,
  actionHref?: string,
): HTMLDivElement {
  const wrap = document.createElement("div");
  wrap.className = "ui-empty-state";
  const content = document.createElement("div");
  content.className = "ui-empty-state__content";
  const title = document.createElement("h3");
  title.textContent = heading;
  const body = document.createElement("p");
  body.textContent = description;
  content.append(title, body);
  wrap.append(content);
  if (actionLabel && actionHref) {
    const link = document.createElement("a");
    link.className = "ui-button ui-button--secondary ui-button--sm";
    link.href = actionHref;
    link.textContent = actionLabel;
    wrap.append(link);
  }
  return wrap;
}

export function loadingState(message = "Loading…"): HTMLDivElement {
  const wrap = document.createElement("div");
  wrap.className = "ui-skeleton-group";
  wrap.textContent = message;
  return wrap;
}
