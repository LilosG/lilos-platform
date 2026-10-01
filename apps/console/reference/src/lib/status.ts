export function statusTone(text: string): "error" | "warn" | "neutral" | "" {
  return /Error|Failed|Disconnected|Critical|High|Tracking/.test(text)
    ? "error"
    : /attention|review|issue|Missing|Medium|Declining/.test(text)
      ? "warn"
      : /Upcoming|configured|Stable|New/.test(text)
        ? "neutral"
        : "";
}
export function updateBadge(element: HTMLElement, text: string) {
  element.textContent = text;
  element.className = "badge " + statusTone(text);
}
