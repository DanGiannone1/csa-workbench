import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { MVP_EVAL_MANIFEST } from "./mvp_eval_manifest.mjs";

const DEFAULT_PATHS = Object.freeze({
  cases: "tests/evals/mvp-cases.json",
  workflows: "tests/evals/mvp-workflows.json",
  rubrics: "tests/evals/judge-rubrics.json",
});

function readJson(path) {
  return JSON.parse(readFileSync(path, "utf8"));
}

function duplicateValues(values) {
  const seen = new Set();
  const duplicates = new Set();
  for (const value of values) {
    if (seen.has(value)) duplicates.add(value);
    seen.add(value);
  }
  return [...duplicates];
}

function sameOrderedIds(actual, expected) {
  return Array.isArray(actual)
    && actual.length === expected.length
    && actual.every((value, index) => value === expected[index]);
}

function requireString(errors, value, path) {
  if (typeof value !== "string" || !value.trim()) errors.push(`${path} must be a non-empty string`);
}

function requireObject(errors, value, path) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    errors.push(`${path} must be an object`);
    return false;
  }
  return true;
}

function validateExpectation(errors, expectation, path) {
  if (!requireObject(errors, expectation, path)) return;
  if ("stateChanged" in expectation && typeof expectation.stateChanged !== "boolean") {
    errors.push(`${path}.stateChanged must be boolean when present`);
  }
  if (expectation.stateChanged === true && (!expectation.operation || !expectation.status)) {
    errors.push(`${path} with stateChanged=true must define operation and status`);
  }
  if (expectation.noCommitted === true && expectation.stateChanged !== false) {
    errors.push(`${path} with noCommitted=true must also set stateChanged=false`);
  }
  if (expectation.toolCall !== undefined) {
    if (requireObject(errors, expectation.toolCall, `${path}.toolCall`)) {
      requireString(errors, expectation.toolCall.name, `${path}.toolCall.name`);
      if (expectation.toolCall.args !== undefined && !requireObject(errors, expectation.toolCall.args, `${path}.toolCall.args`)) return;
      if (Array.isArray(expectation.forbiddenToolNames) && expectation.forbiddenToolNames.includes(expectation.toolCall.name)) {
        errors.push(`${path}.forbiddenToolNames must not include the expected tool ${expectation.toolCall.name}`);
      }
    }
  }
  for (const field of ["forbiddenToolNames", "requiredToolNames", "forbiddenSkillNames"]) {
    if (expectation[field] !== undefined && (!Array.isArray(expectation[field]) || expectation[field].some((item) => typeof item !== "string" || !item.trim()))) {
      errors.push(`${path}.${field} must be an array of non-empty strings when present`);
    }
  }
  if (expectation.navigation !== undefined && !requireObject(errors, expectation.navigation, `${path}.navigation`)) return;
  if (expectation.safeNonExecution !== undefined && !requireObject(errors, expectation.safeNonExecution, `${path}.safeNonExecution`)) return;
}

function validateAtomicSuite(errors, suite) {
  if (!requireObject(errors, suite, "mvp-cases")) return [];
  requireString(errors, suite.fixtureVersion, "mvp-cases.fixtureVersion");
  if (!Array.isArray(suite.cases)) {
    errors.push("mvp-cases.cases must be an array");
    return [];
  }
  const ids = suite.cases.map((item) => item?.id);
  for (const duplicate of duplicateValues(ids)) errors.push(`duplicate atomic case id: ${duplicate}`);
  if (!sameOrderedIds(ids, MVP_EVAL_MANIFEST.atomicCaseIds)) {
    errors.push(`atomic case IDs must exactly match manifest order: ${MVP_EVAL_MANIFEST.atomicCaseIds.join(", ")}`);
  }
  for (const [index, item] of suite.cases.entries()) {
    const path = `mvp-cases.cases[${index}]`;
    if (!requireObject(errors, item, path)) continue;
    requireString(errors, item.id, `${path}.id`);
    requireString(errors, item.actor, `${path}.actor`);
    requireString(errors, item.prompt, `${path}.prompt`);
    validateExpectation(errors, item.expectation, `${path}.expectation`);
  }
  return ids;
}

function validateWorkflowSuite(errors, suite) {
  if (!requireObject(errors, suite, "mvp-workflows")) return [];
  requireString(errors, suite.fixtureVersion, "mvp-workflows.fixtureVersion");
  if (!Array.isArray(suite.workflows)) {
    errors.push("mvp-workflows.workflows must be an array");
    return [];
  }
  const ids = suite.workflows.map((item) => item?.id);
  for (const duplicate of duplicateValues(ids)) errors.push(`duplicate workflow id: ${duplicate}`);
  if (!sameOrderedIds(ids, MVP_EVAL_MANIFEST.workflowIds)) {
    errors.push(`workflow IDs must exactly match manifest order: ${MVP_EVAL_MANIFEST.workflowIds.join(", ")}`);
  }
  for (const [workflowIndex, workflow] of suite.workflows.entries()) {
    const path = `mvp-workflows.workflows[${workflowIndex}]`;
    if (!requireObject(errors, workflow, path)) continue;
    requireString(errors, workflow.id, `${path}.id`);
    requireString(errors, workflow.actor, `${path}.actor`);
    requireString(errors, workflow.description, `${path}.description`);
    if (!Array.isArray(workflow.turns) || workflow.turns.length === 0) {
      errors.push(`${path}.turns must be a non-empty array`);
      continue;
    }
    const turnIds = workflow.turns.map((turn) => turn?.id);
    for (const duplicate of duplicateValues(turnIds)) errors.push(`duplicate turn id in ${workflow.id}: ${duplicate}`);
    if (workflow.groundingTurn !== undefined && (!Number.isInteger(workflow.groundingTurn) || workflow.groundingTurn < 0 || workflow.groundingTurn >= workflow.turns.length)) {
      errors.push(`${path}.groundingTurn must be a valid turn index`);
    }
    for (const [turnIndex, turn] of workflow.turns.entries()) {
      const turnPath = `${path}.turns[${turnIndex}]`;
      if (!requireObject(errors, turn, turnPath)) continue;
      requireString(errors, turn.id, `${turnPath}.id`);
      requireString(errors, turn.prompt, `${turnPath}.prompt`);
      validateExpectation(errors, turn.expectation, `${turnPath}.expectation`);
    }
  }
  return ids;
}

function validateRubrics(errors, warnings, suite, atomicIds) {
  if (!requireObject(errors, suite, "judge-rubrics")) return;
  if (suite.version !== 1) errors.push("judge-rubrics.version must be 1");
  if (!Array.isArray(suite.rubrics)) {
    errors.push("judge-rubrics.rubrics must be an array");
    return;
  }
  const caseIds = suite.rubrics.map((item) => item?.caseId);
  for (const duplicate of duplicateValues(caseIds)) errors.push(`duplicate rubric caseId: ${duplicate}`);
  const atomicSet = new Set(atomicIds);
  for (const [index, rubric] of suite.rubrics.entries()) {
    const path = `judge-rubrics.rubrics[${index}]`;
    if (!requireObject(errors, rubric, path)) continue;
    requireString(errors, rubric.caseId, `${path}.caseId`);
    if (!atomicSet.has(rubric.caseId)) errors.push(`${path}.caseId does not match an atomic case: ${rubric.caseId}`);
    if (!Array.isArray(rubric.questions) || rubric.questions.length === 0) {
      errors.push(`${path}.questions must be a non-empty array`);
      continue;
    }
    for (const [questionIndex, question] of rubric.questions.entries()) {
      const questionPath = `${path}.questions[${questionIndex}]`;
      if (!requireObject(errors, question, questionPath)) continue;
      requireString(errors, question.dimension, `${questionPath}.dimension`);
      requireString(errors, question.question, `${questionPath}.question`);
    }
  }
  const rubricSet = new Set(caseIds);
  for (const id of atomicIds) {
    if (!rubricSet.has(id)) warnings.push(`no advisory rubric for atomic case ${id}`);
  }
}

export function validateEvalHarness({ casesSuite, workflowSuite, rubricSuite }) {
  const errors = [];
  const warnings = [];
  const atomicIds = validateAtomicSuite(errors, casesSuite);
  const workflowIds = validateWorkflowSuite(errors, workflowSuite);
  if (casesSuite?.fixtureVersion && workflowSuite?.fixtureVersion && casesSuite.fixtureVersion !== workflowSuite.fixtureVersion) {
    errors.push(`fixture versions must match: ${casesSuite.fixtureVersion} != ${workflowSuite.fixtureVersion}`);
  }
  validateRubrics(errors, warnings, rubricSuite, atomicIds);
  return {
    pass: errors.length === 0,
    errors,
    warnings,
    summary: {
      fixtureVersion: casesSuite?.fixtureVersion ?? workflowSuite?.fixtureVersion ?? null,
      atomicCases: atomicIds.length,
      workflows: workflowIds.length,
      rubricCases: Array.isArray(rubricSuite?.rubrics) ? rubricSuite.rubrics.length : 0,
    },
  };
}

export function loadEvalHarnessInputs(paths = DEFAULT_PATHS) {
  return {
    casesSuite: readJson(paths.cases ?? DEFAULT_PATHS.cases),
    workflowSuite: readJson(paths.workflows ?? DEFAULT_PATHS.workflows),
    rubricSuite: readJson(paths.rubrics ?? DEFAULT_PATHS.rubrics),
  };
}

function main() {
  const result = validateEvalHarness(loadEvalHarnessInputs());
  console.log(JSON.stringify(result, null, 2));
  if (!result.pass) process.exitCode = 1;
}

if (process.argv[1] && resolve(fileURLToPath(import.meta.url)) === resolve(process.argv[1])) {
  main();
}