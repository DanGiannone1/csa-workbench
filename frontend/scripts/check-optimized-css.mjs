import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

const distDir = process.env.NEXT_DIST_DIR || ".next";
const cssRoot = join(process.cwd(), distDir, "static");
assert.ok(existsSync(cssRoot), `optimized CSS directory is missing: ${cssRoot}`);

const cssFiles = readdirSync(cssRoot, { recursive: true })
  .filter((entry) => typeof entry === "string" && entry.endsWith(".css"));
assert.ok(cssFiles.length > 0, "production build emitted no optimized CSS");

const css = cssFiles.map((entry) => readFileSync(join(cssRoot, entry), "utf8")).join("\n");
const forbidden = [
  [/(?:linear|radial|conic)-gradient/i, "gradient"],
  [/(?:^|[;{])(?:-webkit-)?backdrop-filter\s*:/i, "backdrop filter"],
  [/#0073ea\b/i, "retired blue palette"],
  [/\.(?:bg|text|border|ring|outline|fill|stroke|from|via|to)-(?:white|black|slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)(?:-\d{2,3})?(?:\\\/\d+)?\b/i, "hard-coded palette utility"],
  [/\.(?:bg|text|border|from|to|ring|placeholder)-var\\\(/i, "invalid token utility"],
];

for (const [pattern, label] of forbidden) {
  assert.doesNotMatch(css, pattern, `optimized CSS contains ${label}`);
}

console.log(`Checked ${cssFiles.length} optimized CSS file(s).`);
