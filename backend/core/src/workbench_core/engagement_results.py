"""Translation of Engagement service outcomes into product tool results, plus the
one model-visible rendering of an Engagement record shared by both agent adapters."""

from __future__ import annotations

from typing import Any

from .engagements import Outcome
from .tool_protocol import ProductToolResult


def engagement_detail_text(record: dict[str, Any]) -> str:
    """Model-visible detail for one Engagement: the facts a user would ask about.
    The typed ProductToolResult stays the control-plane truth; this is the data."""
    lines = [
        f"Engagement [{record['id']}] {record.get('name', '')}",
        f"customer={record.get('customer') or 'n/a'} | status={record.get('status', 'green')}"
        + (f" ({record['statusNote']})" if record.get("statusNote") else "")
        + f" | start={record.get('startDate') or 'n/a'} | target={record.get('targetDate') or 'n/a'}",
        "members: " + (", ".join(f"{m.get('userId')}({m.get('role')})" for m in record.get("members") or []) or "none"),
    ]
    if record.get("description"):
        lines.append(f"description: {record['description']}")
    if record.get("businessValue"):
        lines.append(f"businessValue: {record['businessValue']}")
    if record.get("value"):
        lines.append(f"value: ${record['value']:,.0f}")
    if record.get("currentState"):
        lines.append(f"currentState (as of {record.get('stateDate') or 'n/a'}): {record['currentState']}")
    if record.get("objectives"):
        lines.append("objectives: " + "; ".join(record["objectives"]))
    if record.get("keyDates"):
        lines.append("keyDates: " + "; ".join(
            f"{k.get('date')} {k.get('label')}{' (done)' if k.get('done') else ''}"
            for k in record["keyDates"]))
    if record.get("contacts"):
        lines.append("customer contacts: " + "; ".join(
            f"{c.get('name')} ({c.get('role')})" for c in record["contacts"]))
    timeline = record.get("timeline") or []
    if timeline:
        lines.append("timeline (newest first):")
        for entry in timeline[:10]:
            src = f" [from {entry['source']}]" if entry.get("source") else ""
            lines.append(f"- [{entry.get('id')}] {entry.get('date')} {entry.get('type')}: "
                         f"{entry.get('title')} — {entry.get('author')}{src}")
    for label, key, fields in (
        ("tasks", "tasks", ("title", "status", "priority", "dueDate")),
        ("actions", "actions", ("title", "status", "owner", "dueDate")),
        ("milestones", "milestones", ("title", "status", "dueDate")),
        ("risks", "risks", ("title", "severity", "status")),
    ):
        items = record.get(key) or []
        if items:
            lines.append(f"{label}:")
            for item in items:
                parts = [str(item.get(field)) for field in fields if item.get(field)]
                lines.append(f"- [{item.get('id')}] " + " | ".join(parts))
    artifacts = record.get("library") or []
    lines.append(f"artifacts: {len(artifacts)}")
    conventions = record.get("conventions") or []
    if conventions:
        lines.append("conventions: " + "; ".join(c.get("text", "") for c in conventions))
    return "\n".join(lines)


_EMPTY_MESSAGE_STATUSES = frozenset({"succeeded", "resolved", "committed"})


def engagement_product_result(outcome: Outcome) -> ProductToolResult:
    """Return the one typed tool-result representation of an Engagement outcome.

    The service-owned status and operation remain authoritative.  Unknown outcome
    statuses are an adapter fault, so fail closed rather than emitting a generic
    successful-looking result.
    """
    if outcome.status in _EMPTY_MESSAGE_STATUSES:
        message = ""
    elif outcome.status == "invalid":
        details = "; ".join(outcome.errors.values())
        message = f"INVALID: {details}" if details else "INVALID: engagement input is invalid."
    elif outcome.status == "not_found":
        message = "ENGAGEMENT_NOT_FOUND: no visible engagement matches that reference."
    elif outcome.status == "forbidden":
        message = "FORBIDDEN: your engagement role does not allow that action."
    elif outcome.status == "noop":
        message = "NO_CHANGES: the engagement already has that state."
    elif outcome.status == "ambiguous":
        message = "AMBIGUOUS: multiple visible engagements match that reference."
    elif outcome.status == "conflict":
        message = "CONFLICT: the engagement changed; refresh and try again."
    elif outcome.status == "failed":
        message = "FAILED: engagement operation failed."
    else:
        raise ValueError(f"unsupported engagement outcome status: {outcome.status}")

    resource = None
    if outcome.record and outcome.record.get("id"):
        resource = {"kind": "engagement", "id": outcome.record["id"]}
    return ProductToolResult(
        outcome.status,
        outcome.code or f"engagement.{outcome.status}",
        outcome.operation,
        message,
        resource=resource,
    )
