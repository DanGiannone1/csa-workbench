import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf8");

test("production CSS has one token authority and no prototype effects", () => {
  const css = read("../frontend/src/app/globals.css");
  const tokens = read("../design-system/src/tokens.css");
  assert.match(css, /@import "\.\.\/\.\.\/\.\.\/design-system\/src\/tokens\.css"/);
  for (const token of ["app-bg", "brand-primary", "status-done", "text-primary"]) {
    assert.equal((css.match(new RegExp(`--${token}:`, "g")) ?? []).length, 0, token);
    assert.match(tokens, new RegExp(`--${token}:`));
  }
  assert.doesNotMatch(css, /linear-gradient|radial-gradient|backdrop-filter/);
  assert.doesNotMatch(css, /reference\/claude-design|support\.js|\.dc\.html/);
});
