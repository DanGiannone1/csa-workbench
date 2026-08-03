"""The session-start brief: deterministic ranking of what needs the user today."""

from __future__ import annotations

import unittest

from fastapi import HTTPException
from fastapi.testclient import TestClient

from workbench_api import app as orchestrator
from workbench_core import compute_brief

TODAY = "2026-08-02"


def eng(eid: str, status: str = "green", note: str = "", key_dates=None, tasks=None) -> dict:
    return {"id": eid, "name": eid.replace("eng-", "").title(), "status": status,
            "statusNote": note, "keyDates": key_dates or [], "tasks": tasks or []}


class BriefTests(unittest.TestCase):
    def test_all_green_reads_as_calm(self):
        brief = compute_brief({"engagements": [eng("eng-a")], "personalTasks": []}, TODAY)
        self.assertEqual(brief["items"], [])
        self.assertIn("Nothing needs you", brief["message"])

    def test_ranking_hard_dates_then_red_then_yellow_then_overdue(self):
        state = {
            "engagements": [
                eng("eng-yellow", "yellow", "Waiting on corpus"),
                eng("eng-red", "red", "Security review failed"),
                eng("eng-dated", key_dates=[
                    {"date": "2026-08-01", "label": "Renewal signed", "done": False},
                    {"date": "2026-12-01", "label": "Far away", "done": False},
                    {"date": "2026-08-03", "label": "Already done", "done": True},
                ]),
                eng("eng-tasks", tasks=[
                    {"title": "Late", "status": "To do", "dueDate": "2026-07-30"}]),
            ],
            "personalTasks": [{"title": "Report", "status": "To do", "dueDate": "2026-07-01"}],
        }
        brief = compute_brief(state, TODAY)
        labels = [item["label"] for item in brief["items"]]
        self.assertEqual(len(brief["items"]), 4)  # capped
        self.assertIn("Renewal signed 2026-08-01", labels[0])   # hard date first
        self.assertEqual(brief["items"][0]["tone"], "red")      # past date is red
        self.assertIn("Security review failed", labels[1])      # red before yellow
        self.assertIn("Waiting on corpus", labels[2])
        self.assertIn("overdue task", labels[3])
        self.assertIn("2 of 4 engagements need attention and 2 things are overdue.",
                      brief["message"])

    def test_horizon_and_dedupe_by_destination(self):
        state = {"engagements": [
            eng("eng-both", "red", "Halted", key_dates=[
                {"date": "2026-08-04", "label": "Plan due", "done": False}])],
            "personalTasks": []}
        brief = compute_brief(state, TODAY)
        # The key-date item and the red-status item share a destination; the
        # higher-ranked hard date survives and the record is not listed twice.
        self.assertEqual(len(brief["items"]), 1)
        self.assertIn("Plan due", brief["items"][0]["label"])
        self.assertEqual(brief["items"][0]["tone"], "yellow")  # future date within horizon
        self.assertEqual(brief["items"][0]["path"], "/engagements/eng-both")

    def test_personal_overdue_routes_to_todo(self):
        brief = compute_brief({"engagements": [], "personalTasks": [
            {"title": "A", "status": "To do", "dueDate": "2026-07-01"},
            {"title": "B", "status": "Done", "dueDate": "2026-07-01"},
        ]}, TODAY)
        self.assertEqual(brief["items"], [
            {"label": "1 of your own task overdue", "tone": "yellow", "path": "/todo"}])


class _AllowRequest:
    async def authenticate(self, _request):
        return None


class BriefEndpointTests(unittest.TestCase):
    """GET /sessions/{id}/brief: session-owned, computed from the caller's state."""

    def _client(self, monkey_state):
        async def owned(session_id: str, uid: str) -> None:
            if session_id != "session-dan" or uid != "dan":
                raise HTTPException(status_code=404, detail="Session not found")

        self._restore = (orchestrator.api_authenticator, orchestrator._require_owned_session,
                         orchestrator.appdb.supported_app_state_for,
                         dict(orchestrator.app.dependency_overrides))
        orchestrator.api_authenticator = _AllowRequest()
        orchestrator._require_owned_session = owned
        orchestrator.appdb.supported_app_state_for = lambda uid: monkey_state
        orchestrator.app.dependency_overrides[orchestrator.current_user] = lambda: "dan"
        return TestClient(orchestrator.app)

    def tearDown(self):
        if hasattr(self, "_restore"):
            (orchestrator.api_authenticator, orchestrator._require_owned_session,
             orchestrator.appdb.supported_app_state_for, overrides) = self._restore
            orchestrator.app.dependency_overrides = overrides

    def test_brief_returns_ranked_items_for_owned_session(self):
        client = self._client({"engagements": [eng("eng-a", "red", "Halted")], "personalTasks": []})
        response = client.get("/sessions/session-dan/brief")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("message", body)
        self.assertEqual(body["items"][0]["path"], "/engagements/eng-a")
        self.assertEqual(body["items"][0]["tone"], "red")

    def test_brief_hidden_for_unowned_session(self):
        client = self._client({"engagements": [], "personalTasks": []})
        self.assertEqual(client.get("/sessions/session-ava/brief").status_code, 404)


if __name__ == "__main__":
    unittest.main()
