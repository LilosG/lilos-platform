import { describe, expect, it, vi } from "vitest";
import { confirmInline } from "./forms";

describe("inline confirmation", () => {
  it("groups actions so message and buttons occupy two responsive grid cells", () => {
    const prompt = confirmInline("Enable provider writes?", vi.fn(), vi.fn());

    expect(prompt.classList.contains("ui-confirm-inline")).toBe(true);
    expect(prompt.children).toHaveLength(2);
    expect(
      prompt.querySelector(".ui-confirm-inline__message")?.textContent,
    ).toBe("Enable provider writes?");
    expect(
      prompt.querySelectorAll(".ui-confirm-inline__actions button"),
    ).toHaveLength(2);
  });

  it("invokes exactly one callback and removes the prompt", () => {
    const confirmed = vi.fn();
    const cancelled = vi.fn();
    const prompt = confirmInline("Continue?", confirmed, cancelled);
    document.body.append(prompt);

    prompt.querySelector<HTMLButtonElement>(".ui-button--danger")?.click();

    expect(confirmed).toHaveBeenCalledOnce();
    expect(cancelled).not.toHaveBeenCalled();
    expect(prompt.isConnected).toBe(false);
  });
});
