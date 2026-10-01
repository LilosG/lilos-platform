import { readdir, readFile } from "node:fs/promises";
import { resolve, dirname } from "node:path";
async function walk(directory) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = resolve(directory, entry.name);
    if (entry.isDirectory()) await walk(path);
    else if (/\.(ts|astro|js|mjs)$/.test(path)) {
      const content = await readFile(path, "utf8");
      const imports = [
        ...content.matchAll(
          /(?:from\s*|import\s*\(|import\s*)["']([^"']+)["']/g,
        ),
      ].map((match) => match[1]);
      for (const specifier of imports) {
        const target = specifier.startsWith(".")
          ? resolve(dirname(path), specifier)
          : specifier;
        if (
          /(?:fixtures|sample-session|prototype|reference)(?:\/|\.|$)/.test(
            target,
          )
        )
          throw new Error(`Production fixture import: ${path}`);
      }
      if (/localStorage|sessionStorage|createBrowserClient/.test(content))
        throw new Error(`Browser authority in ${path}`);
    }
  }
}
await walk(process.argv[2] ?? new URL("../src", import.meta.url).pathname);
console.log("Production fixture/session boundaries pass");
