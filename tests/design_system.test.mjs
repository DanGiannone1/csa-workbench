import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { extname, join } from "node:path";
import test from "node:test";

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf8");

function productionSources(directory) {
  const root = new URL(directory, import.meta.url);
  return readdirSync(root, { recursive: true, withFileTypes: true })
    .filter((entry) => entry.isFile() && [".css", ".tsx"].includes(extname(entry.name)))
    .map((entry) => {
      const path = join(entry.parentPath, entry.name);
      return { path, source: readFileSync(path, "utf8") };
    });
}

test("production CSS uses design tokens and excludes prototype effects", () => {
  const css = read("../frontend/src/app/globals.css");
  const tokens = read("../design-system/src/tokens.css");
  assert.match(css, /@import "\.\.\/\.\.\/\.\.\/design-system\/src\/tokens\.css"/);
  for (const token of ["app-bg", "brand-primary", "status-done", "text-primary"]) {
    assert.equal((css.match(new RegExp(`--${token}:`, "g")) ?? []).length, 0, token);
    assert.match(tokens, new RegExp(`--${token}:`));
  }
  assert.doesNotMatch(css, /#[0-9A-Fa-f]{3,8}\b|rgba?\(/);
  assert.doesNotMatch(css, /linear-gradient|radial-gradient|backdrop-filter/);
  assert.doesNotMatch(css, /reference\/claude-design|support\.js|\.dc\.html/);
});

test("all production component and stylesheet sources exclude retired visual syntax", () => {
  const paletteUtility = /\b(?:bg|text|border|ring|outline|fill|stroke|from|via|to)-(?:white|black|slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)(?:-\d{2,3})?(?:\/\d+)?\b/i;
  const invalidTokenUtility = /\b(?:bg|text|border|from|to|ring|placeholder)-var\(/i;
  const arbitraryVisualUtility = /\b(?:shadow|rounded)-\[[^\]]+\]|\b(?:bg|text|border|ring|outline|fill|stroke)-\[(?:#|rgba?\(|hsla?\(|oklch\(|var\()[^\]]*\]/i;

  for (const { path, source } of productionSources("../frontend/src/")) {
    assert.doesNotMatch(source, /#[0-9A-Fa-f]{3,8}\b|rgba?\(/, path);
    assert.doesNotMatch(source, /(?:linear|radial|conic)-gradient|backdrop-filter|backdrop-(?:blur|filter)/i, path);
    assert.doesNotMatch(source, invalidTokenUtility, path);
    if (path.endsWith(".tsx")) {
      assert.doesNotMatch(source, paletteUtility, path);
      assert.doesNotMatch(source, arbitraryVisualUtility, path);
    }
  }
});

test("semantic React primitives are used by production surfaces", () => {
  const sources = productionSources("../frontend/src/")
    .filter(({ path }) => !path.includes(`${join("components", "ui")}${join("", "")}`))
    .map(({ source }) => source)
    .join("\n");
  for (const component of ["Button", "Dialog", "Drawer", "Field", "Overlay", "Status", "Surface", "Tabs", "Toast"]) {
    assert.match(sources, new RegExp(`(?:components/ui|\\./ui)/${component}`), `${component} is not used`);
  }
});

test("frontend image builds from the repository root without reference assets", () => {
  const dockerfile = read("../frontend/Dockerfile");
  const deploy = read("../infra/deploy.py");
  const dockerignore = read("../.dockerignore");
  const nextConfig = read("../frontend/next.config.ts");

  assert.match(dockerfile, /COPY frontend\/package\.json frontend\/package-lock\.json\* \.\//);
  assert.match(dockerfile, /COPY frontend\/ \.\//);
  assert.match(dockerfile, /COPY design-system\/package\.json \/app\/design-system\/package\.json/);
  assert.match(dockerfile, /COPY design-system\/src\/ \/app\/design-system\/src\//);
  assert.doesNotMatch(dockerfile, /COPY design-system\/reference/);
  assert.match(dockerfile, /COPY --from=build --chown=nextjs:nodejs \/app\/frontend\/\.next\/standalone \.\//);
  assert.match(dockerfile, /WORKDIR \/app\/frontend\s+USER nextjs[\s\S]*CMD \["node", "server\.js"\]/);
  assert.match(deploy, /"-f", "frontend\/Dockerfile", "\."/);
  assert.doesNotMatch(dockerignore, /^frontend$/m);
  assert.match(dockerignore, /^design-system\/reference$/m);
  assert.match(nextConfig, /outputFileTracingRoot: path\.resolve\(__dirname, "\.\."\)/);
});
