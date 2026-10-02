export function statusTone(text: string): "error" | "warn" | "neutral" | "" {
  return /Error|Failed|Disconnected|Critical|High|Tracking/.test(text)
    ? "error"
    : /attention|review|issue|Missing|Medium|Declining/.test(text)
      ? "warn"
      : /Upcoming|configured|Stable|New|connected|access|tracked/.test(text)
        ? "neutral"
        : "";
}
