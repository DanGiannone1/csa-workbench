import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, readFileSync, realpathSync, rmSync, symlinkSync, utimesSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import {
  REPOSITORY_ROOT,
  buildShowcaseModel,
  describeRecordedResults,
  describeExpectedState,
  explainObservedFailures,
  findEvidenceCandidates,
  findLatestEvidence,
  parseWazaTask,
  projectProductSkill,
  programMetrics,
  renderShowcaseHtml,
} from "../scripts/eval_showcase.mjs";
import { createShowcaseServer, parseShowcaseArgs } from "../scripts/eval_showcase_server.mjs";

const htmlEscape = (value) => value
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")
  .replaceAll("'", "&#39;");

test("Waza task parsing exposes prompt, routing, and tool constraints without transcript content", () => {
  const source = `id: WAZA-1\nname: Direct trigger\ndescription: Route correctly.\ntags: [gate, routing]\ninputs:\n  prompt: Prep me for Product Launch.\ngraders:\n  - type: skill_invocation\n    config:\n      required_skills: [engagement-meeting-prep]\n  - type: tool_constraint\n    config:\n      expect_tools:\n        - { tool: ".*list_engagements$" }\n      reject_tools:\n        - { tool: ".*update_engagement$" }\n`;
  assert.deepEqual(parseWazaTask(source), {
    id: "WAZA-1",
    name: "Direct trigger",
    description: "Route correctly.",
    tags: ["gate", "routing"],
    prompt: "Prep me for Product Launch.",
    expectedTools: [".*list_engagements$"],
    rejectedTools: [".*update_engagement$"],
    requiredSkills: ["engagement-meeting-prep"],
    forbiddenSkills: [],
  });
});

test("Waza task parsing consumes the checked-in inline and block YAML shapes", () => {
  const cases = [
    ["../tests/evals/waza/tasks/tasks/direct-create.yaml", [".*create_task$"], [".*create_event$"], ["tasks"]],
    ["../tests/evals/waza/calendar/tasks/direct-create.yaml", [".*create_event$"], [".*create_task$"], ["calendar"]],
    ["../tests/evals/waza/weekly-review/tasks/full-review.yaml", [".*list_tasks$", ".*update_task$", ".*list_events$", ".*create_event$"], [".*create_task$"], ["weekly-review"]],
  ];
  for (const [relativePath, expectedTools, rejectedTools, requiredSkills] of cases) {
    const task = parseWazaTask(readFileSync(new URL(relativePath, import.meta.url), "utf8"));
    assert.deepEqual(task.expectedTools, expectedTools);
    assert.deepEqual(task.rejectedTools, rejectedTools);
    assert.deepEqual(task.requiredSkills, requiredSkills);
  }
});

test("latest evidence discovery chooses the newest matching artifact and ignores unrelated files", () => {
  const root = mkdtempSync(join(tmpdir(), "csa-showcase-latest-"));
  try {
    mkdirSync(join(root, "evidence", "old"), { recursive: true });
    mkdirSync(join(root, "evidence", "new"), { recursive: true });
    writeFileSync(join(root, "evidence", "old", "results.json"), "{}\n");
    const old = new Date(Date.now() - 20_000);
    const oldPath = join(root, "evidence", "old", "results.json");
    utimesSync(oldPath, old, old);
    writeFileSync(join(root, "evidence", "new", "results.json"), "{}\n");
    writeFileSync(join(root, "evidence", "new", "ignore.txt"), "ignored\n");
    assert.equal(
      realpathSync(findLatestEvidence(root, "evidence", "results.json")),
      realpathSync(join(root, "evidence", "new", "results.json")),
    );
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("automatic discovery rejects product and Waza evidence symlinks that escape their roots", () => {
  const root = mkdtempSync(join(tmpdir(), "csa-showcase-symlink-discovery-"));
  try {
    for (const [evidenceRoot, filename] of [["product", "results.json"], ["waza", "waza.json"]]) {
      const allowed = join(root, evidenceRoot);
      const run = join(allowed, "run");
      const outside = join(root, "outside", evidenceRoot);
      mkdirSync(run, { recursive: true });
      mkdirSync(outside, { recursive: true });
      const target = join(outside, filename);
      writeFileSync(target, "{}\n");
      symlinkSync(target, join(run, filename));
      assert.deepEqual(findEvidenceCandidates(root, evidenceRoot, filename), []);
    }
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("the repository model renders both evaluation lanes and presenter guidance without local evidence", () => {
  const model = buildShowcaseModel({ revision: "test-revision", discoverEvidence: false });
  assert.equal(model.product.available, false);
  assert.equal(model.product.tasks.length, 10);
  assert.equal(model.product.workflows.length, 1);
  assert.equal(model.waza.available, false);
  assert.equal(model.waza.tasks.length, 6);
  assert.equal(model.methodology.length, 4);
  assert.equal(model.programMetrics.length, 6);
  assert.deepEqual(model.programMetrics.map((metric) => metric.name), [
    "Capability", "Trustworthiness", "Safety", "Consistency", "Performance", "Change impact",
  ]);
  assert.ok(model.risks.some((risk) => risk.includes("one trial")));

  const html = renderShowcaseHtml(model);
  assert.match(html, /Can we trust the assistant to do the right thing/);
  assert.match(html, /Test the assistant like a new teammate/);
  assert.match(html, /Demo 1 · one focused skill/);
  assert.match(html, /Demo 2 · the whole assistant/);
  assert.match(html, /What good looks like/);
  assert.match(html, /what the assistant did/i);
  assert.match(html, /Optional details for a technical audience/);
  assert.match(html, /Progress against the six target measures/);
  assert.match(html, /we do not display or grade hidden reasoning/);
  assert.match(html, /Simple ten-minute talk track/);
  assert.match(html, /Waza evidence \/ engine unavailable/);
  assert.match(html, /Focused laboratory—not the full product runtime/);
  assert.doesNotMatch(html, /AZURE_ENDPOINT|DEMO_PASSWORD|COSMOS_KEY/);
  assert.doesNotMatch(html, /system\.message/);
  assert.match(html, /No recorded test result is loaded yet/);
  assert.match(html, /Fixture-only review/);
  assert.match(html, /Expected output/);
  assert.match(html, /Actual output/);
  assert.equal((html.match(/Actual output/g) ?? []).length, 14, "every atomic case and workflow turn needs an actual-output slot");
  assert.equal((html.match(/Optional technical evidence/g) ?? []).length, 14, "technical evidence should be drill-down for every client example");
  const atomicDefinitions = JSON.parse(readFileSync(new URL("./evals/mvp-cases.json", import.meta.url), "utf8"));
  const workflowDefinitions = JSON.parse(readFileSync(new URL("./evals/mvp-workflows.json", import.meta.url), "utf8"));
  for (const definition of atomicDefinitions.cases) assert.ok(html.includes(htmlEscape(definition.clientExpectedOutput)));
  for (const turn of workflowDefinitions.workflows.flatMap((workflow) => workflow.turns)) {
    assert.ok(html.includes(htmlEscape(turn.clientExpectedOutput)));
  }
  assert.doesNotMatch(html, /focused skill passed; the full journey exposed a miss/i);
});

test("stale passing evidence is described as a selected recorded run, never as current behavior", () => {
  const staleWaza = {
    available: true,
    sourceMatchesCurrent: false,
    skillMatchesCurrent: false,
    summary: { succeeded: 2, total_tests: 2 },
  };
  const focused = describeRecordedResults({ available: false }, staleWaza);
  assert.equal(focused.focusedHeadline, "The selected focused run passed.");
  assert.doesNotMatch(focused.focusedHeadline, /works|today/i);

  const staleProduct = { available: true, sourceMatchesCurrent: false, hardGatePass: true };
  const product = describeRecordedResults(staleProduct, { available: false });
  assert.equal(product.fullHeadline, "The selected full-product run passed its required checks.");
  assert.doesNotMatch(product.fullHeadline, /assistant passed today|works/i);
});

test("all-pass rendering keeps result, talk track, provenance, contracts, and raw evidence truthful", () => {
  const model = buildShowcaseModel({ revision: "current-revision", discoverEvidence: false });
  model.waza = {
    ...model.waza,
    available: true,
    sourceMatchesCurrent: false,
    skillMatchesCurrent: false,
    sourceClean: true,
    engine: "custom-engine",
    model: "focused-model",
    tag: "gate",
    summary: { succeeded: model.waza.tasks.length, total_tests: model.waza.tasks.length, aggregate_score: 1 },
    tasks: model.waza.tasks.map((task) => ({
      ...task,
      transcript: [{ type: "system.message", content: "RAW_TRANSCRIPT_MARKER" }],
      observed: {
        pass: true,
        status: "passed",
        durationMs: 1,
        tools: [],
        skills: [],
        validationFeedback: [],
        reasoning: "RAW_REASONING_MARKER",
      },
    })),
  };
  model.product = {
    ...model.product,
    available: true,
    hardGatePass: true,
    sourceMatchesCurrent: false,
    harness: "custom-harness",
    model: "product-model",
    atomic: { passed: 1, total: 1, failed: [] },
    workflowsSummary: { passed: 1, total: 1, failed: [] },
    checks: { passed: 2, total: 2 },
    scope: "all",
    groundingReview: "MATCHED",
    groundingReviews: [],
    acceptance: { status: "COMPLETE", baseline: "ACCEPTED" },
    skill: { name: "meeting-prep", version: "1.2.3", sha256: "abc123" },
    tasks: [{
      id: "test-task",
      actor: "member-a",
      prompt: "Test the contract",
      kind: "regression",
      gold: {
        referenceTools: [],
        referenceArguments: null,
        forbiddenTools: [],
        requiredSkill: null,
        forbiddenSkills: ["meeting-prep"],
        expectedState: [],
        judgeQuestions: [],
      },
      observed: null,
    }],
    workflows: [],
  };
  const html = renderShowcaseHtml(model);
  assert.match(html, /Both selected recorded runs passed/);
  assert.match(html, /the selected focused run passed; the selected full-product run passed/);
  assert.doesNotMatch(html, /full journey exposed a miss/i);
  assert.match(html, /Waza evidence \/ custom-engine/);
  assert.match(html, /custom-harness\/product-model/);
  assert.match(html, /Skill meeting-prep v1\.2\.3 · abc123/);
  assert.match(html, /Instruction sets it must not load/);
  assert.doesNotMatch(html, /RAW_TRANSCRIPT_MARKER|RAW_REASONING_MARKER|system\.message/);
  assert.match(html, /we do not display or grade hidden reasoning/);
});

test("workflow-only evidence reports safety as not run instead of zero failures", () => {
  const metrics = programMetrics({
    available: true,
    tasks: [
      { kind: "safety", observed: null },
      { kind: "safety", observed: null },
      { kind: "regression", observed: null },
    ],
    acceptance: { baseline: "NOT_ACCEPTED" },
  });
  const safety = metrics.find((metric) => metric.name === "Safety");
  assert.deepEqual({ value: safety.value, tone: safety.tone }, { value: "NOT RUN", tone: "warn" });
});

test("product evidence retains the exact skill name, version, and hash", () => {
  assert.deepEqual(projectProductSkill({
    name: "engagement-meeting-prep",
    version: "1.0.0",
    path: "backend/assistant/product-skills/engagement-meeting-prep/SKILL.md",
    sha256: "f27459ac7c7377b5f53d6fe889080967a62e40d4d4430764f51c8419a046348c",
    ignoredExtraField: "not presenter-visible",
  }), {
    name: "engagement-meeting-prep",
    version: "1.0.0",
    sha256: "f27459ac7c7377b5f53d6fe889080967a62e40d4d4430764f51c8419a046348c",
  });
  assert.equal(projectProductSkill(null), null);
});

test("safe alternatives are described without contradicting the primary expected result", () => {
  assert.ok(describeExpectedState({
    operation: "update",
    status: "not_found",
    stateChanged: false,
    safeNonExecution: { allowedResultAlternatives: [] },
  }).includes("either structured result update / not_found, or safe non-execution without changing state"));
});

test("showcase rejects pinned evidence outside its evidence roots", () => {
  assert.throws(
    () => buildShowcaseModel({ productPath: "package.json" }),
    /Evidence must be a results\.json file under evidence\/mvp\/local-synthetic\/agent-evals/,
  );
});

test("showcase rejects a pinned evidence symlink that resolves outside its evidence root", () => {
  const name = `zz-showcase-symlink-${process.pid}`;
  const testRoot = join(REPOSITORY_ROOT, "evidence", "mvp", "local-synthetic", "agent-evals", name);
  try {
    mkdirSync(testRoot, { recursive: true });
    symlinkSync(join(REPOSITORY_ROOT, "package.json"), join(testRoot, "results.json"));
    assert.throws(
      () => buildShowcaseModel({ productPath: `evidence/mvp/local-synthetic/agent-evals/${name}/results.json` }),
      /Evidence must be a results\.json file under evidence\/mvp\/local-synthetic\/agent-evals/,
    );
  } finally {
    rmSync(testRoot, { recursive: true, force: true });
  }
});

test("invalid evidence is rejected when pinned and skipped during automatic discovery", () => {
  const name = `zz-showcase-invalid-${process.pid}`;
  const testRoot = join(REPOSITORY_ROOT, "evidence", "mvp", "local-synthetic", "agent-evals", name);
  try {
    mkdirSync(testRoot, { recursive: true });
    const malformed = join(testRoot, "results.json");
    writeFileSync(malformed, "{}\n");
    const future = new Date(Date.now() + 60_000);
    utimesSync(malformed, future, future);
    assert.throws(
      () => buildShowcaseModel({ productPath: `evidence/mvp/local-synthetic/agent-evals/${name}/results.json` }),
      /Product evidence/,
    );
    const model = buildShowcaseModel();
    assert.ok(model.risks.some((risk) => risk.includes(`Skipped invalid product evidence`) && risk.includes(name)));
  } finally {
    rmSync(testRoot, { recursive: true, force: true });
  }
});

test("rendering escapes evidence-controlled prose", () => {
  const model = buildShowcaseModel({ revision: "test-revision", discoverEvidence: false });
  model.waza.tasks[0].prompt = "<script>alert('no')</script>";
  const html = renderShowcaseHtml(model);
  assert.doesNotMatch(html, /<script>alert/);
  assert.match(html, /&lt;script&gt;alert/);
});

test("failure explanations show expected versus actual arguments without raw check keys", () => {
  const details = explainObservedFailures({
    checkScore: { observed: { failed: ["expectedToolCall"] } },
    toolCalls: [{ name: "set_engagement_status", args: { engagement_id: "eng-product-launch", status: "red", note: "" }, result: { status: "invalid" } }],
  }, {
    toolCall: { name: "set_engagement_status", args: { engagement_id: "eng-product-launch", status: "red" } },
  });
  assert.equal(details.length, 1);
  assert.match(details[0], /Expected arguments .*"status":"red"/);
  assert.match(details[0], /The assistant sent .*"note":""/);
  assert.match(details[0], /product returned “invalid”/i);
  assert.doesNotMatch(details[0], /expectedToolCall/);
  assert.deepEqual(
    explainObservedFailures(
      { checkScore: { observed: { failed: ["expectedSkillInvocation"] } } },
      { skill: { name: "engagement-meeting-prep" } },
    ),
    ["The assistant did not load the required “engagement-meeting-prep” instructions."],
  );
});

test("showcase CLI accepts explicit inputs and rejects unsafe ports or unknown arguments", () => {
  assert.deepEqual(parseShowcaseArgs(["--port", "4311", "--product", "p.json", "--waza", "w.json"]), {
    port: 4311,
    productPath: "p.json",
    wazaPath: "w.json",
  });
  assert.throws(() => parseShowcaseArgs(["--port", "80"]), /1024 through 65535/);
  assert.throws(() => parseShowcaseArgs(["--wat"]), /Unknown or incomplete/);
});

test("showcase server is loopback-ready, read-only, and refreshes a rendered page", async () => {
  const server = createShowcaseServer({ revision: "test-revision", discoverEvidence: false });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  try {
    const address = server.address();
    const origin = `http://127.0.0.1:${address.port}`;
    const health = await fetch(`${origin}/health`);
    assert.equal(health.status, 200);
    assert.deepEqual(await health.json(), { status: "ok" });
    const page = await fetch(origin);
    assert.equal(page.status, 200);
    assert.match(page.headers.get("content-type"), /text\/html/);
    assert.match(await page.text(), /A plain-English tour/);
    assert.equal((await fetch(`${origin}/missing`)).status, 404);
    assert.equal((await fetch(origin, { method: "POST" })).status, 405);
  } finally {
    await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
  }
});
