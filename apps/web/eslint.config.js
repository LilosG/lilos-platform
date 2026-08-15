import eslint from "@eslint/js";
import { defineConfig, globalIgnores } from "eslint/config";
import astro from "eslint-plugin-astro";
import tseslint from "typescript-eslint";

export default defineConfig(
  globalIgnores([".astro/", "coverage/", "dist/"]),
  eslint.configs.recommended,
  tseslint.configs.recommended,
  astro.configs["flat/recommended"],
  {
    files: ["**/*.astro"],
    rules: {
      "no-restricted-syntax": [
        "error",
        {
          selector: "JSXAttribute[name.name='style']",
          message:
            "Inline style attributes bypass design-system tokens and primitives.",
        },
      ],
    },
  },
);
