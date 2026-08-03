import assert from "node:assert/strict";
import { chmodSync, mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import test from "node:test";

const REPOSITORY_ROOT = resolve(fileURLToPath(new URL("..", import.meta.url)));

function fakeWaza(root) {
  const path = join(root, "fake-waza.py");
  writeFileSync(path, `#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

arguments = sys.argv[1:]
if arguments == ["--version"]:
    print("waza version 0.38.3")
    raise SystemExit(0)
if len(arguments) < 2 or arguments[0] != "run":
    raise SystemExit(2)

skill = Path(arguments[1]).parent.name
with Path(os.environ["FAKE_WAZA_LOG"]).open("a", encoding="utf-8") as log:
    log.write(f"{skill}\\n")
if os.environ["FAKE_WAZA_MODE"] == "runtime-error" and skill == "tasks":
    raise SystemExit(2)

try:
    output = Path(arguments[arguments.index("--output") + 1])
except (ValueError, IndexError):
    raise SystemExit(2)
report = {
    "schemaVersion": "1.2",
    "eval_id": f"fake-{skill}",
    "summary": {"total_tests": 0, "succeeded": 0, "failed": 0},
    "tasks": [],
}
output.write_text(json.dumps(report) + "\\n", encoding="utf-8")
if os.environ["FAKE_WAZA_MODE"] == "test-failure" and skill == "tasks":
    raise SystemExit(1)
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
      CSA_WAZA_BIN: binary,
      CSA_WAZA_RESULTS_ROOT: results,
      CSA_WAZA_TEST_MODE: "1",
      CSA_WAZA_TRIALS: trials,
      FAKE_WAZA_LOG: log,
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
    assert.deepEqual(readFileSync(run.log, "utf8").trim().split(/\r?\n/), ["engagement-meeting-prep", "tasks", "calendar", "weekly-review"]);
    const reports = resultFiles(run.results).map((path) => JSON.parse(readFileSync(path, "utf8")));
    assert.equal(reports.length, 4);
    assert.deepEqual(reports.map((report) => report.csaMvpProvenance.skill.name).sort(), ["calendar", "engagement-meeting-prep", "tasks", "weekly-review"]);
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
    assert.deepEqual(readFileSync(run.log, "utf8").trim().split(/\r?\n/), ["engagement-meeting-prep", "tasks", "calendar", "weekly-review"]);
    assert.equal(resultFiles(run.results).length, 4);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("advisory Waza setup/runtime errors keep their exit status and stop later suites", () => {
  const root = mkdtempSync(join(tmpdir(), "csa-waza-runner-"));
  try {
    const run = runAdvisory(root, "runtime-error");
    assert.equal(run.status, 2, run.stderr);
    assert.deepEqual(readFileSync(run.log, "utf8").trim().split(/\r?\n/), ["engagement-meeting-prep", "tasks"]);
    assert.equal(resultFiles(run.results).length, 1);
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
