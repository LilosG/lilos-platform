// @vitest-environment happy-dom
import { it, expect, vi } from "vitest";
it("binds streamed forms at document readiness and sends the exact discovered property", async () => {
  Object.defineProperty(document, "readyState", {
    value: "loading",
    configurable: true,
  });
  document.body.innerHTML =
    '<meta name="csrf-token" content="bound-nonce"><p data-integration-status></p>';
  const fetcher = vi.fn(
    async (_url: RequestInfo | URL, _init?: RequestInit) =>
      new Response(
        JSON.stringify({
          data: {
            properties: [
              {
                external_property_id: "sc-domain:example.test",
                property_type: "domain",
              },
            ],
          },
        }),
        { headers: { "Content-Type": "application/json" } },
      ),
  );
  vi.stubGlobal("fetch", fetcher);
  await import("../../src/lib/integration-actions");
  const form = document.createElement("form");
  form.setAttribute("data-discovery", "");
  form.dataset.source = "search_console";
  form.dataset.api = "/api/organizations/11111111-1111-4111-8111-111111111111/";
  form.innerHTML =
    '<select name="website_id"><option value="11111111-1111-4111-8111-111111111111">Exact website</option></select><button type="submit">Find</button><div data-discovered></div>';
  document.body.append(form);
  document.dispatchEvent(new Event("DOMContentLoaded"));
  const event = new Event("submit", { cancelable: true });
  form.dispatchEvent(event);
  expect(event.defaultPrevented).toBe(true);
  await vi.waitFor(() =>
    expect(form.querySelector("[data-discovered] button")?.textContent).toBe(
      "Match example.test",
    ),
  );
  expect(fetcher.mock.calls).toHaveLength(1);
  vi.unstubAllGlobals();
});
