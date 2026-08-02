"""The session-start brief: the day's ranked items, computed from the record.

Deterministic by design — the brief is the app speaking, not a model answering
a query (no tool-call chrome, no token cost, identical for identical state).
Ranking follows the design reference: hard dates first, then off-track
records, then overdue work.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

BRIEF_ITEM_CAP = 4
IMMINENT_DAYS = 7


def _overdue_tasks(tasks: list[dict[str, Any]], today: str) -> list[dict[str, Any]]:
    return [t for t in tasks
            if t.get("status") != "Done" and (t.get("dueDate") or "")[:10]
            and t["dueDate"][:10] < today]


def compute_brief(state: dict[str, Any], today: str | None = None) -> dict[str, Any]:
    """Rank what needs the user's attention today from their visible state."""
    today = today or date.today().isoformat()
    horizon = (date.fromisoformat(today) + timedelta(days=IMMINENT_DAYS)).isoformat()
    engagements = state.get("engagements") or []
    personal = state.get("personalTasks") or []

    items: list[dict[str, str]] = []

    # 1. Hard dates: undone key dates already past or landing within the horizon.
    dated: list[tuple[str, dict[str, str]]] = []
    for eng in engagements:
        for kd in eng.get("keyDates") or []:
            when = (kd.get("date") or "")[:10]
            if kd.get("done") or not when or when > horizon:
                continue
            dated.append((when, {
                "label": f"{eng['name']} — {kd.get('label', 'key date')} {when}",
                "tone": "red" if when <= today else "yellow",
                "path": f"/engagements/{eng['id']}",
            }))
    items.extend(item for _, item in sorted(dated, key=lambda pair: pair[0]))

    # 2. Off-track records, red before yellow, with the stated reason.
    for status in ("red", "yellow"):
        for eng in engagements:
            if eng.get("status") != status:
                continue
            why = (eng.get("statusNote") or "").strip()
            items.append({
                "label": f"{eng['name']}{' — ' + why if why else ''}",
                "tone": status,
                "path": f"/engagements/{eng['id']}",
            })

    # 3. Overdue shared tasks, grouped per engagement.
    for eng in engagements:
        count = len(_overdue_tasks(eng.get("tasks") or [], today))
        if count:
            items.append({
                "label": f"{count} overdue task{'s' if count != 1 else ''} on {eng['name']}",
                "tone": "yellow",
                "path": f"/engagements/{eng['id']}/tasks",
            })

    # 4. The user's own overdue list.
    personal_overdue = len(_overdue_tasks(personal, today))
    if personal_overdue:
        items.append({
            "label": f"{personal_overdue} of your own task{'s' if personal_overdue != 1 else ''} overdue",
            "tone": "yellow",
            "path": "/todo",
        })

    # One item per destination; ranked order decides which survives.
    seen: set[str] = set()
    deduped = [item for item in items
               if item["path"] not in seen and not seen.add(item["path"])]
    top = deduped[:BRIEF_ITEM_CAP]

    attention = [e for e in engagements if e.get("status") in ("yellow", "red")]
    overdue_total = personal_overdue + sum(
        len(_overdue_tasks(e.get("tasks") or [], today)) for e in engagements)
    n = len(engagements)
    message = (
        f"{len(attention)} of {n} engagement{'s' if n != 1 else ''} need"
        f"{'s' if len(attention) == 1 else ''} attention and {overdue_total} "
        f"thing{'s are' if overdue_total != 1 else ' is'} overdue."
    )
    if not top:
        message = "Nothing needs you right now — every record is green and nothing is overdue."

    return {"message": message, "items": top, "computedFor": today}
