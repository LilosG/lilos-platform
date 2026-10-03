#!/usr/bin/env node
// Fails on any high or critical npm advisory that is not listed, unexpired, in
// security/npm-audit-exceptions.json. An expired exception fails the gate.
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const EXCEPTIONS_PATH = fileURLToPath(
  new URL("../security/npm-audit-exceptions.json", import.meta.url),
);
const BLOCKING = new Set(["high", "critical"]);

function loadExceptions(now) {
  const { exceptions } = JSON.parse(readFileSync(EXCEPTIONS_PATH, "utf8"));
  const problems = [];
  const active = new Map();
  for (const entry of exceptions) {
    const missing = ["ghsa", "package", "reason", "expires"].filter(
      (key) => typeof entry[key] !== "string" || entry[key].trim() === "",
    );
    if (missing.length > 0) {
      problems.push(
        `Exception ${entry.ghsa ?? "(no id)"} is missing: ${missing.join(", ")}`,
      );
      continue;
    }
    const expires = new Date(`${entry.expires}T23:59:59Z`);
    if (Number.isNaN(expires.getTime())) {
      problems.push(`Exception ${entry.ghsa} has an invalid expires date`);
    } else if (expires < now) {
      problems.push(
        `Exception ${entry.ghsa} (${entry.package}) expired on ${entry.expires}`,
      );
    } else {
      active.set(entry.ghsa, entry);
    }
  }
  return { active, problems };
}

const audit = spawnSync("npm", ["audit", "--json"], {
  encoding: "utf8",
  maxBuffer: 64 * 1024 * 1024,
});
let report;
try {
  report = JSON.parse(audit.stdout);
} catch {
  console.error("npm audit did not return JSON:", audit.stderr || audit.stdout);
  process.exit(2);
}
if (report.error) {
  console.error("npm audit failed:", report.error.summary ?? report.error);
  process.exit(2);
}

// Advisories are the object entries in `via`; string entries only name a dependency
// that is affected through another package, so they add nothing new.
const advisories = new Map();
for (const vulnerability of Object.values(report.vulnerabilities ?? {})) {
  for (const via of vulnerability.via) {
    if (typeof via !== "object" || !BLOCKING.has(via.severity)) continue;
    const ghsa = via.url?.split("/").pop() ?? String(via.source);
    advisories.set(ghsa, via);
  }
}

const { active, problems } = loadExceptions(new Date());
const failures = [...problems];
for (const [ghsa, via] of advisories) {
  if (active.has(ghsa)) {
    console.log(
      `Allowed ${ghsa} (${via.name}, ${via.severity}) until ${active.get(ghsa).expires}`,
    );
  } else {
    failures.push(`${ghsa} ${via.name} (${via.severity}): ${via.title}`);
  }
}

if (failures.length > 0) {
  console.error("npm audit gate failed:");
  for (const failure of failures) console.error(`  - ${failure}`);
  process.exit(1);
}
console.log("npm audit gate passed.");
