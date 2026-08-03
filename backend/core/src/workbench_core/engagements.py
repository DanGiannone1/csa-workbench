"""The small shared Engagement application service.

Persistence and user lookup are deliberately supplied by the caller so this module
can be imported by both the orchestrator and the session runtime without bringing
their framework or Cosmos dependencies into the domain rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable, Protocol


ROLE_RANK = {"viewer": 0, "editor": 1, "owner": 2}
ROLES = tuple(ROLE_RANK)
STATUSES = ("green", "yellow", "red")
TIMELINE_TYPES = ("meeting", "decision", "risk", "note")


@dataclass(frozen=True)
class Outcome:
    """A transport-neutral, typed result for an Engagement operation."""

    status: str
    operation: str
    record: dict[str, Any] | None = None
    target_user_id: str | None = None
    changed_fields: tuple[str, ...] = ()
    errors: dict[str, str] = field(default_factory=dict)
    code: str | None = None


@dataclass(frozen=True)
class _Mutation:
    outcome: Outcome
    commit: bool


class EngagementRepository(Protocol):
    def create(self, actor_id: str, values: dict[str, Any]) -> dict[str, Any]: ...
    def load(self, engagement_id: str) -> dict[str, Any] | None: ...
    def list_for(self, actor_id: str) -> list[dict[str, Any]]: ...
    def update(self, engagement_id: str, mutator: Callable[[dict[str, Any]], _Mutation]) -> Outcome: ...
    def log_activity(self, engagement: dict[str, Any], actor_id: str, action: str, detail: str) -> None: ...


class EngagementService:
    """Authorization, validation, and resulting-state rules for Engagement basics."""

    def __init__(self, repository: EngagementRepository, user_lookup: Callable[[str], dict[str, Any] | None]):
        self._repository = repository
        self._user_lookup = user_lookup

    def list(self, actor_id: str) -> Outcome:
        return Outcome("succeeded", "list", record={"engagements": self._repository.list_for(actor_id)})

    def get(self, actor_id: str, engagement_id: str) -> Outcome:
        record = self._visible(actor_id, engagement_id)
        if record is None:
            return Outcome("not_found", "get", code="engagement.not_found")
        return Outcome("succeeded", "get", record=record)

    def resolve(self, actor_id: str, reference: str) -> Outcome:
        """Resolve only within the actor's permitted Engagements."""
        ref = (reference or "").strip()
        if not ref:
            return Outcome("invalid", "resolve", errors={"engagement": "required"})
        records = self._repository.list_for(actor_id)
        exact_id = next((item for item in records if item.get("id") == ref), None)
        if exact_id:
            return Outcome("resolved", "resolve", record=exact_id)
        exact_name = [item for item in records if (item.get("name") or "").lower() == ref.lower()]
        if len(exact_name) == 1:
            return Outcome("resolved", "resolve", record=exact_name[0])
        if len(exact_name) > 1:
            return Outcome("ambiguous", "resolve", code="engagement.ambiguous")
        partial = [item for item in records if ref.lower() in (item.get("name") or "").lower()]
        if len(partial) == 1:
            return Outcome("resolved", "resolve", record=partial[0])
        return Outcome("not_found" if not partial else "ambiguous", "resolve", code="engagement.not_found")

    def create(self, actor_id: str, values: dict[str, Any]) -> Outcome:
        normalized, errors = self._normalize(values, creating=True)
        if not errors:
            errors.update(self._validate_state({"status": "green", "statusNote": "", **normalized}))
        if errors:
            return Outcome("invalid", "create", errors=errors)
        if normalized.get("status", "green") == "green":
            normalized["statusNote"] = ""
        existing = next(
            (record for record in self._repository.list_for(actor_id)
             if record.get("createdBy") == actor_id
             and self._role(record, actor_id) == "owner"
             and (record.get("name") or "").strip().lower() == normalized["name"].lower()),
            None,
        )
        if existing is not None:
            return Outcome("noop", "create", record=existing)
        record = self._repository.create(actor_id, normalized)
        return Outcome("committed", "create", record=record, changed_fields=tuple(normalized))

    def update(self, actor_id: str, engagement_id: str, values: dict[str, Any]) -> Outcome:
        initial = self._visible(actor_id, engagement_id)
        if initial is None:
            return Outcome("not_found", "update", code="engagement.not_found")
        required = "owner" if "name" in values else "editor"

        def mutate(record: dict[str, Any]) -> _Mutation:
            denied = self._authorize(record, actor_id, required, "update")
            if denied:
                return _Mutation(denied, False)
            normalized, errors = self._normalize(values)
            if errors:
                return _Mutation(Outcome("invalid", "update", errors=errors), False)
            if not normalized:
                return _Mutation(Outcome("noop", "update", record=record), False)
            candidate = dict(record)
            candidate.update(normalized)
            if candidate.get("status") == "green":
                candidate["statusNote"] = ""
            state_errors = self._validate_state(candidate)
            if state_errors:
                return _Mutation(Outcome("invalid", "update", errors=state_errors), False)
            changed = tuple(key for key, value in candidate.items() if record.get(key) != value and key in set(normalized) | {"statusNote"})
            if not changed:
                return _Mutation(Outcome("noop", "update", record=record), False)
            for key in changed:
                record[key] = candidate[key]
            self._repository.log_activity(record, actor_id, "engagement.updated", ", ".join(changed))
            return _Mutation(Outcome("committed", "update", record=record, changed_fields=changed), True)

        return self._repository.update(engagement_id, mutate)

    def share(self, actor_id: str, engagement_id: str, user_ref: str, role: str) -> Outcome:
        initial = self._visible(actor_id, engagement_id)
        if initial is None:
            return Outcome("not_found", "share", code="engagement.not_found")
        def mutate(record: dict[str, Any]) -> _Mutation:
            denied = self._authorize(record, actor_id, "owner", "share")
            if denied:
                return _Mutation(denied, False)
            normalized_role = (role or "").strip().lower() or "viewer"
            if normalized_role not in ROLES:
                return _Mutation(Outcome("invalid", "share", errors={"role": "must be owner, editor, or viewer"}), False)
            target = self._user_lookup((user_ref or "").strip())
            if target is None or not target.get("id"):
                return _Mutation(Outcome("invalid", "share", errors={"userId": "unknown user"}), False)
            target_id = target["id"]
            existing = next((member for member in record.get("members", []) if member.get("userId") == target_id), None)
            if existing and existing.get("role") == normalized_role:
                return _Mutation(Outcome("noop", "share", record=record, target_user_id=target_id), False)
            if existing and existing.get("role") == "owner" and normalized_role != "owner":
                owners = [member for member in record.get("members", []) if member.get("role") == "owner"]
                if len(owners) == 1:
                    return _Mutation(Outcome("invalid", "share", errors={"members": "an engagement must keep at least one owner"}), False)
            if existing:
                existing["role"] = normalized_role
            else:
                record.setdefault("members", []).append({"userId": target_id, "role": normalized_role})
            self._repository.log_activity(record, actor_id, "member.added", f"{target_id} as {normalized_role}")
            return _Mutation(Outcome("committed", "share", record=record, target_user_id=target_id,
                                     changed_fields=("members",)), True)

        return self._repository.update(engagement_id, mutate)

    def remove_member(self, actor_id: str, engagement_id: str, member_id: str) -> Outcome:
        initial = self._visible(actor_id, engagement_id)
        if initial is None:
            return Outcome("not_found", "remove_member", code="engagement.not_found")

        def mutate(record: dict[str, Any]) -> _Mutation:
            denied = self._authorize(record, actor_id, "owner", "remove_member")
            if denied:
                return _Mutation(denied, False)
            target = next((member for member in record.get("members", []) if member.get("userId") == member_id), None)
            if target is None:
                return _Mutation(Outcome("not_found", "remove_member", code="member.not_found"), False)
            owners = [member for member in record.get("members", []) if member.get("role") == "owner"]
            if target.get("role") == "owner" and len(owners) == 1:
                return _Mutation(Outcome("invalid", "remove_member", errors={"members": "an engagement must keep at least one owner"}), False)
            record["members"] = [member for member in record["members"] if member.get("userId") != member_id]
            self._repository.log_activity(record, actor_id, "member.removed", member_id)
            return _Mutation(Outcome("committed", "remove_member", record=record, changed_fields=("members",)), True)

        return self._repository.update(engagement_id, mutate)

    # ── Prototype record operations (#31) ──────────────────────────────────────
    # Each writes one collection on the record, requires editor access, and logs
    # attributed activity. The timeline is append-only by construction: there are
    # no edit or delete operations for entries.

    def add_objective(self, actor_id: str, engagement_id: str, text: str) -> Outcome:
        cleaned = (text or "").strip()
        if not cleaned or len(cleaned) > 200:
            return Outcome("invalid", "add_objective", errors={"text": "required, at most 200 characters"})
        return self._append(actor_id, engagement_id, "add_objective", "objectives", cleaned,
                            "objective.added", cleaned,
                            duplicate=lambda items: cleaned.lower() in (i.lower() for i in items),
                            limit=(20, "objectives"))

    def add_key_date(self, actor_id: str, engagement_id: str, date_iso: str, label: str) -> Outcome:
        errors: dict[str, str] = {}
        cleaned = (label or "").strip()
        if not cleaned or len(cleaned) > 120:
            errors["label"] = "required, at most 120 characters"
        parsed = self._iso_or_none(date_iso)
        if parsed is None:
            errors["date"] = "must be an ISO calendar date"
        if errors:
            return Outcome("invalid", "add_key_date", errors=errors)
        entry = {"date": parsed, "label": cleaned, "done": False}
        return self._append(actor_id, engagement_id, "add_key_date", "keyDates", entry,
                            "keyDate.added", f"{cleaned} · {parsed}",
                            duplicate=lambda items: any(
                                i.get("label", "").lower() == cleaned.lower() and i.get("date") == parsed
                                for i in items),
                            limit=(30, "key dates"), sort_key=lambda i: i.get("date", ""))

    def toggle_key_date(self, actor_id: str, engagement_id: str, reference: str) -> Outcome:
        ref = (reference or "").strip().lower()
        if not ref:
            return Outcome("invalid", "toggle_key_date", errors={"reference": "required"})
        initial = self._visible(actor_id, engagement_id)
        if initial is None:
            return Outcome("not_found", "toggle_key_date", code="engagement.not_found")

        def mutate(record: dict[str, Any]) -> _Mutation:
            denied = self._authorize(record, actor_id, "editor", "toggle_key_date")
            if denied:
                return _Mutation(denied, False)
            items = record.get("keyDates") or []
            matches = [i for i in items if i.get("label", "").lower() == ref or i.get("date") == ref]
            if not matches:
                matches = [i for i in items if ref in i.get("label", "").lower()]
            if len(matches) != 1:
                status = "not_found" if not matches else "ambiguous"
                return _Mutation(Outcome(status, "toggle_key_date", code=f"keyDate.{status}"), False)
            matches[0]["done"] = not matches[0].get("done", False)
            state = "done" if matches[0]["done"] else "reopened"
            self._repository.log_activity(record, actor_id, "keyDate.toggled", f"{matches[0]['label']} {state}")
            return _Mutation(Outcome("committed", "toggle_key_date", record=record, changed_fields=("keyDates",)), True)

        return self._repository.update(engagement_id, mutate)

    def add_contact(self, actor_id: str, engagement_id: str, name: str, role: str = "") -> Outcome:
        cleaned = (name or "").strip()
        if not cleaned or len(cleaned) > 120:
            return Outcome("invalid", "add_contact", errors={"name": "required, at most 120 characters"})
        entry = {"name": cleaned, "role": (role or "").strip()[:120] or "Contact"}
        return self._append(actor_id, engagement_id, "add_contact", "contacts", entry,
                            "contact.added", f"{cleaned} ({entry['role']})",
                            duplicate=lambda items: any(i.get("name", "").lower() == cleaned.lower() for i in items),
                            limit=(30, "contacts"))

    def add_timeline_entry(self, actor_id: str, engagement_id: str, entry_type: str, title: str,
                           body: str = "", date_iso: str = "", source: str = "") -> Outcome:
        errors: dict[str, str] = {}
        kind = (entry_type or "").strip().lower()
        if kind not in TIMELINE_TYPES:
            errors["type"] = f"must be one of {', '.join(TIMELINE_TYPES)}"
        cleaned = (title or "").strip()
        if not cleaned or len(cleaned) > 200:
            errors["title"] = "required, at most 200 characters"
        when = self._iso_or_none(date_iso) if (date_iso or "").strip() else date.today().isoformat()
        if when is None:
            errors["date"] = "must be an ISO calendar date"
        if errors:
            return Outcome("invalid", "add_timeline_entry", errors=errors)
        initial = self._visible(actor_id, engagement_id)
        if initial is None:
            return Outcome("not_found", "add_timeline_entry", code="engagement.not_found")

        def mutate(record: dict[str, Any]) -> _Mutation:
            denied = self._authorize(record, actor_id, "editor", "add_timeline_entry")
            if denied:
                return _Mutation(denied, False)
            entries = record.setdefault("timeline", [])
            ids = {e.get("id") for e in entries}
            n = len(entries) + 1
            while f"tl-{n}" in ids:
                n += 1
            entries.insert(0, {
                "id": f"tl-{n}", "type": kind, "title": cleaned, "date": when,
                "body": (body or "").strip()[:2000], "author": actor_id,
                "source": (source or "").strip()[:200],
            })
            del entries[500:]  # bounded log
            self._repository.log_activity(record, actor_id, "timeline.added", f"{kind}: {cleaned}")
            return _Mutation(Outcome("committed", "add_timeline_entry", record=record,
                                     changed_fields=("timeline",)), True)

        return self._repository.update(engagement_id, mutate)

    def promote_artifact(self, actor_id: str, engagement_id: str, artifact_id: str) -> Outcome:
        ref = (artifact_id or "").strip()
        if not ref:
            return Outcome("invalid", "promote_artifact", errors={"artifactId": "required"})
        initial = self._visible(actor_id, engagement_id)
        if initial is None:
            return Outcome("not_found", "promote_artifact", code="engagement.not_found")

        def mutate(record: dict[str, Any]) -> _Mutation:
            denied = self._authorize(record, actor_id, "editor", "promote_artifact")
            if denied:
                return _Mutation(denied, False)
            item = next((a for a in record.get("library") or []
                         if a.get("id") == ref or a.get("name") == ref), None)
            if item is None:
                return _Mutation(Outcome("not_found", "promote_artifact", code="artifact.not_found"), False)
            if item.get("tier") == "gold":
                return _Mutation(Outcome("noop", "promote_artifact", record=record), False)
            item["tier"] = "gold"
            item["promotedBy"] = actor_id
            item["promotedAt"] = date.today().isoformat()
            self._repository.log_activity(record, actor_id, "artifact.promoted", item.get("name", ref))
            return _Mutation(Outcome("committed", "promote_artifact", record=record,
                                     changed_fields=("library",)), True)

        return self._repository.update(engagement_id, mutate)

    def _append(self, actor_id: str, engagement_id: str, operation: str, field_name: str,
                entry: Any, action: str, detail: str,
                duplicate: Callable[[list], bool], limit: tuple[int, str],
                sort_key: Callable[[Any], Any] | None = None) -> Outcome:
        initial = self._visible(actor_id, engagement_id)
        if initial is None:
            return Outcome("not_found", operation, code="engagement.not_found")

        def mutate(record: dict[str, Any]) -> _Mutation:
            denied = self._authorize(record, actor_id, "editor", operation)
            if denied:
                return _Mutation(denied, False)
            items = record.setdefault(field_name, [])
            if duplicate(items):
                return _Mutation(Outcome("noop", operation, record=record), False)
            cap, label = limit
            if len(items) >= cap:
                return _Mutation(Outcome("invalid", operation, errors={field_name: f"at most {cap} {label}"}), False)
            items.append(entry)
            if sort_key is not None:
                items.sort(key=sort_key)
            self._repository.log_activity(record, actor_id, action, detail)
            return _Mutation(Outcome("committed", operation, record=record, changed_fields=(field_name,)), True)

        return self._repository.update(engagement_id, mutate)

    @staticmethod
    def _iso_or_none(value: str) -> str | None:
        cleaned = (value or "").strip()
        if len(cleaned) != 10:
            return None
        try:
            parsed = date.fromisoformat(cleaned)
        except ValueError:
            return None
        return parsed.isoformat() if parsed.isoformat() == cleaned else None

    def _visible(self, actor_id: str, engagement_id: str) -> dict[str, Any] | None:
        record = self._repository.load(engagement_id)
        return record if record and self._role(record, actor_id) else None

    def _authorize(self, record: dict[str, Any], actor_id: str, minimum: str, operation: str) -> Outcome | None:
        role = self._role(record, actor_id)
        if role is None:
            return Outcome("not_found", operation, code="engagement.not_found")
        if ROLE_RANK[role] < ROLE_RANK[minimum]:
            return Outcome("forbidden", operation, errors={"role": f"requires {minimum} access"})
        return None

    @staticmethod
    def _role(record: dict[str, Any], actor_id: str) -> str | None:
        member = next((item for item in record.get("members", []) if item.get("userId") == actor_id), None)
        return member.get("role") if member else None

    def _normalize(self, values: dict[str, Any], creating: bool = False) -> tuple[dict[str, Any], dict[str, str]]:
        allowed = {"name", "description", "customer", "status", "statusNote", "startDate", "targetDate",
                   "businessValue", "currentState", "stateDate", "value", "objective"}
        errors: dict[str, str] = {}
        normalized: dict[str, Any] = {}
        for key, value in values.items():
            key = "statusNote" if key == "statusWhy" else key
            if key not in allowed:
                errors[key] = "unknown field"
                continue
            if value is None and not creating:
                continue
            if key == "value":
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    errors[key] = "must be a non-negative number"
                elif value < 0:
                    errors[key] = "must be a non-negative number"
                else:
                    normalized[key] = float(value)
                continue
            if not isinstance(value, str):
                errors[key] = "must be a string"
                continue
            normalized[key] = value.strip()
        if not creating and "objective" in normalized:
            errors["objective"] = "unknown field"  # creation-only convenience; use add_objective afterwards
            normalized.pop("objective", None)
        if creating and not normalized.get("name"):
            errors["name"] = "required"
        if "name" in normalized and not normalized["name"]:
            errors["name"] = "required"
        for field, limit in (("name", 120), ("description", 500), ("customer", 120), ("statusNote", 300),
                             ("businessValue", 300), ("currentState", 1200), ("objective", 200)):
            if field in normalized and len(normalized[field]) > limit:
                errors[field] = f"must be at most {limit} characters"
        if "status" in normalized:
            normalized["status"] = normalized["status"].lower()
            if creating and not normalized["status"]:
                normalized["status"] = "green"
            elif normalized["status"] not in STATUSES:
                errors["status"] = "must be green, yellow, or red"
        for field in ("startDate", "targetDate", "stateDate"):
            if normalized.get(field) and self._iso_or_none(normalized[field]) is None:
                errors[field] = "must be an ISO calendar date"
        # "Where it stands" always carries its as-of date: stamp today unless given.
        if normalized.get("currentState") and not normalized.get("stateDate"):
            normalized["stateDate"] = date.today().isoformat()
        return normalized, errors

    @staticmethod
    def _validate_state(record: dict[str, Any]) -> dict[str, str]:
        status = (record.get("status") or "green").lower()
        if status not in STATUSES:
            return {"status": "must be green, yellow, or red"}
        if status in ("yellow", "red") and not (record.get("statusNote") or "").strip():
            return {"statusNote": "yellow/red status requires a reason"}
        return {}
