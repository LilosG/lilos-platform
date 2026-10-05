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
const step = process.argv[2] ?? "step-4b";
const out = new URL(`../visual/${step}/`, import.meta.url);
const sizes = { desktop: [1440, 1000], mobile: [390, 844] };
const gbp = "/clients/synthetic-beta/local-search/google-business-profile/";
const coco = "/clients/coco-maya/local-search/";
const open = (name) => async (page) => {
  await page.getByRole("button", { name, exact: true }).first().click();
  await page.locator("dialog[open]").waitFor();
};
// Each screen: the console route, the user to sign in as, the nearest reference route, and
// an optional step that opens a dialog before the capture.
const screens = [
  ["local-search-overview", "b", "/clients/synthetic-beta/local-search/", coco],
  ["gbp-performance", "b", gbp, `${coco}google-business-profile/`],
  ["gbp-posts", "b", `${gbp}?view=posts`, `${coco}google-business-profile/`],
  [
    "gbp-post-dialog",
    "b",
    `${gbp}?view=posts`,
    `${coco}google-business-profile/`,
    open("New post"),
  ],
  ["gbp-photos", "b", `${gbp}?view=photos`, `${coco}google-business-profile/`],
  [
    "gbp-special-hours",
    "b",
    `${gbp}?view=special-hours`,
    `${coco}google-business-profile/`,
  ],
  [
    "gbp-profile",
    "b",
    `${gbp}?view=profile`,
    `${coco}google-business-profile/`,
  ],
  [
    "gbp-profile-dialog",
    "b",
    `${gbp}?view=profile`,
    `${coco}google-business-profile/`,
    open("Edit details"),
  ],
  [
    "search-console",
    "b",
    "/clients/synthetic-beta/local-search/search-console/",
    `${coco}search-console/`,
  ],
  [
    "rankings",
    "b",
    "/clients/synthetic-beta/local-search/rankings/",
    `${coco}rankings/`,
  ],
  ["client-overview", "a", "/clients/synthetic-alpha/", "/clients/coco-maya/"],
];
async function signIn(context, who) {
  const page = await context.newPage();
  await page.goto(`${consoleUrl}/login/`);
  await page.getByLabel("Email", { exact: true }).fill(`${who}@example.test`);
  await page.getByLabel("Password", { exact: true }).fill("synthetic-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.waitForURL((url) => !url.pathname.startsWith("/login"));
  await page.close();
}
async function shot(context, url, step) {
  const page = await context.newPage();
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
await mkdir(out, { recursive: true });
const browser = await chromium.launch();
await fetch(`${consoleUrl.replace("4346", "4455")}/test/gbp-reset`, {
  method: "POST",
  body: "{}",
}).catch(() => undefined);
for (const [label, [width, height]] of Object.entries(sizes)) {
  const viewport = { width, height };
  const contexts = {};
  for (const who of ["a", "b"]) {
    contexts[who] = await browser.newContext({ viewport });
    await signIn(contexts[who], who);
  }
  const plain = await browser.newContext({ viewport });
  for (const [name, who, path, refPath, step] of screens) {
    const right = await shot(contexts[who], consoleUrl + path, step);
    const left = await shot(plain, reference + refPath, undefined);
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
