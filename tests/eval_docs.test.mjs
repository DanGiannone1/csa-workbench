import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf8");

test("beginner eval guide keeps the client view and links the advanced paths", () => {
  const guide = read("./evals/README.md");
  for (const phrase of [
    "Input prompt", "Expected output", "ACME-3-meeting-prep", "ACME-4-boundary",
    "ACME-5-full-conversation", "Plain-English glossary", "Waza",
  ]) assert.ok(guide.includes(phrase), `missing ${phrase}`);
  assert.match(guide, /gold-dataset-authoring\.md/);
  assert.match(guide, /waza-skill-evals\.md/);
});

test("Waza advisory suites cover every remaining shipped product skill", () => {
  const directTask = {
    tasks: "direct-create.yaml",
    calendar: "direct-create.yaml",
    "weekly-review": "full-review.yaml",
  };
  for (const skill of Object.keys(directTask)) {
    const suite = read(`./evals/waza/${skill}/eval.yaml`);
    const task = read(`./evals/waza/${skill}/tasks/${directTask[skill]}`);
    assert.match(suite, new RegExp(`skill: ${skill}`));
    assert.match(task, /tags: \[advisory, routing/);
    assert.match(task, /type: skill_invocation/);
    assert.match(task, /type: tool_constraint/);
  }
  const runner = read("../scripts/waza_eval.sh");
  assert.match(runner, /for skill in tasks calendar weekly-review/);
  assert.match(runner, /run_eval advisory/);
});

test("technical references keep Waza separate from product-runtime evidence", () => {
  const waza = read("../testing/waza-skill-evals.md");
  assert.match(waza, /does \*\*not\*\* run the CSA Workbench Deep Agents product runtime/);
  assert.match(waza, /does\n+not currently support native Windows/);
  const engineering = read("../testing/gold-dataset-authoring.md");
  assert.match(engineering, /fixtureVersion/);
  assert.match(engineering, /safeNonExecution/);
  assert.match(engineering, /pass@k/);
});
