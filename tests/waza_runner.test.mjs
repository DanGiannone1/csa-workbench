import assert from "node:assert/strict";
import { chmodSync, mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import test from "node:test";

const REPOSITORY_ROOT = resolve(fileURLToPath(new URL("..", import.meta.url)));

function bashPath(path) {
  return path.replaceAll("\\", "/");
}

function fakeWaza(root) {
  const path = join(root, "fake-waza.sh");
  writeFileSync(path, `#!/usr/bin/env bash
set -u
if [[ "\${1:-}" == "--version" ]]; then
  echo "waza version 0.38.3"
  exit 0
fi
if [[ "\${1:-}" != "run" ]]; then
  exit 2
fi
eval_file="\${2}"
skill="$(basename "$(dirname "\${eval_file}")")"
printf '%s\\n' "\${skill}" >>"\${FAKE_WAZA_LOG}"
output=""
shift 2
while (( \$# )); do
  if [[ "\${1}" == "--output" ]]; then
    output="\${2}"
    shift 2
  else
    shift
  fi
done
if [[ "\${FAKE_WAZA_MODE}" == "runtime-error" && "\${skill}" == "tasks" ]]; then
  exit 2
fi
printf '{"schemaVersion":"1.2","eval_id":"fake-%s","summary":{"total_tests":0,"succeeded":0,"failed":0},"tasks":[]}\\n' "\${skill}" >"\${output}"
if [[ "\${FAKE_WAZA_MODE}" == "test-failure" && "\${skill}" == "tasks" ]]; then
  exit 1
fi
exit 0
`, "utf8");
  chmodSync(path, 0o755);
  return path;
}

function resultFiles(root) {
  return readdirSync(root, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => join(root, entry.name, "waza.json"))
    .filter((path) => {
      try {
        readFileSync(path);
        return true;
      } catch {
        return false;
      }
    });
}

function runAdvisory(root, mode, trials = "") {
  const results = join(root, "results");
  const log = join(root, "calls.log");
  const binary = fakeWaza(root);
  const run = spawnSync("bash", ["scripts/waza_eval.sh", "advisory"], {
    cwd: REPOSITORY_ROOT,
    encoding: "utf8",
    env: {
      ...process.env,
      CSA_WAZA_BIN: bashPath(binary),
      CSA_WAZA_RESULTS_ROOT: bashPath(results),
      CSA_WAZA_TEST_MODE: "1",
      CSA_WAZA_TRIALS: trials,
      FAKE_WAZA_LOG: bashPath(log),
      FAKE_WAZA_MODE: mode,
    },
  });
  return { ...run, results, log };
}

test("advisory Waza test failures retain provenance, run every suite, and aggregate exit 1", () => {
  const root = mkdtempSync(join(tmpdir(), "csa-waza-runner-"));
  try {
    const run = runAdvisory(root, "test-failure");
    assert.equal(run.status, 1, run.stderr);
    assert.deepEqual(readFileSync(run.log, "utf8").trim().split(/\r?\n/), ["tasks", "calendar", "weekly-review"]);
    const reports = resultFiles(run.results).map((path) => JSON.parse(readFileSync(path, "utf8")));
    assert.equal(reports.length, 3);
    assert.deepEqual(reports.map((report) => report.csaMvpProvenance.skill.name).sort(), ["calendar", "tasks", "weekly-review"]);
    for (const report of reports) {
      assert.equal(report.csaMvpProvenance.tag, "advisory");
      assert.equal(report.csaMvpProvenance.wazaVersion, "0.38.3");
      assert.equal(report.csaMvpProvenance.sourceDirtyBefore, true);
      assert.equal(report.csaMvpProvenance.sourceDirtyAfter, true);
      assert.match(report.csaMvpProvenance.eval, new RegExp(`tests/evals/waza/${report.csaMvpProvenance.skill.name}/eval\\.yaml$`));
    }
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("advisory Waza returns zero only when every suite succeeds", () => {
  const root = mkdtempSync(join(tmpdir(), "csa-waza-runner-"));
  try {
    const run = runAdvisory(root, "success");
    assert.equal(run.status, 0, run.stderr);
    assert.deepEqual(readFileSync(run.log, "utf8").trim().split(/\r?\n/), ["tasks", "calendar", "weekly-review"]);
    assert.equal(resultFiles(run.results).length, 3);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("advisory Waza setup/runtime errors keep their exit status and stop later suites", () => {
  const root = mkdtempSync(join(tmpdir(), "csa-waza-runner-"));
  try {
    const run = runAdvisory(root, "runtime-error");
    assert.equal(run.status, 2, run.stderr);
    assert.deepEqual(readFileSync(run.log, "utf8").trim().split(/\r?\n/), ["tasks"]);
    assert.equal(resultFiles(run.results).length, 0);
    assert.match(run.stderr, /exit status 2/);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("advisory Waza rejects an invalid trial count as configuration exit 2", () => {
  const root = mkdtempSync(join(tmpdir(), "csa-waza-runner-"));
  try {
    const run = runAdvisory(root, "success", "zero");
    assert.equal(run.status, 2, run.stderr);
    assert.match(run.stderr, /CSA_WAZA_TRIALS must be a positive integer/);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});
