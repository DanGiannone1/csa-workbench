/* Layer 3 + 4 demo: run ONE canonical scenario against the live app, print the
 * deterministic verdict fact by fact, then ship the same transcript to Azure AI
 * Foundry for LLM judging.
 *
 *   node scripts/eval_demo.mjs [case-id]        (default: ACME-2-update-status)
 *
 * Env: DEMO_PASSWORD, MVP_API_URL, MVP_RAW_TRACE_ROOT (+ the reset env used by
 * dev.py), and optionally FOUNDRY_PROJECT_ENDPOINT / FOUNDRY_JUDGE_DEPLOYMENT /
 * FOUNDRY_EVAL_GROUP_ID for the layer-4 hand-off.
 *
 * Output is written under .local-runs/eval-demo/ — a demo run is NOT evidence:
 * it skips the clean-worktree and provenance gates of npm run eval:mvp. */
import { execFileSync, spawnSync } from "node:child_process";
import { mkdirSync, readFileSync, realpathSync, writeFileSync } from "node:fs";
import { relative, resolve, sep } from "node:path";
import { evaluateCase, parseSse } from "./mvp_evidence.mjs";
import { atomicScoringMode } from "./mvp_eval_manifest.mjs";

const API = process.env.MVP_API_URL || "http://127.0.0.1:18000";
const caseId = process.argv[2] || "ACME-2-update-status";
const suite = JSON.parse(readFileSync(new URL("../tests/evals/mvp-cases.json", import.meta.url), "utf8"));
const item = suite.cases.find((c) => c.id === caseId);
if (!item) throw new Error(`unknown case '${caseId}' — canonical ids: ${suite.cases.map((c) => c.id).join(", ")}`);
if (!process.env.DEMO_PASSWORD) throw new Error("DEMO_PASSWORD is required");

const bold = (s) => `\x1b[1m${s}\x1b[0m`;
const green = (s) => `\x1b[32m${s}\x1b[0m`;
const red = (s) => `\x1b[31m${s}\x1b[0m`;
const dim = (s) => `\x1b[2m${s}\x1b[0m`;
const rule = () => console.log(dim("─".repeat(72)));

async function json(path, init = {}) {
  const r = await fetch(`${API}${path}`, init);
  if (!r.ok) throw new Error(`${init.method ?? "GET"} ${path} -> ${r.status} ${await r.text()}`);
  return r.status === 204 ? null : r.json();
}
async function sessionFor(actor) {
  const login = await json("/auth/login", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ username: actor, password: process.env.DEMO_PASSWORD }) });
  const headers = { "X-Auth-Token": login.token, "content-type": "application/json" };
  const session = await json("/sessions", { method: "POST", headers });
  return { headers, sessionId: session.session_id };
}
const state = (s) => json(`/sessions/${s.sessionId}/app/state`, { headers: s.headers });

function readRawRecords(rawPath, runIdForTurn) {
  const root = realpathSync(resolve(process.env.MVP_RAW_TRACE_ROOT || "logs/sdk-events"));
  const file = realpathSync(rawPath);
  const within = relative(root, file);
  if (within.startsWith(`..${sep}`) || within === ".." || within.startsWith(sep)) throw new Error("trace outside root");
  return readFileSync(file, "utf8").split(/\r?\n/).filter(Boolean).map((l) => JSON.parse(l)).filter((r) => r.run_id === runIdForTurn);
}

function toolCallsOf(events) {
  const calls = new Map(); const order = [];
  for (const e of events) {
    if (e.type === "TOOL_CALL_START") { calls.set(e.tool_call_id, { name: e.tool_call_name, args: "", result: null }); order.push(e.tool_call_id); }
    else if (e.type === "TOOL_CALL_ARGS") calls.get(e.tool_call_id).args += e.delta ?? "";
    else if (e.type === "TOOL_CALL_RESULT") calls.get(e.tool_call_id).result = e.result;
  }
  return order.map((id) => { const c = calls.get(id); let args = {}; try { args = c.args ? JSON.parse(c.args) : {}; } catch { args = { raw: c.args }; } return { name: c.name, args, result: c.result }; });
}

const engagementLine = (s, id) => { const e = (s.engagements ?? []).find((x) => x.id === id); return e ? `status=${e.status} statusNote=${JSON.stringify(e.statusNote ?? "")}` : "(not visible)"; };

console.log(bold(`\nLAYER 3 DEMO — ${item.id}`));
console.log(dim("demo run (skips evidence provenance gates; use npm run eval:mvp for evidence)\n"));
console.log(`${bold("Actor:")} ${item.actor}${item.observerActor ? ` (end state verified as ${item.observerActor})` : ""}`);
console.log(`${bold("Prompt:")} "${item.prompt}"\n`);

console.log("resetting fixture to known state (acme-ai-v1)…");
const resetOut = execFileSync("uv", ["run", "python", "scripts/reset_demo_state.py"], { env: { ...process.env, CONFIRM_DEMO_RESET: "YES" }, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] }).trim();
const fixture = JSON.parse(resetOut.split("\n").at(-1));
console.log(dim(`fixture ${fixture.fixtureVersion} · ${fixture.engagementIds.join(", ")}\n`));

const session = await sessionFor(item.actor);
const observer = item.observerActor && item.observerActor !== item.actor ? await sessionFor(item.observerActor) : session;
const before = await state(observer);
const started = performance.now();
const response = await fetch(`${API}/sessions/${session.sessionId}/messages`, { method: "POST", headers: session.headers, body: JSON.stringify({ prompt: item.prompt, navigation_version: 0 }) });
if (!response.ok) throw new Error(`turn failed: ${response.status}`);
const events = parseSse(await response.text());
const runId = events.find((e) => e.type === "RUN_STARTED")?.run_id;
const trace = await json(`/sessions/${session.sessionId}/trace`, { headers: session.headers });
const rawRecords = readRawRecords(trace.raw_sdk_trace, runId);
const after = await state(observer);
const latencyMs = Math.round(performance.now() - started);

rule();
console.log(bold("WHAT THE AGENT DID"));
for (const call of toolCallsOf(events)) {
  console.log(`  ${call.name}(${dim(JSON.stringify(call.args))})`);
  console.log(`    → ${call.result?.operation} · ${call.result?.status}`);
}
const answer = events.filter((e) => e.type === "TEXT_MESSAGE_CONTENT").map((e) => e.delta).join("");
if (answer.trim()) console.log(`  ${bold("answer:")} ${answer.trim().slice(0, 200)}${answer.trim().length > 200 ? "…" : ""}`);

rule();
console.log(bold("DATABASE (authoritative reads, before → after)"));
const targetId = item.expectation.engagementAfter?.id ?? item.expectation.resourceId ?? item.expectation.argumentTargetId;
if (targetId) console.log(`  ${targetId}:\n    before ${engagementLine(before, targetId)}\n    after  ${engagementLine(after, targetId)}`);
console.log(`  personalTasks: ${(before.personalTasks ?? []).length} → ${(after.personalTasks ?? []).length}`);
console.log(`  engagements visible: ${(before.engagements ?? []).length} → ${(after.engagements ?? []).length}`);

const verdict = evaluateCase({ expectation: item.expectation, before, after, events, rawRecords, scoringMode: atomicScoringMode(item.id) });
rule();
console.log(bold(`DETERMINISTIC CHECKS — ${verdict.pass ? green("PASS") : red("FAIL")} (${verdict.checkScore.credit.passed}/${verdict.checkScore.credit.total} credited, ${latencyMs} ms)`));
for (const [name, ok] of Object.entries(verdict.scoredChecks)) console.log(`  ${ok ? green("✓") : red("✗")} ${name}`);

const outDir = `.local-runs/eval-demo/${new Date().toISOString().replace(/[:.]/g, "-")}`;
mkdirSync(outDir, { recursive: true });
const results = { schemaVersion: 5, kind: "mvp-agent-eval", runId: `demo-${caseId}`, scope: "demo", provenance: "eval_demo.mjs — demo run, not evidence", fixture, model: process.env.AZURE_DEPLOYMENT || "UNSPECIFIED", harness: "deepagents", results: [{ id: item.id, scenario: item.scenario, actor: item.actor, prompt: item.prompt, ...verdict, latencyMs, before, after, events, rawRecords }], workflows: [] };
writeFileSync(`${outDir}/results.json`, JSON.stringify(results, null, 2));

rule();
if (process.env.FOUNDRY_PROJECT_ENDPOINT) {
  console.log(bold("LAYER 4 — shipping this transcript to Azure AI Foundry for judging…\n"));
  const upload = spawnSync("npm", ["run", "-s", "eval:foundry"], { env: { ...process.env, MVP_RESULTS: `${outDir}/results.json` }, encoding: "utf8" });
  process.stdout.write(upload.stdout ?? "");
  if (upload.status !== 0) { process.stderr.write(upload.stderr ?? ""); process.exitCode = 1; }
} else {
  console.log(`${bold("LAYER 4:")} set FOUNDRY_PROJECT_ENDPOINT / FOUNDRY_JUDGE_DEPLOYMENT, then:\n  MVP_RESULTS=${outDir}/results.json npm run eval:foundry`);
}
