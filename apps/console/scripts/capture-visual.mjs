// Captures each changed screen at 1440px and 390px next to its reference screen.
//
//   REFERENCE=http://127.0.0.1:4401 CONSOLE=http://127.0.0.1:4346 \
//     node scripts/capture-visual.mjs <step-folder>
//
// The console runs against the synthetic simulator (tests/browser/upstream.mjs); the reference
// app runs from apps/console/reference. Nothing here touches production data.
import { mkdir, writeFile } from "node:fs/promises";
import { chromium } from "@playwright/test";
const reference = process.env.REFERENCE ?? "http://127.0.0.1:4401";
const consoleUrl = process.env.CONSOLE ?? "http://127.0.0.1:4346";
const stepName = process.argv[2] ?? "step-4c";
const out = new URL(`../visual/${stepName}/`, import.meta.url);
const sizes = { desktop: [1440, 1000], mobile: [390, 844] };
const gbp = "/clients/synthetic-beta/local-search/google-business-profile/";
const coco = "/clients/coco-maya/local-search/";
// Each screen: the console route, the user to sign in as, the nearest reference route, and
// an optional step that opens a dialog before the capture.
const hours = `${gbp}?view=special-hours`;
const photos = `${gbp}?view=photos`;
const beta = "http://127.0.0.1:4455";
const reset = () =>
  fetch(`${beta}/test/gbp-reset`, { method: "POST", body: "{}" });
const emptyPhotos = async () => {
  await reset();
  await fetch(`${beta}/test/gbp-clear-media`, { method: "POST", body: "{}" });
};
// A synthetic photo chosen through the real file input, as a person would.
const choosePhoto = async (page) => {
  await page.getByRole("button", { name: "Add photo" }).first().click();
  await page.locator("dialog[open]").waitFor();
  await page.locator("[data-photo-input]").evaluate(async (input) => {
    const canvas = document.createElement("canvas");
    canvas.width = 640;
    canvas.height = 480;
    const g = canvas.getContext("2d");
    const sky = g.createLinearGradient(0, 0, 0, 480);
    sky.addColorStop(0, "#f6a15c");
    sky.addColorStop(1, "#235448");
    g.fillStyle = sky;
    g.fillRect(0, 0, 640, 480);
    for (let i = 0; i < 4000; i++) {
      g.fillStyle = `rgba(255,255,255,${Math.random() * 0.25})`;
      g.fillRect(Math.random() * 640, Math.random() * 480, 3, 3);
    }
    const blob = await new Promise((r) => canvas.toBlob(r, "image/png"));
    const transfer = new DataTransfer();
    transfer.items.add(new File([blob], "patio.png", { type: "image/png" }));
    input.files = transfer.files;
    input.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await page.locator("[data-photo-preview]").waitFor({ state: "visible" });
  await page.getByLabel("Who may use it").selectOption("Owned by the business");
};
const closedAllDay = async (page) => {
  await page.getByRole("button", { name: "Add special hours" }).first().click();
  await page.locator("dialog[open]").waitFor();
  await page.getByLabel("Date", { exact: true }).fill("2026-12-31");
  await page.getByLabel("Closed all day").check();
};
// Each screen: name, the user to sign in as, the console route, the nearest reference route,
// and an optional step before the capture.
const screens = [
  ["local-search-overview", "b", "/clients/synthetic-beta/local-search/", coco],
  [
    "gbp-photos-empty",
    "b",
    photos,
    `${coco}google-business-profile/`,
    undefined,
    emptyPhotos,
  ],
  [
    "gbp-photos-selected",
    "b",
    photos,
    `${coco}google-business-profile/`,
    choosePhoto,
    reset,
  ],
  [
    "gbp-photos-grid",
    "b",
    photos,
    `${coco}google-business-profile/`,
    undefined,
    reset,
  ],
  [
    "special-hours-form",
    "b",
    hours,
    `${coco}google-business-profile/`,
    closedAllDay,
    reset,
  ],
  [
    "special-hours-list",
    "b",
    hours,
    `${coco}google-business-profile/`,
    undefined,
    reset,
  ],
  ["client-overview", "a", "/clients/synthetic-alpha/", "/clients/coco-maya/"],
];
// Step 6: the Reviews inbox, an empty source, source details, a filter and the response dialog.
const reviewsAlpha = "/clients/synthetic-alpha/reviews/";
const detailPath = `${reviewsAlpha}locations/77777777-7777-4777-8777-777777777777/33333333-3333-4333-8333-333333333333/`;
const referenceReviews = "/clients/coco-maya/reviews/";
const openSource = async (page) => {
  await page.getByRole("button", { name: /Review source status/ }).click();
  await page.locator("dialog[open]").waitFor();
};
const referenceRespond = async (page) => {
  await page.getByRole("button", { name: "Respond" }).first().click();
  await page.locator("dialog[open]").waitFor();
};
const referenceAwaiting = async (page) => {
  await page.getByRole("button", { name: "Awaiting approval" }).first().click();
};
const reviewScreens = [
  ["reviews-inbox", "a", reviewsAlpha, referenceReviews],
  [
    "reviews-awaiting-approval",
    "a",
    `${reviewsAlpha}?status=awaiting_approval`,
    referenceReviews,
    undefined,
    undefined,
    referenceAwaiting,
  ],
  ["reviews-empty", "b", "/clients/synthetic-beta/reviews/", referenceReviews],
  ["reviews-source-details", "a", reviewsAlpha, referenceReviews, openSource],
  [
    "reviews-response",
    "a",
    detailPath,
    referenceReviews,
    undefined,
    undefined,
    referenceRespond,
  ],
];
// Step 5a: Website & Content. The reference's standard client stands for every tab; each console
// screen is shown in the simulator scenario that exercises it.
const site = "/clients/synthetic-alpha/website-content/";
const referenceSite = "/clients/northline-electric/website-content/";
const scenario = (mode) => () =>
  fetch(`${beta}/test/website-scenario`, {
    method: "POST",
    body: JSON.stringify({ mode }),
  });
const openWebsiteDetails = async (page) => {
  await page.getByRole("button", { name: /Website data status/ }).click();
  await page.locator("dialog[open]").waitFor();
};
const referenceInspect = async (page) => {
  await page.getByRole("button", { name: "Inspect" }).first().click();
  await page.locator("dialog[open]").waitFor();
};
const websiteScreens = [
  ["website-overview", "a", site, referenceSite, undefined, scenario("rich")],
  [
    "website-pages",
    "a",
    `${site}pages/`,
    `${referenceSite}pages/`,
    undefined,
    scenario("rich"),
  ],
  [
    "website-technical",
    "a",
    `${site}technical/`,
    `${referenceSite}technical/`,
    undefined,
    scenario("rich"),
  ],
  [
    "website-conversions",
    "a",
    `${site}conversions/`,
    `${referenceSite}conversions/`,
    undefined,
    scenario("rich"),
  ],
  [
    "website-page-detail",
    "a",
    `${site}pages/11111111-1111-4111-8111-111111111111/00000002-0000-4000-8000-000000000000/`,
    `${referenceSite}pages/`,
    undefined,
    scenario("rich"),
    referenceInspect,
  ],
  [
    "website-page-detail-unlinked",
    "a",
    `${site}pages/11111111-1111-4111-8111-111111111111/00000002-0000-4000-8000-000000000000/`,
    `${referenceSite}pages/`,
    undefined,
    scenario("clean"),
    referenceInspect,
  ],
  [
    "website-details",
    "a",
    site,
    referenceSite,
    openWebsiteDetails,
    scenario("rich"),
  ],
  ["website-empty", "a", site, referenceSite, undefined, scenario("empty")],
  [
    "website-pages-empty",
    "a",
    `${site}pages/`,
    `${referenceSite}pages/`,
    undefined,
    scenario("empty"),
  ],
  [
    "website-not-connected",
    "a",
    site,
    referenceSite,
    undefined,
    scenario("no_website"),
  ],
  [
    "website-technical-clean",
    "a",
    `${site}technical/`,
    `${referenceSite}technical/`,
    undefined,
    scenario("clean"),
  ],
  ["website-error", "a", site, referenceSite, undefined, scenario("error")],
];
// Step 5b: the Content tab, the composer, the draft review and the approval. The reference's
// Content tab and its content dialog stand in for them; the console shows each in the scenario
// that exercises it.
const hexId = (n) =>
  `${n.toString(16).padStart(8, "0")}-0000-4000-8000-000000000000`;
const readyDraft = `${site}content/${hexId(0xc1)}/`;
const referenceContent = `${referenceSite}content/`;
const referenceOpenContent = async (page) => {
  await page.getByRole("button", { name: "Edit brief" }).first().click();
  await page.locator("dialog[open]").waitFor();
};
const openComposer = async (page) => {
  await page.getByRole("button", { name: "New content" }).click();
  await page.locator("dialog[open]").waitFor();
  await page
    .getByLabel("What should it be about?")
    .fill("listicle: best places to watch Packers games in San Diego");
  await page.getByText("Listicle", { exact: true }).click();
};
const openApproval = async (page) => {
  await page.getByRole("button", { name: "Confirm" }).click();
  await page.locator("[data-claim='confirmed']").waitFor();
  await page.getByRole("button", { name: "Approve…" }).click();
  await page.locator("#content-approval[open]").waitFor();
};
const openRegenerate = async (page) => {
  await page.getByRole("button", { name: "Regenerate…" }).click();
  await page
    .getByLabel("What should change?")
    .fill("make it longer, add a section on game-day specials");
};
const contentScreens = [
  [
    "content-list",
    "a",
    `${site}content/`,
    referenceContent,
    undefined,
    scenario("content"),
  ],
  [
    "content-composer",
    "a",
    `${site}content/`,
    referenceContent,
    openComposer,
    scenario("content"),
    referenceOpenContent,
  ],
  [
    "content-empty",
    "a",
    `${site}content/`,
    referenceContent,
    undefined,
    scenario("content_empty"),
  ],
  [
    "content-not-connected",
    "a",
    `${site}content/`,
    referenceContent,
    undefined,
    scenario("no_website"),
  ],
  [
    "content-error",
    "a",
    `${site}content/`,
    referenceContent,
    undefined,
    scenario("error"),
  ],
  [
    "content-draft-review",
    "admin",
    readyDraft,
    referenceContent,
    undefined,
    scenario("content"),
    referenceOpenContent,
  ],
  [
    "content-regenerate",
    "admin",
    readyDraft,
    referenceContent,
    openRegenerate,
    scenario("content"),
    referenceOpenContent,
  ],
  [
    "content-approval",
    "admin",
    readyDraft,
    referenceContent,
    openApproval,
    scenario("content"),
    referenceOpenContent,
  ],
  [
    "content-writing",
    "a",
    `${site}content/${hexId(0xc2)}/`,
    referenceContent,
    undefined,
    scenario("content"),
    referenceOpenContent,
  ],
  [
    "content-failed",
    "a",
    `${site}content/${hexId(0xc3)}/`,
    referenceContent,
    undefined,
    scenario("content"),
    referenceOpenContent,
  ],
  [
    "content-landing-page-review",
    "a",
    `${site}content/${hexId(0xc4)}/`,
    referenceContent,
    undefined,
    scenario("content"),
    referenceOpenContent,
  ],
];
// Dashboard GBP actions column: the platform administrator sees every client, so all three cell
// states (trend, no previous period, not connected) are on screen.
const dashboardScreens = [["dashboard-gbp-actions", "admin", "/", "/"]];
async function signIn(context, who) {
  const page = await context.newPage();
  await page.goto(`${consoleUrl}/login/`);
  await page.getByLabel("Email", { exact: true }).fill(`${who}@example.test`);
  await page.getByLabel("Password", { exact: true }).fill("synthetic-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.waitForURL((url) => !url.pathname.startsWith("/login"));
  await page.close();
}
const swatch = (name) => {
  const hue = [...name].reduce((n, c) => n + c.charCodeAt(0), 0) % 360;
  return `<svg xmlns="http://www.w3.org/2000/svg" width="800" height="600"><defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="hsl(${hue},70%,68%)"/><stop offset="1" stop-color="hsl(${(hue + 40) % 360},45%,28%)"/></linearGradient></defs><rect width="800" height="600" fill="url(#g)"/></svg>`;
};
async function shot(context, url, step) {
  const page = await context.newPage();
  // The synthetic photo addresses do not resolve; serve a picture for each.
  await page.route("https://photos.example.invalid/**", (route) =>
    route.fulfill({
      contentType: "image/svg+xml",
      body: swatch(route.request().url()),
    }),
  );
  await page.goto(url, { waitUntil: "networkidle" });
  if (step) await step(page);
  const image = await page.screenshot({
    fullPage: true,
    type: "jpeg",
    quality: 82,
  });
  await page.close();
  return image;
}
const side = async (browser, size, left, right) => {
  const page = await browser.newPage({
    viewport: { width: size[0] * 2 + 60, height: 800 },
  });
  const src = (buffer) => `data:image/jpeg;base64,${buffer.toString("base64")}`;
  await page.setContent(
    `<body style="margin:0;background:#dfe5e1;display:flex;gap:20px;padding:20px;align-items:flex-start;font:600 14px sans-serif">
      <figure style="margin:0"><figcaption style="padding:0 0 8px">Reference</figcaption><img style="width:${size[0]}px;display:block" src="${src(left)}"></figure>
      <figure style="margin:0"><figcaption style="padding:0 0 8px">Console</figcaption><img style="width:${size[0]}px;display:block" src="${src(right)}"></figure>
    </body>`,
  );
  const image = await page.screenshot({
    fullPage: true,
    type: "jpeg",
    quality: 82,
  });
  await page.close();
  return image;
};
const activeScreens =
  stepName === "dashboard-gbp-actions"
    ? dashboardScreens
    : stepName === "step-5b"
      ? contentScreens
      : stepName === "step-5a"
        ? websiteScreens
        : stepName === "step-6"
          ? reviewScreens
          : stepName === "special-hours-publish"
            ? screens.filter(([name]) => name === "special-hours-list")
            : screens;
await mkdir(out, { recursive: true });
const browser = await chromium.launch(
  process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
    ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE }
    : {},
);
await fetch(`${consoleUrl.replace("4346", "4455")}/test/gbp-reset`, {
  method: "POST",
  body: "{}",
}).catch(() => undefined);
for (const [label, [width, height]] of Object.entries(sizes)) {
  const viewport = { width, height };
  const contexts = {};
  for (const who of ["a", "b", "admin"]) {
    contexts[who] = await browser.newContext({ viewport });
    await signIn(contexts[who], who);
  }
  const plain = await browser.newContext({ viewport });
  for (const [
    name,
    who,
    path,
    refPath,
    step,
    prepare,
    refStep,
  ] of activeScreens) {
    await (prepare ?? reset)();
    const right = await shot(contexts[who], consoleUrl + path, step);
    const left = await shot(plain, reference + refPath, refStep);
    const combined = await side(browser, [width, height], left, right);
    await writeFile(
      new URL(`${name}-${label}-reference-left-console-right.jpg`, out),
      combined,
    );
    console.log(`${name} ${label}`);
  }
  await plain.close();
  for (const context of Object.values(contexts)) await context.close();
}
await browser.close();
