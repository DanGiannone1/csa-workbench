import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf8");

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

test("frontend image builds from the repository root without reference assets", () => {
  const dockerfile = read("../frontend/Dockerfile");
  const deploy = read("../infra/deploy.sh");
  const dockerignore = read("../.dockerignore");
  const nextConfig = read("../frontend/next.config.ts");

  assert.match(dockerfile, /COPY frontend\/package\.json frontend\/package-lock\.json\* \.\//);
  assert.match(dockerfile, /COPY frontend\/ \.\//);
  assert.match(dockerfile, /COPY design-system\/package\.json \/app\/design-system\/package\.json/);
  assert.match(dockerfile, /COPY design-system\/src\/ \/app\/design-system\/src\//);
  assert.doesNotMatch(dockerfile, /COPY design-system\/reference/);
  assert.match(dockerfile, /COPY --from=build --chown=nextjs:nodejs \/app\/frontend\/\.next\/standalone \.\//);
  assert.match(dockerfile, /WORKDIR \/app\/frontend\s+USER nextjs[\s\S]*CMD \["node", "server\.js"\]/);
  assert.match(deploy, /-f frontend\/Dockerfile \. --build-arg/);
  assert.doesNotMatch(dockerignore, /^frontend$/m);
  assert.match(dockerignore, /^design-system\/reference$/m);
  assert.match(nextConfig, /outputFileTracingRoot: path\.resolve\(__dirname, "\.\."\)/);
});
