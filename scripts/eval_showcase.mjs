import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import {
  existsSync,
  readFileSync,
  realpathSync,
  readdirSync,
  statSync,
} from "node:fs";
import { basename, dirname, isAbsolute, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { buildMvpScorecard, summarizeWaza } from "./mvp_scorecard.mjs";
import { validateProductEvidence, validateWazaEvidence } from "./mvp_scorecard_history.mjs";
import { parseWazaYaml } from "./waza_spec_validation.mjs";

const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));
export const REPOSITORY_ROOT = resolve(SCRIPT_DIR, "..");

const PRODUCT_EVIDENCE_ROOT = "evidence/mvp/local-synthetic/agent-evals";
const WAZA_EVIDENCE_ROOT = "evidence/mvp/local-synthetic/waza";
const SAFETY_CASES = new Set([
  "ACME-4-boundary",
]);

function readJson(path) {
  return JSON.parse(readFileSync(path, "utf8"));
}

function currentRevision(repositoryRoot) {
  try {
    return execFileSync("git", ["rev-parse", "HEAD"], {
      cwd: repositoryRoot,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
  } catch {
    return "UNAVAILABLE";
  }
}

function sha256(path) {
  return createHash("sha256").update(readFileSync(path)).digest("hex");
}

export function findEvidenceCandidates(repositoryRoot, evidenceRoot, filename) {
  const root = resolve(repositoryRoot, evidenceRoot);
  if (!existsSync(root)) return [];
  const candidates = [];
  for (const entry of readdirSync(root, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const path = join(root, entry.name, filename);
    if (!existsSync(path)) continue;
    const canonical = canonicalContainedPath(root, path, filename);
    if (canonical) candidates.push({ path: canonical, modified: statSync(canonical).mtimeMs });
  }
  candidates.sort((left, right) => right.modified - left.modified || right.path.localeCompare(left.path));
  return candidates.map((candidate) => candidate.path);
}

export function findLatestEvidence(repositoryRoot, evidenceRoot, filename) {
  return findEvidenceCandidates(repositoryRoot, evidenceRoot, filename)[0] ?? null;
}

function canonicalContainedPath(allowedRoot, selected, filename) {
  const canonicalRoot = realpathSync(allowedRoot);
  const canonicalSelected = realpathSync(selected);
  const withinRoot = relative(canonicalRoot, canonicalSelected);
  if (!withinRoot || withinRoot.startsWith("..") || isAbsolute(withinRoot) || basename(selected) !== filename) {
    return null;
  }
  return canonicalSelected;
}

function requireContainedEvidencePath(repositoryRoot, suppliedPath, evidenceRoot, filename) {
  const allowedRoot = resolve(repositoryRoot, evidenceRoot);
  const selected = resolve(repositoryRoot, suppliedPath);
  if (!existsSync(allowedRoot) || !existsSync(selected)) {
    throw new Error(`Evidence must be a ${filename} file under ${evidenceRoot}`);
  }
  const canonical = canonicalContainedPath(allowedRoot, selected, filename);
  if (!canonical) throw new Error(`Evidence must be a ${filename} file under ${evidenceRoot}`);
  return canonical;
}

function evidenceLabel(repositoryRoot, path) {
  if (!path) return null;
  const label = relative(repositoryRoot, path);
  return label.startsWith("..") ? basename(path) : label;
}

function unique(values) {
  return [...new Set(values.filter((value) => typeof value === "string" && value))];
}

export function describeExpectedState(expectation) {
  const entries = [];
  if (expectation.stateChanged === true) entries.push("authoritative application state changes");
  if (expectation.stateChanged === false) entries.push("authoritative application state remains unchanged");
  if (expectation.engagementAfter) {
    const item = expectation.engagementAfter;
    entries.push(`${item.id} ends ${item.status}${item.statusNote !== undefined ? ` with reason “${item.statusNote || "empty"}”` : ""}`);
  }
  if (expectation.onlyEngagementMayChange) entries.push(`only ${expectation.onlyEngagementMayChange} may change`);
  if (expectation.onlyPersonalAggregateMayChange) entries.push(`only ${expectation.onlyPersonalAggregateMayChange} may gain a record`);
  if (expectation.onlyEngagementAndPersonalAggregateMayChange) {
    const joint = expectation.onlyEngagementAndPersonalAggregateMayChange;
    entries.push(`only ${joint.engagementId} may change and only ${joint.aggregateKey} may gain a record`);
  }
  if (expectation.navigation?.destination) entries.push(`navigation resolves to ${expectation.navigation.destination.path}`);
  if (expectation.noNavigation) entries.push("no navigation event");
  if (expectation.noCommitted) entries.push("no committed result");
  if (expectation.zeroToolResults) entries.push("zero product-tool results");
  if (expectation.operation || expectation.status) {
    const result = `structured result ${[expectation.operation, expectation.status].filter(Boolean).join(" / ")}`;
    entries.push(expectation.safeNonExecution
      ? `either ${result}, or safe non-execution without changing state`
      : result);
  }
  return entries;
}

function goldContract(expectation, judgeQuestions = []) {
  const referenceTools = unique([
    ...(expectation.requiredToolNames ?? []),
    expectation.toolCall?.name,
  ]);
  return {
    referenceTools,
    referenceArguments: expectation.toolCall?.args ?? null,
    forbiddenTools: unique(expectation.forbiddenToolNames ?? []),
    requiredSkill: expectation.skill?.name ?? null,
    forbiddenSkills: unique(expectation.forbiddenSkillNames ?? []),
    expectedState: describeExpectedState(expectation),
    judgeQuestions,
  };
}

function readableCheckName(value) {
  return String(value).replaceAll(".", ": ").replace(/([a-z])([A-Z])/g, "$1 $2").toLowerCase();
}

export function explainObservedFailures(result, expectation) {
  const failed = result?.checkScore?.observed?.failed ?? [];
  return failed.map((name) => {
    const shortName = String(name).split(".").at(-1);
    if (shortName === "expectedToolCall" && expectation?.toolCall) {
      const expected = expectation.toolCall;
      const actual = (result.toolCalls ?? []).find((call) => call.name === expected.name);
      if (!actual) return `The expected ${expected.name} action was not taken.`;
      const resultStatus = actual.result?.status ? ` The product returned “${actual.result.status}”.` : "";
      return `Expected arguments ${JSON.stringify(expected.args)}. The assistant sent ${JSON.stringify(actual.args ?? {})}.${resultStatus}`;
    }
    if (shortName === "expectedSkillInvocation" && expectation?.skill?.name) {
      return `The assistant did not load the required “${expectation.skill.name}” instructions.`;
    }
    return `The ${readableCheckName(name)} check did not pass.`;
  });
}

function observedAttempt(result, latencyMs = null, expectation = null) {
  if (!result) return null;
  const failedChecks = result.checkScore?.observed?.failed
    ?? Object.entries(result.scoredChecks ?? {}).filter(([, pass]) => pass !== true).map(([name]) => name);
  return {
    pass: result.pass === true,
    scoringPath: result.checkScore?.path ?? "unknown",
    checksPassed: result.checkScore?.credit?.passed ?? null,
    checksTotal: result.checkScore?.credit?.total ?? null,
    failedChecks,
    failureDetails: explainObservedFailures(result, expectation),
    tools: (result.toolCalls ?? []).map((call) => ({ name: call.name, args: call.args ?? {}, status: call.result?.status ?? null })),
    response: typeof result.assistantResponse === "string" ? result.assistantResponse : "",
    terminal: result.terminal ?? null,
    latencyMs: latencyMs ?? result.latencyMs ?? null,
  };
}

function rubricMap(rubric) {
  return new Map((rubric?.rubrics ?? []).map((entry) => [
    entry.caseId,
    (entry.questions ?? []).map((question) => `${question.dimension}: ${question.question}`),
  ]));
}

function workflowRubricMap(rubric) {
  return new Map((rubric?.workflows ?? []).map((entry) => [
    entry.workflowId,
    (entry.questions ?? []).map((question) => `${question.dimension}: ${question.question}`),
  ]));
}

export function projectProductSkill(skill) {
  if (!skill) return null;
  return { name: skill.name, version: skill.version, sha256: skill.sha256 };
}

function productLane(repositoryRoot, productPath, definitions, workflows, rubric, revision) {
  const report = productPath ? validateProductEvidence(readJson(productPath)) : null;
  const scorecard = report ? buildMvpScorecard(report) : null;
  const lane = scorecard?.lanes?.productRuntime ?? null;
  const resultById = new Map((report?.results ?? []).map((result) => [result.id, result]));
  const workflowById = new Map((report?.workflows ?? []).map((result) => [result.id, result]));
  const rubrics = rubricMap(rubric);
  const workflowRubrics = workflowRubricMap(rubric);
  const tasks = (definitions.cases ?? []).map((definition) => {
    const result = resultById.get(definition.id);
    return {
      id: definition.id,
      actor: definition.actor,
      prompt: definition.prompt,
      clientExpectedOutput: definition.clientExpectedOutput,
      kind: SAFETY_CASES.has(definition.id) ? "safety" : "regression",
      gold: goldContract(definition.expectation, rubrics.get(definition.id) ?? []),
      observed: observedAttempt(result, result?.latencyMs, definition.expectation),
    };
  });
  const workflowViews = (workflows.workflows ?? []).map((definition) => {
    const result = workflowById.get(definition.id);
    const turns = definition.turns.map((turn, index) => ({
      id: turn.id,
      prompt: turn.prompt,
      clientExpectedOutput: turn.clientExpectedOutput,
      gold: goldContract(turn.expectation, []),
      observed: observedAttempt(
        result?.turnResults?.[index],
        result?.turns?.[index]?.latencyMs,
        definition.skillName && index === 0 ? { ...turn.expectation, skill: { name: definition.skillName } } : turn.expectation,
      ),
    }));
    return {
      id: definition.id,
      actor: definition.actor,
      description: definition.description,
      skillName: definition.skillName,
      pass: result?.pass === true,
      checksPassed: result?.checkScore?.credit?.passed ?? null,
      checksTotal: result?.checkScore?.credit?.total ?? null,
      failedChecks: result?.checkScore?.observed?.failed ?? [],
      failureDetails: turns.flatMap((turn) => turn.observed?.failureDetails ?? []),
      judgeQuestions: workflowRubrics.get(definition.id) ?? [],
      turns,
    };
  });
  const summaryChecks = report?.summary?.checks ?? lane?.checks ?? null;
  return {
    available: report !== null,
    evidence: productPath ? evidenceLabel(repositoryRoot, productPath) : null,
    runId: report?.runId ?? null,
    sourceRevision: report?.sourceRevision ?? null,
    currentRevision: revision,
    sourceMatchesCurrent: report?.sourceRevision === revision,
    harness: report?.harness ?? null,
    model: report?.model ?? null,
    scope: report?.scope ?? "unspecified",
    fixtureVersion: report?.fixture?.fixtureVersion ?? definitions.fixtureVersion ?? null,
    skill: projectProductSkill(report?.skill),
    startedAt: report?.startedAt ?? null,
    completedAt: report?.completedAt ?? null,
    atomic: lane?.atomic ?? {
      passed: report?.summary?.atomic?.passed ?? 0,
      total: report?.results?.length ?? 0,
      failed: report?.summary?.atomic?.failed ?? [],
    },
    workflowsSummary: lane?.workflows ?? {
      passed: report?.summary?.workflows?.passed ?? 0,
      total: report?.workflows?.length ?? 0,
      failed: report?.summary?.workflows?.failed ?? [],
    },
    checks: summaryChecks,
    latency: lane?.latency ?? null,
    hardGatePass: lane?.hardGatePass === true,
    groundingReview: lane?.groundingReviewBinding?.status ?? "NOT_SUPPLIED",
    groundingReviews: lane?.groundingReviews ?? [],
    judgeStatus: scorecard?.lanes?.advisoryJudge?.status ?? "NOT_SUPPLIED",
    acceptance: scorecard?.acceptance ?? { status: "INCOMPLETE", baseline: "NOT_ACCEPTED" },
    tasks,
    workflows: workflowViews,
  };
}

export function parseWazaTask(source) {
  const task = parseWazaYaml(source, "Waza task");
  const graders = Array.isArray(task.graders) ? task.graders : [];
  const configurations = graders.map((grader) => grader?.config ?? {});
  const tools = (key) => configurations.flatMap((config) =>
    Array.isArray(config[key]) ? config[key].map((entry) => entry?.tool).filter((tool) => typeof tool === "string") : [],
  );
  const skills = (key) => configurations.flatMap((config) =>
    Array.isArray(config[key]) ? config[key].filter((skill) => typeof skill === "string") : [],
  );
  return {
    id: task.id ?? null,
    name: task.name ?? null,
    description: task.description ?? null,
    tags: Array.isArray(task.tags) ? task.tags : [],
    prompt: task.inputs?.prompt ?? null,
    expectedTools: tools("expect_tools"),
    rejectedTools: tools("reject_tools"),
    requiredSkills: skills("required_skills"),
    forbiddenSkills: skills("forbidden_skills"),
  };
}

function observedWazaTask(result) {
  if (!result) return null;
  const run = result.runs?.[0] ?? null;
  const validations = Object.values(run?.validations ?? {});
  return {
    pass: result.status === "passed",
    status: result.status ?? "unknown",
    durationMs: run?.duration_ms ?? result.stats?.avg_duration_ms ?? null,
    tools: run?.session_digest?.tools_used ?? [],
    skills: unique(validations.flatMap((validation) => validation.details?.actual_skills ?? [])),
    validationFeedback: validations.map((validation) => ({
      name: validation.identifier ?? "validation",
      pass: validation.passed === true,
      feedback: validation.feedback ?? "",
    })),
  };
}

function wazaLane(repositoryRoot, wazaPath, revision, skillHash) {
  const taskRoot = resolve(repositoryRoot, "tests/evals/waza/engagement-meeting-prep/tasks");
  const definitions = readdirSync(taskRoot)
    .filter((name) => name.endsWith(".yaml"))
    .map((name) => parseWazaTask(readFileSync(join(taskRoot, name), "utf8")))
    .sort((left, right) => left.id.localeCompare(right.id));
  if (!wazaPath) return { available: false, tasks: definitions.map((definition) => ({ ...definition, observed: null })) };
  const report = validateWazaEvidence(readJson(wazaPath));
  const strictSummary = summarizeWaza(report);
  if (!strictSummary.countsConsistent) throw new Error("Waza evidence summary does not match its task results");
  const resultById = new Map((report.tasks ?? []).map((result) => [result.test_id ?? result.id, result]));
  const provenance = report.csaMvpProvenance ?? null;
  const sourceDirtyBefore = provenance?.sourceDirtyBefore ?? provenance?.sourceDirty ?? null;
  const sourceDirtyAfter = provenance?.sourceDirtyAfter ?? provenance?.sourceDirty ?? null;
  return {
    available: true,
    evidence: evidenceLabel(repositoryRoot, wazaPath),
    runId: report.eval_id ?? null,
    sourceRevision: provenance?.sourceRevision ?? null,
    currentRevision: revision,
    sourceMatchesCurrent: provenance?.sourceRevision === revision && provenance?.sourceRevisionAfter === revision,
    sourceClean: sourceDirtyBefore === false && sourceDirtyAfter === false,
    skill: report.skill ?? provenance?.skill?.name ?? "engagement-meeting-prep",
    skillMatchesCurrent: provenance?.skill?.sha256 === skillHash,
    model: report.config?.model_id ?? null,
    engine: report.config?.engine_type ?? "copilot-sdk",
    tag: provenance?.tag ?? "unknown",
    summary: report.summary ?? null,
    tasks: definitions.map((definition) => ({
      ...definition,
      observed: observedWazaTask(resultById.get(definition.id)),
    })),
  };
}

function presentationRisks(product, waza, evidenceWarnings = []) {
  const risks = [...evidenceWarnings];
  if (!product.available) risks.push("No local Deep Agents product evidence was discovered.");
  else {
    if (!product.sourceMatchesCurrent) risks.push("The displayed Deep Agents evidence does not match the current Git revision.");
    if (!product.hardGatePass) risks.push("The displayed Deep Agents product hard gate did not pass.");
    if (product.groundingReview !== "MATCHED" || product.groundingReviews.some((review) => review.status === "REVIEW_REQUIRED")) {
      risks.push("A human grounding review of the meeting brief is still required before this run can be accepted as a baseline.");
    }
    if (product.acceptance?.baseline !== "ACCEPTED") risks.push("No reviewed baseline has been accepted, so there is no valid change-over-change comparison.");
    if (product.judgeStatus !== "RECORDED") risks.push("Language-quality judging is not recorded for the displayed product run.");
  }
  if (!waza.available) risks.push("No local Waza execution evidence was discovered.");
  else {
    if (!waza.sourceMatchesCurrent || !waza.skillMatchesCurrent) risks.push("The displayed Waza evidence is stale relative to the current source or skill.");
    if (!waza.sourceClean) risks.push("The displayed Waza evidence was recorded from a dirty worktree and is demonstration-only.");
  }
  risks.push("The product suite is one trial per task; consistency, pass@k, and pass^k are not implemented.");
  risks.push("Tasks, calendar, and weekly-review have advisory Waza suites; only engagement-meeting-prep has recorded gate evidence.");
  risks.push("Product token/cost capture and automated judge calibration are not implemented.");
  return risks;
}

export function programMetrics(product) {
  const safetyTasks = product.tasks?.filter((task) => task.kind === "safety" && task.observed) ?? [];
  const safetyPassed = safetyTasks.filter((task) => task.observed?.pass === true).length;
  const atomicMean = product.latency?.atomic?.meanMs;
  const workflowMean = product.latency?.workflowTurns?.meanMs;
  return [
    {
      name: "Capability",
      value: "NOT SCORED",
      tone: "warn",
      note: "No use-case-derived gold capability suite exists yet; current tasks are regression + safety.",
    },
    {
      name: "Trustworthiness",
      value: product.judgeStatus === "RECORDED" ? "ADVISORY RECORDED" : "PARTIAL",
      tone: "warn",
      note: "Tool outputs and state are deterministic; complete response judging is not recorded for this run.",
    },
    {
      name: "Safety",
      value: !product.available ? "NO EVIDENCE" : safetyTasks.length ? `${safetyPassed}/${safetyTasks.length}` : "NOT RUN",
      tone: safetyTasks.length > 0 && safetyPassed === safetyTasks.length ? "pass" : safetyTasks.length ? "fail" : "warn",
      note: "All-or-nothing boundary case: rejecting a status change to a non-member's engagement.",
    },
    {
      name: "Consistency",
      value: "NOT MEASURED",
      tone: "warn",
      note: "One trial per task; pass@k and pass^k are not implemented.",
    },
    {
      name: "Performance",
      value: atomicMean === null || atomicMean === undefined ? "NOT RECORDED" : `${(atomicMean / 1000).toFixed(1)}s atomic`,
      tone: "neutral",
      note: workflowMean === null || workflowMean === undefined
        ? "End-to-end workflow timing is not recorded."
        : `${(workflowMean / 1000).toFixed(1)}s workflow-turn mean; non-gating end-to-end harness time.`,
    },
    {
      name: "Change impact",
      value: product.acceptance?.baseline === "ACCEPTED" ? "COMPARABLE" : "NO BASELINE",
      tone: product.acceptance?.baseline === "ACCEPTED" ? "pass" : "warn",
      note: "A reviewed accepted baseline is required for blocking regression deltas.",
    },
  ];
}

export function buildShowcaseModel({
  repositoryRoot = REPOSITORY_ROOT,
  productPath = null,
  wazaPath = null,
  revision = null,
  discoverEvidence = true,
} = {}) {
  const root = resolve(repositoryRoot);
  const actualRevision = revision ?? currentRevision(root);
  const atomicDefinitions = readJson(resolve(root, "tests/evals/mvp-cases.json"));
  const workflowDefinitions = readJson(resolve(root, "tests/evals/mvp-workflows.json"));
  const rubric = readJson(resolve(root, "tests/evals/judge-rubrics.json"));
  const skillPath = resolve(root, "backend/assistant/product-skills/engagement-meeting-prep/SKILL.md");
  const skillHash = sha256(skillPath);
  const evidenceWarnings = [];
  const productCandidates = productPath
    ? [requireContainedEvidencePath(root, productPath, PRODUCT_EVIDENCE_ROOT, "results.json")]
    : discoverEvidence ? findEvidenceCandidates(root, PRODUCT_EVIDENCE_ROOT, "results.json") : [];
  const wazaCandidates = wazaPath
    ? [requireContainedEvidencePath(root, wazaPath, WAZA_EVIDENCE_ROOT, "waza.json")]
    : discoverEvidence ? findEvidenceCandidates(root, WAZA_EVIDENCE_ROOT, "waza.json") : [];
  let product = null;
  for (const candidate of productCandidates) {
    try {
      product = productLane(root, candidate, atomicDefinitions, workflowDefinitions, rubric, actualRevision);
      break;
    } catch (error) {
      if (productPath) throw error;
      evidenceWarnings.push(`Skipped invalid product evidence ${evidenceLabel(root, candidate)}: ${error instanceof Error ? error.message : String(error)}`);
    }
  }
  let waza = null;
  for (const candidate of wazaCandidates) {
    try {
      waza = wazaLane(root, candidate, actualRevision, skillHash);
      break;
    } catch (error) {
      if (wazaPath) throw error;
      evidenceWarnings.push(`Skipped invalid focused-skill evidence ${evidenceLabel(root, candidate)}: ${error instanceof Error ? error.message : String(error)}`);
    }
  }
  product ??= productLane(root, null, atomicDefinitions, workflowDefinitions, rubric, actualRevision);
  waza ??= wazaLane(root, null, actualRevision, skillHash);
  return {
    generatedAt: new Date().toISOString(),
    currentRevision: actualRevision,
    product,
    waza,
    methodology: [
      { name: "Outcome", question: "Did authoritative application state end correctly, without collateral changes?", grader: "Deterministic code" },
      { name: "Boundaries", question: "Were forbidden tools, targets, navigation, and mutations avoided?", grader: "Deterministic code" },
      { name: "Response", question: "Was the answer accurate, non-leaking, and useful?", grader: "Advisory rubric / human today" },
      { name: "Operational", question: "How long did the harness take, and what did it call?", grader: "Measured evidence" },
    ],
    programMetrics: programMetrics(product),
    risks: presentationRisks(product, waza, evidenceWarnings),
  };
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function statusTone(value) {
  if (value === true || ["PASS", "PASSED", "RECORDED", "READY_FOR_BASELINE"].includes(String(value).toUpperCase())) return "pass";
  if (value === false || ["FAIL", "FAILED", "INCOMPLETE", "NOT_ACCEPTED"].includes(String(value).toUpperCase())) return "fail";
  return "warn";
}

function badge(label, tone = null) {
  return `<span class="badge ${tone ?? statusTone(label)}">${escapeHtml(label)}</span>`;
}

function metric(label, value, note = "") {
  return `<article class="metric"><p>${escapeHtml(label)}</p><strong>${escapeHtml(value)}</strong>${note ? `<small>${escapeHtml(note)}</small>` : ""}</article>`;
}

function toolChips(tools) {
  if (!tools?.length) return '<span class="muted">none</span>';
  return `<div class="chips">${tools.map((tool) => `<code>${escapeHtml(typeof tool === "string" ? tool : tool.name)}</code>`).join("")}</div>`;
}

function argumentBlock(argumentsValue) {
  if (!argumentsValue) return "";
  return `<pre>${escapeHtml(JSON.stringify(argumentsValue, null, 2))}</pre>`;
}

function observedBlock(observed) {
  if (!observed) return '<div class="empty">No matching technical evidence is selected for this fixture.</div>';
  const checkText = observed.checksTotal === null ? "not recorded" : `${observed.checksPassed}/${observed.checksTotal}`;
  return `<div class="observed">
    <div class="row between"><strong>What the assistant did</strong>${badge(observed.pass ? "PASS" : "FAIL")}</div>
    <dl class="facts">
      <div><dt>Checks passed</dt><dd>${escapeHtml(checkText)}</dd></div>
      <div><dt>How it was checked</dt><dd>${escapeHtml(observed.scoringPath)}</dd></div>
      <div><dt>Time</dt><dd>${observed.latencyMs === null ? "not recorded" : `${escapeHtml(observed.latencyMs)} ms`}</dd></div>
    </dl>
    <p class="eyebrow">Actions taken</p>${toolChips(observed.tools)}
    ${observed.failureDetails?.length ? `<div class="failure"><b>What missed the mark:</b><ul>${observed.failureDetails.map((detail) => `<li>${escapeHtml(detail)}</li>`).join("")}</ul></div>` : ""}
  </div>`;
}

function actualOutputBlock(observed) {
  return `<div class="prompt"><span>Actual output ${observed ? badge(observed.pass ? "PASS" : "FAIL") : badge("NO RESULT")}</span><p>${escapeHtml(observed?.response || (observed ? "No assistant answer was recorded." : "No recorded attempt is selected for this fixture."))}</p></div>`;
}

function goldBlock(gold) {
  return `<div class="gold">
    <div class="row between"><strong>What good looks like</strong>${badge("SET IN ADVANCE", "gold-tone")}</div>
    <p class="eyebrow">Likely actions (guidance, not the only valid path)</p>${toolChips(gold.referenceTools)}
    ${argumentBlock(gold.referenceArguments)}
    <p class="eyebrow">Result we require</p>
    <ul>${gold.expectedState.map((item) => `<li>${escapeHtml(item)}</li>`).join("") || "<li>structured event and result contract</li>"}</ul>
    ${gold.requiredSkill ? `<p><b>Instruction set it must use:</b> <code>${escapeHtml(gold.requiredSkill)}</code></p>` : ""}
    ${gold.forbiddenTools.length ? `<details><summary>Actions it must not take</summary>${toolChips(gold.forbiddenTools)}</details>` : ""}
    ${gold.forbiddenSkills.length ? `<details><summary>Instruction sets it must not load</summary>${toolChips(gold.forbiddenSkills)}</details>` : ""}
    ${gold.judgeQuestions.length ? `<details><summary>Questions we use to review the answer</summary><ul>${gold.judgeQuestions.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></details>` : ""}
  </div>`;
}

function productTask(task) {
  return `<article class="task">
    <summary><span>${badge(task.kind === "safety" ? "SAFETY" : "EVERYDAY JOB", task.kind === "safety" ? "warn" : "neutral")} <b>${escapeHtml(task.prompt)}</b><small class="task-id">${escapeHtml(task.id)}</small></span>${task.observed ? badge(task.observed.pass ? "PASS" : "FAIL") : badge("NO RESULT")}</summary>
    <div class="task-body">
      <div class="prompt"><span>Actor: ${escapeHtml(task.actor)}</span><p>“${escapeHtml(task.prompt)}”</p></div>
      <div class="prompt"><span>Expected output</span><p>${escapeHtml(task.clientExpectedOutput || "Not recorded in this fixture.")}</p></div>
      ${actualOutputBlock(task.observed)}
      <details><summary>Optional technical evidence</summary><div class="compare">${goldBlock(task.gold)}${observedBlock(task.observed)}</div></details>
    </div>
  </article>`;
}

function workflowView(workflow) {
  return `<details class="workflow-card">
    <summary><div><p class="eyebrow">One job across four messages</p><h3>Prepare, update, open, and capture a follow-up task</h3><small class="task-id">${escapeHtml(workflow.id)}</small></div>${badge(workflow.pass ? "PASS" : "FAIL")}</summary>
    <div class="workflow-body">
    <p>${escapeHtml(workflow.description)}</p>
    <p>${workflow.skillName ? `<b>Instruction set expected:</b> <code>${escapeHtml(workflow.skillName)}</code> · ` : ""}<b>Checks passed:</b> ${escapeHtml(workflow.checksPassed ?? "—")}/${escapeHtml(workflow.checksTotal ?? "—")}</p>
    ${workflow.failureDetails.length ? `<div class="failure"><b>What missed the mark:</b><ul>${workflow.failureDetails.map((detail) => `<li>${escapeHtml(detail)}</li>`).join("")}</ul></div>` : ""}
    <div class="turns">${workflow.turns.map((turn, index) => `<section class="turn"><span class="turn-index">${index + 1}</span><h4>${escapeHtml(turn.id)}</h4><p class="turn-prompt">“${escapeHtml(turn.prompt)}”</p><div class="prompt"><span>Expected output</span><p>${escapeHtml(turn.clientExpectedOutput || "Not recorded in this fixture.")}</p></div>${actualOutputBlock(turn.observed)}<details><summary>Optional technical evidence</summary><div class="compare">${goldBlock(turn.gold)}${observedBlock(turn.observed)}</div></details></section>`).join("")}</div>
    ${workflow.judgeQuestions.length ? `<details><summary>Questions we use to review the full conversation</summary><ul>${workflow.judgeQuestions.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></details>` : ""}
    </div>
  </details>`;
}

function wazaTask(task) {
  const observed = task.observed;
  return `<details class="task">
    <summary><span>${badge(task.tags.includes("gate") ? "CORE EXAMPLE" : "EXTRA EXAMPLE", task.tags.includes("gate") ? "neutral" : "warn")} <b>${escapeHtml(task.name)}</b><small class="task-id">${escapeHtml(task.id)}</small></span>${observed ? badge(observed.pass ? "PASS" : observed.status.toUpperCase()) : badge("NOT RUN")}</summary>
    <div class="task-body">
      <div class="prompt"><span>${escapeHtml(task.name)}</span><p>“${escapeHtml(task.prompt)}”</p></div>
      <div class="compare">
        <div class="gold"><strong>What good looks like</strong><p>${escapeHtml(task.description)}</p><p class="eyebrow">Actions we expect</p>${toolChips(task.expectedTools)}<p class="eyebrow">Actions we reject</p>${toolChips(task.rejectedTools)}${task.requiredSkills.length ? `<p><b>Instruction set it should use:</b> ${escapeHtml(task.requiredSkills.join(", "))}</p>` : ""}${task.forbiddenSkills.length ? `<p><b>Instruction set it should avoid:</b> ${escapeHtml(task.forbiddenSkills.join(", "))}</p>` : ""}</div>
        ${observed ? `<div class="observed"><div class="row between"><strong>What the assistant did</strong>${badge(observed.pass ? "PASS" : observed.status.toUpperCase())}</div><p><b>Time:</b> ${escapeHtml(observed.durationMs ?? "—")} ms</p><p class="eyebrow">Actions taken</p>${toolChips(observed.tools)}<p class="eyebrow">Instruction sets used</p>${toolChips(observed.skills)}${observed.validationFeedback.map((item) => `<p class="validation ${item.pass ? "ok" : "bad"}"><b>${escapeHtml(item.name)}:</b> ${escapeHtml(item.feedback)}</p>`).join("")}</div>` : '<div class="empty">This example was not included in the selected run.</div>'}
      </div>
    </div>
  </details>`;
}

export function describeRecordedResults(product, waza) {
  const wazaPassed = waza.summary?.succeeded ?? 0;
  const wazaTotal = waza.summary?.total_tests ?? 0;
  const focusedPassed = waza.available && wazaTotal > 0 && wazaPassed === wazaTotal;
  const fullPassed = product.available && product.hardGatePass;
  let summaryHeadline;
  if (!waza.available && !product.available) summaryHeadline = "No recorded test result is loaded yet.";
  else if (waza.available && product.available) {
    if (focusedPassed && fullPassed) summaryHeadline = "Both selected recorded runs passed.";
    else if (focusedPassed) summaryHeadline = "The selected focused run passed. The selected full-product run found a problem.";
    else summaryHeadline = "The selected recorded runs contain behavior that needs attention.";
  } else if (waza.available) {
    summaryHeadline = focusedPassed ? "The selected focused run passed." : "The selected focused run needs attention.";
  } else {
    summaryHeadline = fullPassed ? "The selected full-product run passed." : "The selected full-product run needs attention.";
  }
  const focusedHeadline = !waza.available
    ? "No focused result is loaded."
    : focusedPassed ? "The selected focused run passed." : "The selected focused run needs attention.";
  const fullHeadline = !product.available
    ? "No full-product result is loaded."
    : fullPassed ? "The selected full-product run passed its required checks." : "The selected full-product run still has a miss.";
  const talkTrack = `Describe what is shown: ${!waza.available
    ? "no focused result is loaded"
    : focusedPassed ? "the selected focused run passed" : "the selected focused run needs attention"}; ${!product.available
    ? "no full-product result is loaded"
    : fullPassed ? "the selected full-product run passed" : "the selected full-product run needs attention"}.`;
  return { focusedPassed, fullPassed, summaryHeadline, focusedHeadline, fullHeadline, talkTrack };
}

export function renderShowcaseHtml(model) {
  const product = model.product;
  const waza = model.waza;
  const productTitle = product.available ? `${product.harness}/${product.model}` : "No product evidence";
  const wazaPassed = waza.summary?.succeeded ?? 0;
  const wazaTotal = waza.summary?.total_tests ?? 0;
  const productAtomicPassed = product.atomic?.passed ?? 0;
  const productAtomicTotal = product.atomic?.total ?? 0;
  const productWorkflowPassed = product.workflowsSummary?.passed ?? 0;
  const productWorkflowTotal = product.workflowsSummary?.total ?? 0;
  const {
    focusedPassed,
    fullPassed,
    summaryHeadline,
    focusedHeadline,
    fullHeadline,
    talkTrack,
  } = describeRecordedResults(product, waza);
  const groundingReviewNeeded = product.available
    && (product.groundingReview !== "MATCHED" || product.groundingReviews.some((review) => review.status === "REVIEW_REQUIRED"));
  const productMetrics = product.available ? [
    metric("Short jobs", `${product.atomic.passed}/${product.atomic.total}`, product.atomic.failed?.length ? `Needs attention: ${product.atomic.failed.join(", ")}` : "all selected passed"),
    metric("Full journeys", `${product.workflowsSummary.passed}/${product.workflowsSummary.total}`, product.workflowsSummary.failed?.length ? `Needs attention: ${product.workflowsSummary.failed.join(", ")}` : "all selected passed"),
    metric("Detailed checks", product.checks ? `${product.checks.passed}/${product.checks.total}` : "not recorded", "facts checked by code"),
    metric("Overall result", product.hardGatePass ? "PASS" : "NEEDS ATTENTION", `test scope: ${product.scope}`),
  ].join("") : metric("Product evidence", "NOT FOUND", "run the Deep Agents suite first");
  const wazaMetrics = waza.available ? [
    metric("Examples run", `${waza.summary?.succeeded ?? 0}/${waza.summary?.total_tests ?? 0}`, `set: ${waza.tag}`),
    metric("Overall score", waza.summary?.aggregate_score ?? "—", "reported by the focused test"),
    metric("Time", waza.summary?.duration_ms ? `${waza.summary.duration_ms} ms` : "—", "focused skill test"),
    metric("Test runner", `Waza / ${waza.engine}`, `${waza.model ?? "model not recorded"}; focused lab, not the product runtime`),
  ].join("") : metric("Waza evidence", "NOT FOUND", "run the gate or advisory lane first");

  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'">
<title>CSA Workbench · Agent evaluation showcase</title>
<style>
:root{--ink:#10233f;--muted:#5c6b7d;--line:#dbe3ec;--paper:#f4f7fb;--card:#fff;--navy:#08172c;--cyan:#2dd4bf;--blue:#4f7cff;--gold:#d4971f;--red:#c33f4a;--green:#12805c;--shadow:0 18px 50px rgba(16,35,63,.09)}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.55 Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}a{color:inherit}.shell{max-width:1280px;margin:auto;padding:0 28px 80px}.hero{background:radial-gradient(circle at 80% 10%,rgba(45,212,191,.25),transparent 30%),linear-gradient(135deg,#07162b,#122d52);color:#fff;padding:72px max(28px,calc((100vw - 1224px)/2));margin-bottom:0}.hero-grid{display:grid;grid-template-columns:1.35fr .65fr;gap:50px;align-items:end}.kicker,.eyebrow{text-transform:uppercase;letter-spacing:.11em;font-size:11px;font-weight:800;color:#66758a}.hero .kicker{color:var(--cyan)}h1{font-size:clamp(38px,6vw,68px);line-height:1.02;letter-spacing:-.04em;margin:12px 0 20px;max-width:850px}.hero p{font-size:20px;color:#d8e3ef;max-width:760px}.hero-aside{border-left:1px solid rgba(255,255,255,.2);padding-left:28px}.hero-aside strong{font-size:22px;display:block;margin:7px 0}.hero-aside small{color:#a9bbd1}.nav{position:sticky;top:0;z-index:5;background:rgba(244,247,251,.92);backdrop-filter:blur(12px);border-bottom:1px solid var(--line)}.nav-inner{max-width:1280px;margin:auto;padding:12px 28px;display:flex;gap:10px;overflow:auto}.nav a{text-decoration:none;font-weight:750;font-size:13px;white-space:nowrap;padding:8px 13px;border-radius:999px}.nav a:hover{background:#e7edf5}section.block{padding-top:54px}.section-head{display:grid;grid-template-columns:1fr minmax(260px,440px);gap:30px;align-items:end;margin-bottom:22px}.section-head h2{font-size:34px;line-height:1.12;letter-spacing:-.025em;margin:5px 0}.section-head p{color:var(--muted);margin:0}.lane-note,.callout{padding:18px 20px;border:1px solid var(--line);border-radius:16px;background:#fff}.lane-note{border-left:4px solid var(--blue)}.callout{border-left:4px solid var(--gold);margin:18px 0}.pipeline{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.pipe{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:24px;box-shadow:var(--shadow);position:relative}.pipe:not(:last-child):after{content:"→";position:absolute;right:-20px;top:44%;z-index:2;color:var(--blue);font-size:22px;font-weight:900}.pipe span{display:block;color:var(--blue);font-weight:900;font-size:12px}.pipe b{display:block;margin:5px 0;font-size:18px}.pipe p{color:var(--muted);margin:0}.result-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.result-card{background:#fff;border:1px solid var(--line);border-radius:22px;padding:26px;box-shadow:var(--shadow);border-top:5px solid var(--green)}.result-card.attention{border-top-color:var(--gold)}.result-card h3{font-size:24px;margin:6px 0}.result-card .big-result{font-size:38px;font-weight:900;letter-spacing:-.04em;margin:10px 0}.result-card p{color:var(--muted)}.method-grid,.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}.program-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.program-metric{background:#fff;border:1px solid var(--line);border-radius:18px;padding:20px;box-shadow:var(--shadow);border-top:4px solid var(--blue)}.program-metric.pass{border-top-color:var(--green)}.program-metric.fail{border-top-color:var(--red)}.program-metric.warn{border-top-color:var(--gold)}.program-metric h3{margin:5px 0}.program-metric strong{font-size:23px;letter-spacing:-.02em}.program-metric p{margin:8px 0 0;color:var(--muted)}.method,.metric{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:20px;box-shadow:var(--shadow)}.method h3{margin:4px 0}.method p,.metric p{margin:0;color:var(--muted)}.method small,.metric small{display:block;color:var(--muted);margin-top:6px}.metric strong{display:block;font-size:30px;letter-spacing:-.03em;margin-top:4px}.lane{background:#fff;border:1px solid var(--line);border-radius:22px;padding:24px;box-shadow:var(--shadow);margin-top:20px}.lane-header{display:flex;justify-content:space-between;gap:24px;align-items:flex-start;margin-bottom:18px}.lane-header h3{font-size:24px;margin:2px 0}.provenance{font-size:12px;color:var(--muted);text-align:right}.badge{display:inline-flex;align-items:center;border-radius:999px;padding:4px 9px;font-size:10px;font-weight:900;letter-spacing:.07em;background:#edf1f6;color:#536074;vertical-align:middle}.badge.pass{background:#dff6eb;color:#096143}.badge.fail{background:#fde5e7;color:#9d2632}.badge.warn{background:#fff1cc;color:#79580b}.badge.neutral{background:#e8eefc;color:#31519e}.badge.gold-tone{background:#fff0c8;color:#765000}.task{border-top:1px solid var(--line)}.task:last-child{border-bottom:1px solid var(--line)}.task>summary{cursor:pointer;padding:15px 4px;display:flex;justify-content:space-between;gap:16px;list-style:none}.task>summary>span{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.task>summary::-webkit-details-marker{display:none}.task-id{display:block;color:var(--muted);font:11px "SFMono-Regular",Consolas,monospace;width:100%}.task-body{padding:0 0 22px}.prompt{background:#0d203c;color:#fff;border-radius:14px;padding:16px 18px;margin-bottom:14px}.prompt span{font-size:11px;text-transform:uppercase;letter-spacing:.1em;color:#9eb4cf}.prompt p{font-size:17px;margin:6px 0 0}.compare{display:grid;grid-template-columns:1fr 1fr;gap:14px}.gold,.observed,.empty{border:1px solid var(--line);border-radius:14px;padding:17px;background:#fbfcfe}.gold{border-top:3px solid var(--gold)}.observed{border-top:3px solid var(--blue)}.empty{display:grid;place-items:center;color:var(--muted);min-height:150px}.row{display:flex;align-items:center;gap:10px}.between{justify-content:space-between}.chips{display:flex;gap:7px;flex-wrap:wrap;margin:7px 0 12px}code{font-family:"SFMono-Regular",Consolas,monospace;background:#edf2f8;border:1px solid #dce5ef;border-radius:6px;padding:2px 6px;font-size:12px}pre{background:#0a1a30;color:#dce8f7;border-radius:10px;padding:12px;overflow:auto;font-size:12px}.facts{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.facts div{background:#f0f4f8;padding:9px;border-radius:8px}.facts dt{font-size:10px;text-transform:uppercase;color:var(--muted)}.facts dd{margin:2px 0 0;font-weight:800}.failure,.validation.bad{color:var(--red)}.validation.ok{color:var(--green)}blockquote{white-space:pre-wrap;margin:10px 0 0;padding:12px 14px;background:#f1f5f9;border-left:3px solid var(--blue);border-radius:7px}.workflow-card{border:1px solid var(--line);border-radius:18px;padding:22px;background:#fff}.workflow-card h3{margin:0}.turns{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:18px 0}.turn{position:relative;border:1px solid var(--line);border-radius:16px;padding:16px;background:#f8fafc}.turn-index{position:absolute;right:12px;top:10px;width:28px;height:28px;border-radius:50%;display:grid;place-items:center;background:var(--navy);color:#fff;font-weight:900}.turn h4{margin:0}.turn-prompt{min-height:70px;color:#31445d}.turn .gold,.turn .observed{margin-top:10px}.risk-list{display:grid;grid-template-columns:1fr 1fr;gap:10px;list-style:none;padding:0}.risk-list li{background:#fff;border:1px solid var(--line);border-left:4px solid var(--gold);border-radius:12px;padding:13px 15px}.run-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.command{background:#07172b;color:#d8e7f8;border-radius:16px;padding:18px;overflow:auto}.command .eyebrow{color:var(--cyan)}.command pre{padding:0;margin:10px 0 0;background:transparent;color:inherit;white-space:pre-wrap}.script{counter-reset:demo;display:grid;gap:10px}.script li{counter-increment:demo;list-style:none;background:#fff;border:1px solid var(--line);border-radius:13px;padding:15px 15px 15px 56px;position:relative}.script li:before{content:counter(demo);position:absolute;left:14px;top:13px;width:28px;height:28px;border-radius:50%;display:grid;place-items:center;background:var(--blue);color:#fff;font-weight:900}.technical{margin-top:48px;border:1px solid var(--line);border-radius:20px;background:#edf2f8;padding:0 24px 24px}.technical>summary{font-size:20px;font-weight:850;padding:22px 0;list-style:none}.technical>summary::-webkit-details-marker{display:none}.technical>summary:after{content:" +";color:var(--blue)}.technical[open]>summary:after{content:" −"}.footer{margin-top:60px;border-top:1px solid var(--line);padding-top:22px;color:var(--muted);font-size:12px}.muted{color:var(--muted)}details>summary{cursor:pointer}ul{padding-left:20px}@media(max-width:950px){.hero-grid,.section-head,.compare,.run-grid{grid-template-columns:1fr}.pipeline{grid-template-columns:1fr 1fr}.pipe:after{display:none}.result-grid{grid-template-columns:1fr}.method-grid,.metrics,.program-grid{grid-template-columns:1fr 1fr}.turns{grid-template-columns:1fr}.hero-aside{border-left:0;border-top:1px solid rgba(255,255,255,.2);padding:20px 0 0}.risk-list{grid-template-columns:1fr}}@media(max-width:580px){.shell{padding-left:16px;padding-right:16px}.hero{padding:48px 20px}.pipeline,.method-grid,.metrics,.program-grid{grid-template-columns:1fr}.lane{padding:16px}.facts{grid-template-columns:1fr}.task>summary{align-items:flex-start}}
.workflow-card{padding:0 22px}.workflow-card>summary{display:flex;justify-content:space-between;align-items:center;gap:16px;padding:22px 0;list-style:none}.workflow-card>summary::-webkit-details-marker{display:none}.workflow-card>summary:after{content:"Open →";color:var(--blue);font-weight:800}.workflow-card[open]>summary:after{content:"Close ↑"}.workflow-card>summary>.badge{margin-left:auto}.workflow-body{padding-bottom:22px}
</style></head><body>
<header class="hero"><div class="hero-grid"><div><div class="kicker">A plain-English tour</div><h1>Can we trust the assistant to do the right thing?</h1><p>We give it a known job, watch what it does, and compare the result with rules we wrote before the test.</p></div><aside class="hero-aside"><small>Selected evidence summary</small><strong>${escapeHtml(focusedHeadline)}</strong><strong>${escapeHtml(fullHeadline)}</strong><small>The evaluation makes both successes and misses visible.</small></aside></div></header>
<nav class="nav"><div class="nav-inner"><a href="#story">The idea</a><a href="#results">Recorded result</a><a href="#waza">Demo 1: one skill</a><a href="#product">Demo 2: full journey</a><a href="#run">Run it</a><a href="#details">Optional details</a></div></nav>
<main class="shell">
<section class="block" id="story"><div class="section-head"><div><p class="eyebrow">The idea in 30 seconds</p><h2>Test the assistant like a new teammate</h2></div><p>We do not grade secret thought processes or demand one perfect sentence. We check the job, the actions, the final result, and the safety rules.</p></div><div class="pipeline"><div class="pipe"><span>01</span><b>Give it a known job</b><p>We write the request and define “good” before the assistant starts.</p></div><div class="pipe"><span>02</span><b>Let it do the work</b><p>It uses safe test data and the same actions the product provides.</p></div><div class="pipe"><span>03</span><b>Check what happened</b><p>We compare the answer and saved result with the rules we set up front.</p></div></div></section>
<section class="block" id="results"><div class="section-head"><div><p class="eyebrow">Selected recorded result</p><h2>${escapeHtml(summaryHeadline)}</h2></div><p>A useful evaluation is not a marketing score. It should make success clear and expose a miss we can fix.</p></div><div class="result-grid"><article class="result-card${focusedPassed ? "" : " attention"}"><p class="eyebrow">Demo 1 · one focused skill</p><h3>Does meeting prep show up at the right time?</h3><div class="big-result">${waza.available ? `${escapeHtml(wazaPassed)}/${escapeHtml(wazaTotal)} passed` : "Not run"}</div><p>${!waza.available ? "Run the focused examples to load a result." : focusedPassed ? "In the selected run, the assistant used the meeting-prep instructions when asked and stayed out of unrelated requests." : "One or more focused examples need attention; open the demo to see which rule failed."}</p><a href="#waza">Show this demo →</a></article><article class="result-card${fullPassed ? "" : " attention"}"><p class="eyebrow">Demo 2 · the whole assistant</p><h3>Can it complete real jobs from start to finish?</h3><div class="big-result">${product.available ? `${escapeHtml(productAtomicPassed)}/${escapeHtml(productAtomicTotal)} short jobs` : "Not run"}</div><p>${!product.available ? "Run the full-product suite to load a result." : `${escapeHtml(productWorkflowPassed)}/${escapeHtml(productWorkflowTotal)} full journeys passed. ${fullPassed ? "The selected full-product test passed its required checks." : "The failed checks show exactly where behavior missed the rule."}`}</p><a href="#product">Show this demo →</a></article></div></section>
<section class="block" id="waza"><div class="section-head"><div><p class="eyebrow">Demo 1 · one focused skill</p><h2>Does the assistant know when to prepare a meeting?</h2></div><div class="lane-note"><b>Simple version:</b> this is like a unit test for one set of instructions. We try requests that should activate meeting prep and requests that should not.</div></div><div class="metrics">${wazaMetrics}</div><div class="lane"><div class="lane-header"><div><p class="eyebrow">Focused skill test</p><h3>Meeting preparation</h3><div>${waza.available ? `${badge(waza.sourceMatchesCurrent ? "CURRENT VERSION" : "OLDER VERSION")} ${badge(waza.skillMatchesCurrent ? "CURRENT INSTRUCTIONS" : "OLDER INSTRUCTIONS")} ${badge(waza.sourceClean ? "CLEAN RUN" : "DEMO-ONLY RUN")}` : badge("NO RESULT")}</div></div><div class="provenance">Waza evidence / ${escapeHtml(waza.engine ?? "engine unavailable")}<br>Focused laboratory—not the full product runtime<br>${escapeHtml(waza.model ?? "model unavailable")}</div></div>${waza.tasks.map(wazaTask).join("")}</div></section>
<section class="block" id="product"><div class="section-head"><div><p class="eyebrow">Demo 2 · the whole assistant</p><h2>Can it complete the job inside the real product?</h2></div><div class="lane-note"><b>Simple version:</b> now we test the entire path—user request, assistant decisions, product actions, saved data, and answer.</div></div><div class="metrics">${productMetrics}</div><div class="lane"><div class="lane-header"><div><p class="eyebrow">Full product test</p><h3>Realistic jobs and a four-message journey</h3><div>${product.available ? `${badge(product.sourceMatchesCurrent ? "CURRENT VERSION" : "OLDER VERSION")} ${badge(product.hardGatePass ? "OVERALL PASS" : "NEEDS ATTENTION")} ${badge(product.acceptance?.baseline === "ACCEPTED" ? "BASELINE SET" : "NO BASELINE YET")} ${groundingReviewNeeded ? badge("HUMAN REVIEW NEEDED", "warn") : badge("HUMAN REVIEW COMPLETE")}` : badge("NO RESULT")}</div></div><div class="provenance">${escapeHtml(productTitle)}<br>${product.skill ? `Skill ${escapeHtml(product.skill.name)} v${escapeHtml(product.skill.version ?? "unknown")} · ${escapeHtml(product.skill.sha256 ?? "hash unavailable")}<br>` : ""}${escapeHtml(product.model ?? "model unavailable")}</div></div>${product.available ? "" : '<div class="empty">Fixture-only review: expected outputs are shown below. Run the full assistant test and refresh to add actual outputs.</div>'}<h3>Short, focused jobs</h3>${product.tasks.map(productTask).join("")}<h3 style="margin-top:32px">One job across four messages</h3>${product.workflows.map(workflowView).join("")}</div></section>
<section class="block" id="run"><div class="section-head"><div><p class="eyebrow">Live demo controls</p><h2>Run in terminal, present in browser</h2></div><p>The browser is deliberately read-only. Model runs and fixture resets remain explicit terminal actions with visible environment and scope.</p></div><div class="run-grid"><div class="command"><p class="eyebrow">Skill gate · approximately one minute</p><pre>npm run eval:waza:gate

# Refresh this page after completion</pre></div><div class="command"><p class="eyebrow">Deep Agents full suite · approximately 12–15 minutes</p><pre># Start the isolated app first; see the presenter guide
MVP_EVAL_SCOPE=all npm run eval:mvp

# Refresh this page after completion</pre></div></div><h3>Simple ten-minute talk track</h3><ol class="script"><li><b>Start here:</b> “We test the assistant like a new teammate: give it a known job, watch what it does, and check the result.”</li><li><b>Show the selected recorded result:</b> ${escapeHtml(talkTrack)}</li><li><b>Run the focused test:</b> show one request that should trigger meeting prep and one that should not.</li><li><b>Open one full-product job:</b> compare “what good looks like” with “what the assistant did.”</li><li><b>Open the four-message journey:</b> describe the result shown and, when a rule failed, why that makes the test useful.</li><li><b>Only if asked:</b> open the scoring, metrics, provenance, and current gaps below.</li></ol></section>
<details class="technical" id="details"><summary>Optional details for a technical audience</summary><section class="block" id="method"><div class="section-head"><div><p class="eyebrow">How we decide pass or fail</p><h2>We check four different things</h2></div><p>Facts and safety are checked by code. Answer quality is reviewed against questions written in advance. Time and activity are measured.</p></div><div class="method-grid">${model.methodology.map((item) => `<article class="method"><p class="eyebrow">${escapeHtml(item.grader)}</p><h3>${escapeHtml(item.name)}</h3><p>${escapeHtml(item.question)}</p></article>`).join("")}</div></section><section class="block" id="metrics"><div class="section-head"><div><p class="eyebrow">What we can measure today</p><h2>Progress against the six target measures</h2></div><p>“Not scored” and “not measured” mean the measurement is not built yet. They are not hidden zeroes.</p></div><div class="program-grid">${model.programMetrics.map((item) => `<article class="program-metric ${escapeHtml(item.tone)}"><p class="eyebrow">${escapeHtml(item.name)}</p><strong>${escapeHtml(item.value)}</strong><p>${escapeHtml(item.note)}</p></article>`).join("")}</div></section><section class="block" id="risks"><div class="section-head"><div><p class="eyebrow">Be transparent</p><h2>What this demo does not prove yet</h2></div><p>These are the current limits of the evaluation program, derived from the selected results and roadmap.</p></div><ul class="risk-list">${model.risks.map((risk) => `<li>${escapeHtml(risk)}</li>`).join("")}</ul><div class="callout"><b>About “ideal reasoning”:</b> we do not display or grade hidden reasoning. We define the result, safety boundaries, and useful reference actions, then grade observable evidence.</div><div class="provenance">Evidence: ${escapeHtml(product.evidence ?? "none")}<br>Run: ${escapeHtml(product.runId ?? "none")} · Fixture: ${escapeHtml(product.fixtureVersion ?? "unknown")}<br>Current source: ${escapeHtml(model.currentRevision)} · Generated: ${escapeHtml(model.generatedAt)}</div></section></details>
<footer class="footer">CSA Workbench local evaluation showcase · read-only · refresh to discover the newest local evidence · current revision ${escapeHtml(model.currentRevision)}</footer>
</main></body></html>`;
}
