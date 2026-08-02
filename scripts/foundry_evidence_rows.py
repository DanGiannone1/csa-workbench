"""Convert product eval evidence (results.json) into Foundry agent-message rows.

Each atomic case and each workflow turn becomes one row: the prompt, the
reconstructed assistant/tool message transcript, the product tool definitions
(generated from the model-visible schema catalog), the deterministic harness
verdict, and a ground-truth expected tool sequence derived from the case's own
gold contract (requiredToolNames, else the expected toolCall).
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

from workbench_assistant import mvp_tool_schemas as ts


def tool_definitions() -> list[dict]:
    defs = []
    for name, model in ts.ACTIVE_TOOL_SCHEMAS.items():
        schema = model.model_json_schema()
        schema.pop("title", None)
        defs.append({
            "type": "function", "name": name,
            "description": (model.__doc__ or "").strip() or f"CSA Workbench product tool `{name}`.",
            "parameters": schema,
        })
    return defs


def _expected_actions(expectation: dict) -> list[str]:
    if expectation.get("requiredToolNames"):
        return list(expectation["requiredToolNames"])
    tool_call = expectation.get("toolCall")
    return [tool_call["name"]] if tool_call else []


def _parse_result(raw):
    if isinstance(raw, dict):
        return raw
    for loader in (json.loads, ast.literal_eval):
        try:
            return loader(raw)
        except Exception:
            continue
    return {"raw": str(raw)}


def _transcript(events: list[dict]) -> tuple[list[dict], str]:
    """Rebuild ordered tool calls (keyed by tool_call_id) and assistant text."""
    calls, order, text = {}, [], []
    for event in events:
        kind = event["type"]
        if kind == "TOOL_CALL_START":
            calls[event["tool_call_id"]] = {"id": event["tool_call_id"], "name": event["tool_call_name"], "argstr": "", "result": None}
            order.append(event["tool_call_id"])
        elif kind == "TOOL_CALL_ARGS":
            calls[event["tool_call_id"]]["argstr"] += event.get("delta", "")
        elif kind == "TOOL_CALL_RESULT":
            calls[event["tool_call_id"]]["result"] = event.get("result")
        elif kind == "TEXT_MESSAGE_CONTENT":
            text.append(event.get("delta", ""))
    ordered = []
    for call_id in order:
        call = calls[call_id]
        try:
            args = json.loads(call["argstr"]) if call["argstr"] else {}
        except Exception:
            args = {"raw": call["argstr"]}
        ordered.append({"id": call_id, "name": call["name"], "args": args, "result": call["result"] or {}})
    return ordered, "".join(text)


def _response_messages(tool_calls: list[dict], assistant_text: str) -> list[dict]:
    messages = []
    for call in tool_calls:
        messages.append({"role": "assistant", "content": [
            {"type": "tool_call", "tool_call_id": call["id"], "name": call["name"], "arguments": call["args"]}]})
        messages.append({"role": "tool", "tool_call_id": call["id"], "content": [
            {"type": "tool_result", "tool_result": _parse_result(call["result"])}]})
    if assistant_text:
        messages.append({"role": "assistant", "content": [{"type": "text", "text": assistant_text}]})
    return messages


def build_rows(results_path: Path) -> tuple[list[dict], dict]:
    evidence = json.loads(results_path.read_text())
    cases = {c["id"]: c for c in json.loads((REPO / "tests/evals/mvp-cases.json").read_text())["cases"]}
    workflows = {w["id"]: w for w in json.loads((REPO / "tests/evals/mvp-workflows.json").read_text())["workflows"]}
    unknown = sorted(
        {r["id"] for r in evidence["results"] if r["id"] not in cases}
        | {w["id"] for w in evidence.get("workflows", []) if w["id"] not in workflows})
    if unknown:
        raise ValueError(
            "evidence ids not in the canonical suite (stale evidence or stale suite files): " + ", ".join(unknown))
    defs = tool_definitions()
    rows = []
    for result in evidence["results"]:
        case = cases[result["id"]]
        calls, text = _transcript(result["events"])
        rows.append({
            "item_id": result["id"],
            "scenario": result.get("scenario") or case.get("scenario", ""),
            "harness_pass": bool(result["pass"]),
            "user_request": result["prompt"],
            "agent_messages": _response_messages(calls, text),
            "tool_defs": defs,
            "conversation": [{"role": "user", "content": result["prompt"]}] + _response_messages(calls, text),
            "expected_actions": _expected_actions(case.get("expectation", {})),
        })
    for workflow in evidence.get("workflows", []):
        definition = workflows[workflow["id"]]
        turn_expectations = {t["id"]: t.get("expectation", {}) for t in definition.get("turns", [])}
        scored = workflow.get("scoredChecks", {})
        for turn in workflow["turns"]:
            calls, text = _transcript(turn["events"])
            turn_checks = {k: v for k, v in scored.items() if k.startswith(f"{turn['id']}.")}
            rows.append({
                "item_id": f"{workflow['id']}/{turn['id']}",
                "scenario": (workflow.get("scenario") or definition.get("scenario", "")) + f" — {turn['id']}",
                "harness_pass": bool(turn_checks) and all(turn_checks.values()),
                "user_request": turn["prompt"],
                "agent_messages": _response_messages(calls, text),
                "tool_defs": defs,
                "conversation": [{"role": "user", "content": turn["prompt"]}] + _response_messages(calls, text),
                "expected_actions": _expected_actions(turn_expectations.get(turn["id"], {})),
            })
    return rows, evidence
