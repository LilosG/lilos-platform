import { it, expect } from "vitest";
import { mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
it.each([
  "import {sample} from '../data/fixtures/clients';",
  "export * from '../reference/sample-session';",
  "const x=import('../data/fixtures/all');",
  "localStorage.setItem('role','owner');",
])("blocks production fixture and browser authority violations", (source) => {
  const root = mkdtempSync(join(tmpdir(), "console-boundary-"));
  try {
    writeFileSync(join(root, "loader.ts"), source);
    const result = spawnSync(
      process.execPath,
      [resolve("scripts/check-boundaries.mjs"), root],
      { encoding: "utf8" },
    );
    expect(result.status).not.toBe(0);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});
