#!/usr/bin/env python
"""Upload product eval evidence to Azure AI Foundry's evals API (advisory lane).

Converts a completed harness run (results.json) into Foundry agent-message rows
and scores them server-side with the built-in agent evaluators. The run appears
in the Foundry portal; results are advisory and never gate the product suite.

Environment:
  MVP_RESULTS                path to the evidence results.json (required)
  FOUNDRY_PROJECT_ENDPOINT   Foundry project endpoint URL (required)
  FOUNDRY_JUDGE_DEPLOYMENT   judge model deployment; must differ from the model
                             under test recorded in the evidence (required)
  FOUNDRY_EVAL_GROUP_ID      optional existing eval group to add the run to;
                             omit to create a new group

Output: foundry-run.json written beside the input results.json.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

sys.path.insert(0, str(Path(__file__).resolve().parent))
from foundry_evidence_rows import build_rows  # noqa: E402

EVALUATOR_CRITERIA_STD = [
    "builtin.intent_resolution", "builtin.tool_call_accuracy", "builtin.task_adherence",
    "builtin.task_completion", "builtin.tool_selection", "builtin.tool_input_accuracy",
    "builtin.tool_output_utilization", "builtin.quality_grader",
]


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"{name} is required")
    return value


def main() -> None:
    results_path = Path(require_env("MVP_RESULTS")).resolve()
    endpoint = require_env("FOUNDRY_PROJECT_ENDPOINT")
    judge = require_env("FOUNDRY_JUDGE_DEPLOYMENT")

    rows, evidence = build_rows(results_path)
    model_under_test = evidence.get("model")
    if not model_under_test or model_under_test == "UNSPECIFIED":
        raise SystemExit("evidence does not record the model under test; judge provenance would be unverifiable")
    # Same-model judging is allowed (this layer is advisory by charter) but never
    # silent: the pairing is printed so the provenance travels with the run.
    if judge == model_under_test:
        print(
            f"WARNING: judge deployment '{judge}' is the model under test — "
            "scores may carry self-preference bias; treat them accordingly.")
    print(
        f"{len(rows)} rows from evidence run {evidence['runId']} "
        f"(model under test: {model_under_test}; judge: {judge})")

    data_rows = [dict(r) for r in rows]
    client = AIProjectClient(endpoint=endpoint, credential=DefaultAzureCredential())
    oc = client.get_openai_client()

    schema = {
        "type": "custom",
        "item_schema": {
            "type": "object",
            "properties": {
                "item_id": {"type": "string"}, "scenario": {"type": "string"},
                "harness_pass": {"type": "boolean"}, "user_request": {"type": "string"},
                "agent_messages": {"type": "array"}, "tool_defs": {"type": "array"},
                "conversation": {"type": "array"}, "expected_actions": {"type": "array"},
            },
            "required": ["item_id", "user_request", "agent_messages"],
        },
        "include_sample_schema": False,
    }
    std = {"query": "{{item.user_request}}", "response": "{{item.agent_messages}}", "tool_definitions": "{{item.tool_defs}}"}
    criteria = [
        {"type": "azure_ai_evaluator", "name": name.split(".", 1)[1], "evaluator_name": name,
         "initialization_parameters": {"model": judge}, "data_mapping": std}
        for name in EVALUATOR_CRITERIA_STD
    ] + [
        {"type": "azure_ai_evaluator", "name": "tool_call_success", "evaluator_name": "builtin.tool_call_success",
         "initialization_parameters": {"model": judge},
         "data_mapping": {"response": "{{item.agent_messages}}", "tool_definitions": "{{item.tool_defs}}"}},
        {"type": "azure_ai_evaluator", "name": "customer_satisfaction", "evaluator_name": "builtin.customer_satisfaction",
         "initialization_parameters": {"model": judge}, "data_mapping": {"messages": "{{item.conversation}}"}},
        {"type": "azure_ai_evaluator", "name": "task_navigation_efficiency",
         "evaluator_name": "builtin.task_navigation_efficiency",
         # Order-insensitive on purpose: our contracts grade outcomes, not tool
         # sequences, so the advisory lane should not punish a different order.
         "initialization_parameters": {"matching_mode": "any_order_match"},
         "data_mapping": {"actions": "{{item.agent_messages}}", "expected_actions": "{{item.expected_actions}}"}},
    ]

    group_id = os.environ.get("FOUNDRY_EVAL_GROUP_ID", "").strip()
    if group_id:
        group = oc.evals.retrieve(group_id)
        print("reusing eval group:", group.id)
    else:
        group = oc.evals.create(name="csa-workbench-agent-evals", data_source_config=schema, testing_criteria=criteria)
        print("created eval group:", group.id)

    run = oc.evals.runs.create(
        eval_id=group.id, name=f"evidence-{evidence['runId']}",
        data_source={"type": "jsonl", "source": {"type": "file_content", "content": [{"item": r} for r in data_rows]}},
    )
    print("run:", run.id, run.status)

    deadline = time.time() + 30 * 60
    current = run
    while time.time() < deadline:
        current = oc.evals.runs.retrieve(eval_id=group.id, run_id=run.id)
        print("status:", current.status, flush=True)
        if current.status in ("completed", "failed", "canceled"):
            break
        time.sleep(20)

    per_row = []
    if current.status == "completed":
        for item in oc.evals.runs.output_items.list(eval_id=group.id, run_id=run.id):
            record = item.model_dump()
            source = record.get("datasource_item") or {}
            verdicts = {r.get("name") or "?": {"passed": r.get("passed"), "score": r.get("score")}
                        for r in (record.get("results") or [])}
            per_row.append({"item_id": source.get("item_id"), "harness_pass": source.get("harness_pass"), "foundry": verdicts})
        per_row.sort(key=lambda r: str(r["item_id"]))

    summary = {
        "kind": "foundry-advisory-run",
        "evidenceRun": evidence["runId"],
        "sourceRevision": evidence.get("sourceRevision"),
        "modelUnderTest": evidence.get("model"),
        "judge": judge,
        "eval_id": group.id,
        "run_id": run.id,
        "status": current.status,
        "report_url": getattr(current, "report_url", None),
        "per_testing_criteria_results": [dict(x) for x in (getattr(current, "per_testing_criteria_results", None) or [])],
        "per_row": per_row,
    }
    out_path = results_path.parent / "foundry-run.json"
    out_path.write_text(json.dumps(summary, indent=2, default=str))
    print("wrote", out_path)
    print("report_url:", summary["report_url"])
    if current.status != "completed":
        raise SystemExit(f"foundry run ended '{current.status}' (summary written to {out_path})")


if __name__ == "__main__":
    main()
