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
  assert.match(guide, /skill-evals\.md/);
  const cases = JSON.parse(read("./evals/mvp-cases.json")).cases;
  const workflows = JSON.parse(read("./evals/mvp-workflows.json")).workflows;
  for (const id of ["ACME-3-meeting-prep", "ACME-4-boundary"]) {
    assert.ok(guide.includes(cases.find((entry) => entry.id === id).clientExpectedOutput));
  }
  for (const turn of workflows.find((entry) => entry.id === "ACME-5-full-conversation").turns) {
    assert.ok(guide.includes(turn.clientExpectedOutput));
  }
  assert.doesNotMatch(guide, /right account|cannot access the Engagement/i);
  assert.match(guide, /without confirming whether the named Engagement exists/);
});

test("every executable gold fixture carries the client expected-output bridge", () => {
  const cases = JSON.parse(read("./evals/mvp-cases.json"));
  const workflows = JSON.parse(read("./evals/mvp-workflows.json"));
  for (const item of [...cases.cases, ...workflows.workflows.flatMap((workflow) => workflow.turns)]) {
    assert.equal(typeof item.clientExpectedOutput, "string");
    assert.ok(item.clientExpectedOutput.trim());
  }
  const showcase = read("../scripts/eval_showcase.mjs");
  assert.match(showcase, /clientExpectedOutput: definition\.clientExpectedOutput/);
  assert.match(showcase, /Expected output/);
  assert.match(showcase, /Actual output/);
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
    assert.match(suite, /^metrics:/m);
    assert.match(suite, /routing and tool-selection probes/);
    assert.match(task, /tags: \[advisory, routing/);
    assert.match(task, /type: skill_invocation/);
    assert.match(task, /type: tool_constraint/);
  }
  const runner = read("../scripts/workbench.py");
  for (const skill of ["engagement-meeting-prep", "tasks", "calendar", "weekly-review"]) {
    assert.match(runner, new RegExp(`WazaSuite\\("${skill}", "advisory"\\)`));
  }
  assert.ok(!runner.includes('"gate"'), "the Waza runner must not define a gate lane or action");
});

test("the skill-evaluation guide states the real test and keeps Waza laboratory-only", () => {
  const waza = read("../testing/skill-evals.md");
  assert.match(waza, /does \*\*not\*\* run the CSA Workbench Deep Agents product runtime/);
  for (const phrase of [
    "The real test: with the skill, then without", "What Waza is — and is not",
    "Setup and authentication", "Mocks and task anatomy", "Starter suites and building your own",
    "Commands by operating system", "Evidence and a worked interpretation", "Repeated trials",
    "Linux Bash", "macOS Terminal", "Windows PowerShell", "prefer WSL", "CSA_WAZA_TRIALS=5",
    "never gate anything",
  ]) assert.ok(waza.includes(phrase), `missing skill-evals guide section or statement: ${phrase}`);
  assert.match(waza, /github\.com\/microsoft\/waza\/blob\/v0\.38\.3\/schemas\/eval\.schema\.json/);
  assert.match(waza, /GITHUB_TOKEN/);
  const engineering = read("../testing/gold-dataset-authoring.md");
  assert.match(engineering, /fixtureVersion/);
  assert.match(engineering, /safeNonExecution/);
  assert.match(engineering, /pass@k/);
});

test("the complete gold example is executable fixture data rather than copied prose", () => {
  const engineering = read("../testing/gold-dataset-authoring.md");
  const match = engineering.match(/<!-- validated-example:ACME-2-update-status:start -->\s*```json\s*([\s\S]*?)\s*```\s*<!-- validated-example:ACME-2-update-status:end -->/);
  assert.ok(match, "missing validated ACME-2 example");
  const example = JSON.parse(match[1]);
  const fixture = JSON.parse(read("./evals/mvp-cases.json")).cases.find((entry) => entry.id === example.id);
  assert.deepEqual(example, fixture);
});

test("the gold reference names every expectation field consumed by the grader", () => {
  const grader = read("../scripts/mvp_evidence.mjs");
  const engineering = read("../testing/gold-dataset-authoring.md");
  const fields = [...new Set([...grader.matchAll(/expectation\.([A-Za-z][A-Za-z0-9]*)/g)].map((match) => match[1]))].sort();
  assert.ok(fields.length >= 20, "grader field discovery unexpectedly found too few fields");
  for (const field of fields) assert.ok(engineering.includes(`\`${field}\``), `gold reference omits expectation.${field}`);
  for (const workflowField of ["description", "skillName", "groundingTurn", "turns", "finalEngagement"]) {
    assert.ok(engineering.includes(`\`${workflowField}\``), `gold reference omits workflow.${workflowField}`);
  }
});

test("the deterministic Waza validator pins official schemas by URL and digest", () => {
  const validator = read("../scripts/waza_spec_validation.mjs");
  assert.match(validator, /microsoft\/waza\/v0\.38\.3\/schemas\/eval\.schema\.json/);
  assert.match(validator, /microsoft\/waza\/v0\.38\.3\/schemas\/task\.schema\.json/);
  assert.match(validator, /sha256: "[a-f0-9]{64}"/);
  assert.match(read("../scripts/workbench.py"), /"npm", "run", "eval:waza:validate"/);
});
