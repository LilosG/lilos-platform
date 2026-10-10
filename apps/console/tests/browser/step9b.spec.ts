import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
const sim = "http://127.0.0.1:4455/test";
const alpha = "/clients/synthetic-alpha/settings/";
async function scenario(mode: string) {
  const response = await fetch(`${sim}/admin-scenario`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode }),
  });
  expect(response.ok).toBe(true);
}
async function requests() {
  return (await (await fetch(`${sim}/admin-requests`)).json()).requests as {
    path: string;
    location_id?: string;
    organization_id?: string;
    body: Record<string, unknown>;
  }[];
}
async function login(page: Page, who: string, target: string) {
  await page.goto(`/login/?return=${encodeURIComponent(target)}`);
  await page.getByLabel("Email", { exact: true }).fill(`${who}@example.test`);
  await page.getByLabel("Password", { exact: true }).fill("synthetic-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.waitForURL((url) => !url.pathname.startsWith("/login"));
  await page.locator('body[data-app-ready="true"]').waitFor();
}
const clean = async (page: Page) =>
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
/** No ISO timestamp, enum value, fact key, identifier or API text in what a person reads. */
const RAW =
  /\b[A-Z]+(_[A-Z]+)+\b|\b[a-z]+(_[a-z]+)+\b|\b[a-z]+\.[a-z_]+\b(?!\w*\.\w{2,4}\b)|[0-9a-f]{8}-[0-9a-f]{4}-|\d{4}-\d{2}-\d{2}T|Platform resource/;
const noRaw = async (page: Page) => {
  const text = (await page.locator("main").innerText())
    // Website hosts are real text a person recognizes, not system text.
    .replace(/\b[\w-]+(\.[\w-]+)*\.(example\.test|com)\b/g, "");
  expect(text).not.toMatch(RAW);
};
const row = (page: Page, name: string) =>
  page.locator("tbody tr").filter({ hasText: name });
test.beforeEach(async () => scenario("default"));
test.afterEach(async () => scenario("default"));
test.describe("Administration", () => {
  test("clients: status, locations and the one action each state allows", async ({
    page,
  }) => {
    await login(page, "admin", "/administration/");
    await expect(page.locator("h1")).toHaveText("Administration");
    await expect(
      page.getByRole("navigation", { name: "Administration" }),
    ).toContainText("Clients / organizations");
    const alphaRow = row(page, "Synthetic Alpha");
    await expect(alphaRow.locator(".badge")).toHaveText("Active");
    // Six places are on file, one retired: the count is what is still in use.
    await expect(alphaRow.locator("td").nth(1)).toHaveText("6");
    await expect(alphaRow).toContainText("synthetic-alpha.example.test");
    await expect(
      alphaRow.getByRole("button", { name: "Start offboarding" }),
    ).toBeEnabled();
    // No places on file is a count of none; a count that could not be read is a dash.
    await expect(row(page, "Synthetic Beta").locator("td").nth(1)).toHaveText(
      "0",
    );
    await expect(row(page, "Synthetic Gamma").locator("td").nth(1)).toHaveText(
      "–",
    );
    await expect(row(page, "Synthetic Gamma").locator(".badge")).toHaveText(
      "Paused",
    );
    await expect(
      row(page, "Maple Street Cafe").getByRole("button", { name: "Archive" }),
    ).toBeEnabled();
    await expect(
      row(page, "Old Test Client").getByRole("button", {
        name: "Remove data permanently",
      }),
    ).toBeEnabled();
    await noRaw(page);
    await clean(page);
  });
  test("tabs that are not built resolve to the designed not-built state", async ({
    page,
  }) => {
    await login(page, "admin", "/administration/users/");
    await expect(page.locator("[data-not-built]")).toContainText(
      "Administration is not built yet",
    );
    await expect(
      page.getByRole("navigation", { name: "Administration" }),
    ).toBeVisible();
    await clean(page);
  });
  test("a person who is not an administrator sees a designed no-access state", async ({
    page,
  }) => {
    await login(page, "a", "/");
    await expect(
      page.getByRole("link", { name: "Administration" }),
    ).toHaveCount(0);
    await page.goto("/administration/");
    await expect(
      page.getByText("You do not have access to Administration"),
    ).toBeVisible();
    await expect(
      page.getByRole("link", { name: "Verify authenticator" }),
    ).toBeVisible();
    expect(await requests()).toEqual([]);
    await noRaw(page);
    await clean(page);
  });
  test("an administrator sees Administration in the navigation", async ({
    page,
  }) => {
    await login(page, "admin", "/");
    await expect(
      page.getByRole("navigation", { name: "Portfolio management" }),
    ).toContainText("Administration");
  });
  test("start offboarding asks first, then the client leaves the switcher and lists", async ({
    page,
  }) => {
    await login(page, "admin", "/administration/");
    await row(page, "Synthetic Beta")
      .getByRole("button", { name: "Start offboarding" })
      .click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toContainText("Start offboarding Synthetic Beta?");
    await expect(dialog).toContainText("leaves the client switcher");
    await noRaw(page);
    await dialog.getByRole("button", { name: "Cancel" }).click();
    expect(await requests()).toEqual([]);
    await row(page, "Synthetic Beta")
      .getByRole("button", { name: "Start offboarding" })
      .click();
    await dialog.getByRole("button", { name: "Start offboarding" }).click();
    await expect(row(page, "Synthetic Beta").locator(".badge")).toHaveText(
      "Offboarding",
    );
    await expect(
      row(page, "Synthetic Beta").getByRole("button", { name: "Archive" }),
    ).toBeEnabled();
    expect(await requests()).toMatchObject([
      { path: "start-offboarding", body: { expected_version: 3 } },
    ]);
    // Gone from the switcher and from the portfolio's client list.
    await page.goto("/clients/synthetic-alpha/settings/");
    const options = await page
      .locator("[data-client-selector] option")
      .allInnerTexts();
    expect(options).toContain("Synthetic Alpha");
    expect(options).not.toContain("Synthetic Beta");
    await page.goto("/clients/");
    await expect(page.locator("#clientrows")).not.toContainText(
      "Synthetic Beta",
    );
  });
  test("archive says it cannot be undone", async ({ page }) => {
    await login(page, "admin", "/administration/");
    await row(page, "Maple Street Cafe")
      .getByRole("button", { name: "Archive" })
      .click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toContainText("Archive Maple Street Cafe?");
    await expect(dialog).toContainText("This cannot be undone");
    await clean(page);
    await dialog.getByRole("button", { name: "Archive client" }).click();
    await expect(
      row(page, "Maple Street Cafe").locator(".badge").first(),
    ).toHaveText("Archived");
    await expect(
      row(page, "Maple Street Cafe").getByRole("button", {
        name: "Remove data permanently",
      }),
    ).toBeVisible();
    expect(await requests()).toMatchObject([
      { path: "archive", body: { expected_version: 3 } },
    ]);
  });
  test("remove needs the exact name typed, then follows the removal as a chip", async ({
    page,
  }) => {
    await page.clock.install();
    await login(page, "admin", "/administration/");
    await row(page, "Old Test Client")
      .getByRole("button", { name: "Remove data permanently" })
      .click();
    const dialog = page.getByRole("dialog");
    const accept = dialog.getByRole("button", {
      name: "Remove data permanently",
    });
    await expect(dialog).toContainText("cannot be undone");
    await expect(accept).toBeDisabled();
    const typed = dialog.getByLabel("Type Old Test Client to confirm");
    await typed.fill("old test");
    await expect(accept).toBeDisabled();
    await typed.fill("Old Test Cliente");
    await expect(accept).toBeDisabled();
    await clean(page);
    await typed.fill("Old Test Client");
    await expect(accept).toBeEnabled();
    await accept.click();
    const chip = row(page, "Old Test Client").locator(".badge").nth(1);
    await expect(chip).toHaveText("Removal requested");
    await expect(row(page, "Old Test Client").getByRole("button")).toHaveCount(
      0,
    );
    expect(await requests()).toMatchObject([
      { path: "remove", body: { confirm_name: "Old Test Client" } },
    ]);
    await page.clock.runFor(5200);
    await expect(chip).toHaveText("Removing data");
    await page.clock.runFor(5200);
    // Finished: the client is no longer listed.
    await expect(row(page, "Old Test Client")).toHaveCount(0);
  });
  test("a failed removal shows a designed message and a way to try again", async ({
    page,
  }) => {
    await scenario("removal_failed");
    await login(page, "admin", "/administration/");
    const failed = row(page, "Duplicate Cococabana");
    await expect(failed.locator(".badge").nth(1)).toHaveText("Removal failed");
    await expect(failed).toContainText(
      "The removal stopped before it finished",
    );
    await expect(failed).toContainText("contact engineering");
    await expect(
      failed.getByRole("button", { name: "Try removal again" }),
    ).toBeEnabled();
    await noRaw(page);
    await clean(page);
  });
  test("the clients list failing is a designed error, never an empty table", async ({
    page,
  }) => {
    await scenario("error");
    await login(page, "admin", "/administration/");
    await expect(
      page.getByText("Clients are temporarily unavailable"),
    ).toBeVisible();
    await expect(page.getByRole("link", { name: "Try again" })).toBeVisible();
    await expect(page.locator("table")).toHaveCount(0);
    await noRaw(page);
    await clean(page);
  });
  test("no clients is a designed empty state", async ({ page }) => {
    await scenario("no_clients");
    await login(page, "admin", "/administration/");
    await expect(page.getByText("No clients yet")).toBeVisible();
    await clean(page);
  });
});
const locationRow = (page: Page, name: string) =>
  page
    .locator('[data-settings="locations"] tbody tr')
    .filter({ hasText: name });
const buttons = async (page: Page, name: string) =>
  (await locationRow(page, name).getByRole("button").allInnerTexts()).map((t) =>
    t.trim(),
  );
test.describe("Client settings: locations", () => {
  test("each state offers only the changes the API will accept", async ({
    page,
  }) => {
    await login(page, "a", alpha);
    await expect(page.locator("h1")).toHaveText("Settings");
    const main = locationRow(page, "Main Street");
    await expect(main).toContainText("Primary");
    await expect(main).toContainText("100 Main Street, San Diego, CA 92101");
    await expect(main.locator(".badge")).toHaveText("Active");
    expect(await buttons(page, "Main Street")).toEqual([
      "Pause",
      "Close temporarily",
      "Close permanently",
      "Retire location",
    ]);
    expect(await buttons(page, "Pop-up Patio")).toEqual([
      "Resume",
      "Close temporarily",
      "Close permanently",
      "Retire location",
    ]);
    expect(await buttons(page, "Winter Lodge")).toEqual([
      "Reopen",
      "Pause",
      "Close permanently",
      "Retire location",
    ]);
    await expect(locationRow(page, "Winter Lodge")).toContainText(
      "Greater San Diego",
    );
    expect(await buttons(page, "Old Harbor")).toEqual(["Retire location"]);
    expect(await buttons(page, "New Kitchen")).toEqual([
      "Activate",
      "Retire location",
    ]);
    expect(await buttons(page, "Retired Cart")).toEqual([]);
    await expect(locationRow(page, "New Kitchen")).toContainText(
      "No address on file",
    );
    await expect(
      locationRow(page, "Retired Cart").locator(".badge"),
    ).toHaveText("Archived");
    await noRaw(page);
    await clean(page);
  });
  test("retire runs close permanently, then archive, each with the current version", async ({
    page,
  }) => {
    await login(page, "a", alpha);
    await locationRow(page, "DONT USE")
      .getByRole("button", { name: "Retire location" })
      .click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toContainText("Retire DONT USE?");
    await expect(dialog).toContainText("stops all of its automations");
    await expect(dialog).toContainText("hidden from reports");
    await clean(page);
    await dialog.getByRole("button", { name: "Retire location" }).click();
    await expect(locationRow(page, "DONT USE").locator(".badge")).toHaveText(
      "Archived",
    );
    expect(await buttons(page, "DONT USE")).toEqual([]);
    const sent = await requests();
    expect(sent.map((r) => r.path)).toEqual(["close-permanently", "archive"]);
    expect(sent.map((r) => r.body.expected_version)).toEqual([2, 3]);
  });
  test("a retirement that stops says which step it reached", async ({
    page,
  }) => {
    await scenario("retire_archive_fails");
    await login(page, "a", alpha);
    await locationRow(page, "DONT USE")
      .getByRole("button", { name: "Retire location" })
      .click();
    const dialog = page.getByRole("dialog");
    await dialog.getByRole("button", { name: "Retire location" }).click();
    await expect(dialog.getByRole("alert")).toContainText(
      "It was closed permanently, but archiving it did not go through.",
    );
    await expect(dialog).toContainText("not available for this location");
    await noRaw(page);
    await clean(page);
    await dialog.getByRole("button", { name: "Cancel" }).click();
    await page.reload();
    await expect(locationRow(page, "DONT USE").locator(".badge")).toHaveText(
      "Permanently closed",
    );
    expect(await buttons(page, "DONT USE")).toEqual(["Retire location"]);
  });
  test("a single change asks first and sends one call", async ({ page }) => {
    await login(page, "a", alpha);
    await locationRow(page, "Pop-up Patio")
      .getByRole("button", { name: "Resume" })
      .click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toContainText("Activate Pop-up Patio?");
    await dialog.getByRole("button", { name: "Activate" }).click();
    await expect(
      locationRow(page, "Pop-up Patio").locator(".badge"),
    ).toHaveText("Active");
    expect(await requests()).toMatchObject([
      { path: "activate", body: { expected_version: 2 } },
    ]);
  });
  test("locations that cannot be read are an error state, not an empty list", async ({
    page,
  }) => {
    await scenario("locations_error");
    await login(page, "a", alpha);
    await expect(page.getByText("Locations could not be loaded")).toBeVisible();
    // The other section still works.
    await expect(
      page.getByRole("button", { name: "Add or change a fact" }).first(),
    ).toBeVisible();
    await noRaw(page);
    await clean(page);
  });
  test("no locations is a designed empty state", async ({ page }) => {
    await scenario("locations_empty");
    await login(page, "a", alpha);
    await expect(page.getByText("No locations yet")).toBeVisible();
    await clean(page);
  });
});
const factRow = (page: Page, label: string) =>
  page.locator('[data-settings="facts"] tbody tr').filter({ hasText: label });
test.describe("Client settings: business facts", () => {
  test("facts read as plain rows with where they came from", async ({
    page,
  }) => {
    await login(page, "a", alpha);
    const name = factRow(page, "Business name");
    await expect(name).toContainText("Synthetic Alpha");
    await expect(name.locator(".badge")).toHaveText("Confirmed by our team");
    await expect(factRow(page, "Address")).toContainText(
      "100 Main Street, San Diego, CA 92101",
    );
    await expect(factRow(page, "Address").locator(".badge")).toHaveText(
      "From Google",
    );
    await expect(factRow(page, "Opening hours")).toContainText(
      "Open 5 days a week",
    );
    await expect(factRow(page, "Approved claims")).toContainText(
      "Family owned since 1998 · Fresh tortillas made daily",
    );
    await expect(factRow(page, "Other detail")).toContainText("12-345");
    await noRaw(page);
    await clean(page);
  });
  test("an operator who cannot approve leaves the fact waiting for approval", async ({
    page,
  }) => {
    await login(page, "a", alpha);
    await page
      .getByRole("button", { name: "Add or change a fact" })
      .first()
      .click();
    const dialog = page.getByRole("dialog");
    await expect(dialog.getByRole("button", { name: "Save" })).toBeDisabled();
    await dialog
      .getByLabel("What is it?")
      .selectOption({ label: "Business name" });
    await expect(
      dialog.getByRole("textbox", { name: "Business name" }),
    ).toHaveValue("Synthetic Alpha");
    await dialog
      .getByRole("textbox", { name: "Business name" })
      .fill("Synthetic Alpha Kitchen");
    await clean(page);
    await dialog.getByRole("button", { name: "Save" }).click();
    const waiting = page
      .locator('[data-settings="facts"] tbody tr')
      .filter({ hasText: "Synthetic Alpha Kitchen" });
    await expect(waiting.locator(".badge")).toHaveText("Waiting for approval");
    await expect(factRow(page, "Business name").first()).toBeVisible();
    const sent = await requests();
    expect(sent.map((r) => r.path)).toEqual(["business-facts", "decision"]);
    expect(sent[0].body).toMatchObject({
      fact_key: "business.name",
      value: "Synthetic Alpha Kitchen",
      value_type: "string",
      authority: "operator_verified",
      fact_identity: "00000011-0000-4000-8000-000000000000",
    });
    await noRaw(page);
  });
  test("an administrator's change is approved in the same step", async ({
    page,
  }) => {
    await login(page, "admin", alpha);
    await factRow(page, "Approved claims")
      .getByRole("button", { name: "Change" })
      .click();
    const dialog = page.getByRole("dialog");
    const claims = dialog.getByLabel("Claims, one per line");
    await expect(claims).toHaveValue(
      "Family owned since 1998\nFresh tortillas made daily",
    );
    await claims.fill("Family owned since 1998\nOpen late on weekends");
    await dialog.getByRole("button", { name: "Save" }).click();
    await expect(factRow(page, "Approved claims")).toContainText(
      "Open late on weekends",
    );
    await expect(factRow(page, "Approved claims").locator(".badge")).toHaveText(
      "Confirmed by our team",
    );
    await expect(page.getByText("Waiting for approval")).toHaveCount(0);
    const sent = await requests();
    expect(sent[0].body).toMatchObject({
      value_type: "string_list",
      value: ["Family owned since 1998", "Open late on weekends"],
    });
    expect(sent[1].body).toEqual({ decision: "approve" });
  });
  test("a new address is filed against the primary location", async ({
    page,
  }) => {
    await login(page, "admin", alpha);
    await page
      .getByRole("button", { name: "Add or change a fact" })
      .first()
      .click();
    const dialog = page.getByRole("dialog");
    await dialog.getByLabel("What is it?").selectOption({ label: "Address" });
    await dialog
      .getByRole("textbox", { name: "Street address" })
      .fill("200 Ocean Avenue");
    await dialog.getByLabel("City", { exact: true }).fill("Carlsbad");
    await dialog.getByLabel("State").fill("CA");
    await dialog.getByLabel("Postal code").fill("92008");
    await clean(page);
    await dialog.getByRole("button", { name: "Save" }).click();
    await expect(factRow(page, "Address")).toContainText(
      "200 Ocean Avenue, Carlsbad, CA 92008",
    );
  });
  test("empty and failed fact lists are designed states", async ({ page }) => {
    await scenario("facts_empty");
    await login(page, "a", alpha);
    await expect(page.getByText("No business facts yet")).toBeVisible();
    await clean(page);
    await scenario("facts_error");
    await page.reload();
    await expect(
      page.getByText("Business facts could not be loaded"),
    ).toBeVisible();
    await expect(page.locator('[data-settings="facts"] table')).toHaveCount(0);
    await noRaw(page);
    await clean(page);
  });
});
