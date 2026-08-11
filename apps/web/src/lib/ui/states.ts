export function errorAlert(message: string): HTMLDivElement {
  const alert = document.createElement("div");
  alert.className = "alert alert--error";
  alert.setAttribute("role", "alert");
  const text = document.createElement("p");
  text.textContent = message;
  alert.append(text);
  return alert;
}

export function infoAlert(message: string): HTMLDivElement {
  const alert = document.createElement("div");
  alert.className = "alert alert--info";
  const text = document.createElement("p");
  text.textContent = message;
  alert.append(text);
  return alert;
}

export function successAlert(message: string): HTMLDivElement {
  const alert = document.createElement("div");
  alert.className = "alert alert--success";
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
  wrap.className = "empty-state";
  const icon = document.createElement("span");
  icon.className = "empty-state__icon";
  icon.setAttribute("aria-hidden", "true");
  icon.textContent = "○";
  const title = document.createElement("h3");
  title.textContent = heading;
  const body = document.createElement("p");
  body.textContent = description;
  wrap.append(icon, title, body);
  if (actionLabel && actionHref) {
    const link = document.createElement("a");
    link.className = "button button--secondary button--sm";
    link.href = actionHref;
    link.textContent = actionLabel;
    wrap.append(link);
  }
  return wrap;
}

export function loadingState(message = "Loading…"): HTMLDivElement {
  const wrap = document.createElement("div");
  wrap.className = "loading-state";
  wrap.textContent = message;
  return wrap;
}
