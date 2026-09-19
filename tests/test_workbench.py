import json
import tempfile
import unittest
from pathlib import Path

from governed_change_workbench import ChangeWorkbench, SessionStore


def runner(phase: str, prompt: str) -> dict:
    return {"run_outcome": "complete", "raw_output": f"{phase} reviewed {len(prompt)} characters"}


class WorkbenchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.workbench = ChangeWorkbench(self.root)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_seed_creates_draft_and_bounded_title(self) -> None:
        session = self.workbench.create("  Add   export evidence  ")
        self.assertEqual(session.title, "Add export evidence")
        self.assertIn("Add   export evidence", session.implementation_prompt_draft)
        self.assertEqual(session.status, "conversation")

    def test_messages_are_bounded_and_role_checked(self) -> None:
        session = self.workbench.create()
        with self.assertRaises(ValueError):
            self.workbench.add_message(session.session_id, "system", "bad")
        with self.assertRaises(ValueError):
            self.workbench.add_message(session.session_id, "user", "")
        with self.assertRaises(ValueError):
            self.workbench.add_message(session.session_id, "user", "x" * 20_001)

    def test_freeze_requires_a_prompt_and_records_hash(self) -> None:
        empty = self.workbench.create()
        with self.assertRaises(ValueError):
            self.workbench.freeze_implementation(empty.session_id)
        session = self.workbench.create("Change one thing")
        frozen = self.workbench.freeze_implementation(session.session_id)
        self.assertEqual(len(frozen.frozen_implementation_sha256), 64)
        self.assertEqual(frozen.status, "implementation_ready")

    def test_dispatch_requires_explicit_authorization(self) -> None:
        session = self.workbench.freeze_implementation(self.workbench.create("Change one thing").session_id)
        with self.assertRaises(PermissionError):
            self.workbench.dispatch_implementation(session.session_id, runner)

    def test_lifecycle_order_fails_closed(self) -> None:
        session = self.workbench.create("Change one thing")
        with self.assertRaises(RuntimeError):
            self.workbench.review(session.session_id, runner, authorize=True)
        session = self.workbench.freeze_implementation(session.session_id)
        with self.assertRaises(RuntimeError):
            self.workbench.dispatch_audit(session.session_id, runner, authorize=True)

    def test_consultation_updates_the_draft(self) -> None:
        session = self.workbench.create("Initial request")
        session = self.workbench.consult(session.session_id, runner, authorize=True)
        self.assertEqual(session.conversation[-1]["role"], "assistant")
        self.assertIn("Initial request", session.implementation_prompt_draft)

    def test_full_lifecycle_is_durable(self) -> None:
        session = self.workbench.create("Add a safe export")
        session = self.workbench.freeze_implementation(session.session_id)
        session = self.workbench.dispatch_implementation(session.session_id, runner, authorize=True)
        self.assertEqual(session.status, "implementation_complete")
        session = self.workbench.review(session.session_id, runner, authorize=True)
        self.assertEqual(session.status, "review_complete")
        self.assertTrue(session.audit_prompt_draft)
        session = self.workbench.freeze_audit(session.session_id)
        self.assertEqual(len(session.frozen_audit_sha256), 64)
        session = self.workbench.dispatch_audit(session.session_id, runner, authorize=True)
        session = self.workbench.synthesize(session.session_id, runner, authorize=True)
        self.assertEqual(session.status, "synthesis_complete")
        self.assertEqual(self.workbench.require(session.session_id).status, "synthesis_complete")

    def test_runner_must_return_bounded_json(self) -> None:
        session = self.workbench.freeze_implementation(self.workbench.create("Change one thing").session_id)
        with self.assertRaises(TypeError):
            self.workbench.dispatch_implementation(session.session_id, lambda _p, _q: "not a dict", authorize=True)
        with self.assertRaises(ValueError):
            self.workbench.dispatch_implementation(
                session.session_id,
                lambda _p, _q: {"raw_output": "x" * 901_000},
                authorize=True,
            )

    def test_event_journal_contains_evidence_not_prompt_content(self) -> None:
        session = self.workbench.create("private request marker")
        journal = (self.root / session.session_id / "events.jsonl").read_text(encoding="utf-8")
        self.assertNotIn("private request marker", journal)
        record = json.loads(journal.splitlines()[0])
        self.assertEqual(len(record["artifact_sha256"]), 64)

    def test_unknown_session_is_reported(self) -> None:
        with self.assertRaises(KeyError):
            self.workbench.require("change-000000000000")


class StoreTests(unittest.TestCase):
    def test_invalid_ids_and_artifact_names_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = SessionStore(Path(temporary))
            with self.assertRaises(ValueError):
                store.load("../escape")
            with self.assertRaises(ValueError):
                store.artifact("change-000000000000", "../bad", {}, phase="test", status="bad")

    def test_list_returns_saved_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workbench = ChangeWorkbench(Path(temporary))
            created = workbench.create("One")
            self.assertEqual([session.session_id for session in workbench.store.list()], [created.session_id])


if __name__ == "__main__":
    unittest.main()
