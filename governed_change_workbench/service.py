"""State-guarded orchestration for conversation, implementation, review, audit, and synthesis."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from pathlib import Path
from typing import Callable

from .models import ChangeSession
from .storage import SessionStore, now


Runner = Callable[[str, str], dict]


class RunnerFailedError(RuntimeError):
    """The runner reported failure; evidence was saved and the phase is retryable."""


def derive_title(message: str) -> str:
    compact = re.sub(r"\s+", " ", message.strip())
    return compact[:72] or "Untitled Change Session"


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _result_text(result: dict) -> str:
    for key in ("raw_output", "summary", "message"):
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


class ChangeWorkbench:
    def __init__(self, root: Path) -> None:
        self.store = SessionStore(root)

    def create(self, seed_message: str = "") -> ChangeSession:
        session = ChangeSession(
            session_id="change-" + uuid.uuid4().hex[:12],
            title=derive_title(seed_message),
            status="conversation",
            created_at=now(),
            updated_at=now(),
        )
        self.store.save(session)
        if seed_message.strip():
            return self.add_message(session.session_id, "user", seed_message)
        return session

    def require(self, session_id: str) -> ChangeSession:
        try:
            return self.store.load(session_id)
        except FileNotFoundError as exc:
            raise KeyError(f"Unknown change session: {session_id}") from exc

    def add_message(self, session_id: str, role: str, content: str) -> ChangeSession:
        session = self.require(session_id)
        self._require_status(session, "conversation")
        role = role.strip().casefold()
        content = content.strip()
        if role not in {"user", "assistant"}:
            raise ValueError("role must be user or assistant")
        if not content or len(content) > 20_000:
            raise ValueError("message must contain between 1 and 20,000 characters")
        if len(session.conversation) >= 200:
            raise ValueError("session message limit reached")
        session.conversation.append({"role": role, "content": content})
        if session.title == "Untitled Change Session" and role == "user":
            session.title = derive_title(content)
        self._update_drafts(session)
        self.store.artifact(session_id, "conversation.json", session.conversation, phase="conversation", status="updated")
        self.store.save(session)
        return session

    def consult(self, session_id: str, runner: Runner, *, authorize: bool = False) -> ChangeSession:
        session = self.require(session_id)
        self._require_status(session, "conversation")
        result = self._invoke(session, runner, "conversation", self._conversation_prompt(session), authorize)
        text = _result_text(result)
        if text:
            session.conversation.append({"role": "assistant", "content": text[:20_000]})
            self._update_drafts(session)
        self.store.artifact(session_id, "consultation.json", result, phase="conversation", status="complete")
        self.store.save(session)
        return session

    def freeze_implementation(self, session_id: str) -> ChangeSession:
        session = self.require(session_id)
        self._require_status(session, "conversation")
        prompt = session.implementation_prompt_draft.strip()
        if not prompt:
            raise ValueError("Implementation prompt is empty.")
        session.frozen_implementation_prompt = prompt
        session.frozen_implementation_sha256 = _digest(prompt)
        session.status = "implementation_ready"
        self.store.artifact(session_id, "implementation_prompt.txt", prompt, phase="implementation", status="frozen")
        self.store.save(session)
        return session

    def dispatch_implementation(self, session_id: str, runner: Runner, *, authorize: bool = False) -> ChangeSession:
        session = self.require(session_id)
        self._require_status(session, "implementation_ready")
        result = self._invoke(session, runner, "implementation", session.frozen_implementation_prompt, authorize)
        session.implementation_result = result
        session.status = "implementation_complete"
        self.store.artifact(session_id, "implementation_result.json", result, phase="implementation", status="complete")
        self.store.save(session)
        return session

    def review(self, session_id: str, runner: Runner, *, authorize: bool = False) -> ChangeSession:
        session = self.require(session_id)
        self._require_status(session, "implementation_complete")
        result = self._invoke(session, runner, "review", self._review_prompt(session), authorize)
        session.review_notes = _result_text(result)
        session.audit_prompt_draft = self._audit_prompt(session)
        session.status = "review_complete"
        self.store.artifact(session_id, "review_result.json", result, phase="review", status="complete")
        self.store.artifact(session_id, "audit_prompt_draft.txt", session.audit_prompt_draft, phase="audit", status="draft")
        self.store.save(session)
        return session

    def freeze_audit(self, session_id: str) -> ChangeSession:
        session = self.require(session_id)
        self._require_status(session, "review_complete")
        prompt = session.audit_prompt_draft.strip()
        if not prompt:
            raise ValueError("Audit prompt is empty.")
        session.frozen_audit_prompt = prompt
        session.frozen_audit_sha256 = _digest(prompt)
        session.status = "audit_ready"
        self.store.artifact(session_id, "audit_prompt.txt", prompt, phase="audit", status="frozen")
        self.store.save(session)
        return session

    def dispatch_audit(self, session_id: str, runner: Runner, *, authorize: bool = False) -> ChangeSession:
        session = self.require(session_id)
        self._require_status(session, "audit_ready")
        result = self._invoke(session, runner, "audit", session.frozen_audit_prompt, authorize)
        session.audit_result = result
        session.status = "audit_complete"
        self.store.artifact(session_id, "audit_result.json", result, phase="audit", status="complete")
        self.store.save(session)
        return session

    def synthesize(self, session_id: str, runner: Runner, *, authorize: bool = False) -> ChangeSession:
        session = self.require(session_id)
        self._require_status(session, "audit_complete")
        result = self._invoke(session, runner, "synthesis", self._synthesis_prompt(session), authorize)
        session.synthesis_summary = _result_text(result)
        if session.synthesis_summary:
            session.conversation.append({"role": "assistant", "content": session.synthesis_summary[:20_000]})
        session.status = "synthesis_complete"
        self.store.artifact(session_id, "synthesis_result.json", result, phase="synthesis", status="complete")
        self.store.save(session)
        return session

    def _invoke(self, session: ChangeSession, runner: Runner, phase: str, prompt: str, authorize: bool) -> dict:
        if not authorize:
            raise PermissionError(f"{phase} dispatch requires explicit authorization")
        try:
            result = runner(phase, prompt)
            if not isinstance(result, dict):
                raise TypeError("runner must return a dictionary")
            try:
                size = len(json.dumps(result, ensure_ascii=False, allow_nan=False).encode("utf-8"))
            except (TypeError, ValueError) as exc:
                raise ValueError("runner result must be JSON serializable") from exc
            if size > 900_000:
                raise ValueError("runner result exceeds the 900-kilobyte bound")
            if result.get("run_outcome") not in {"complete", "failed"}:
                raise ValueError("runner run_outcome must be complete or failed")
        except Exception as error:
            # Invalid results and exceptions may contain arbitrary private objects.
            # Persist their type, not their repr or message, and keep this phase ready.
            self._failed_attempt(session, phase, {"run_outcome": "failed", "error_type": type(error).__name__})
            raise
        if result["run_outcome"] == "failed":
            self._failed_attempt(session, phase, result)
            raise RunnerFailedError(f"{phase} runner reported failure; phase did not advance")
        return result

    def _failed_attempt(self, session: ChangeSession, phase: str, result: dict) -> None:
        # Each attempt has its own artifact so retrying never erases failed evidence.
        name = f"{phase}_failed_{uuid.uuid4().hex}.json"
        self.store.artifact(session.session_id, name, result, phase=phase, status="failed")
        warning = f"{phase} attempt failed; see artifacts/{name}"
        session.warnings.append(warning)
        self.store.save(session)

    @staticmethod
    def _require_status(session: ChangeSession, expected: str) -> None:
        if session.status != expected:
            raise RuntimeError(f"Expected status {expected}, found {session.status}.")

    @staticmethod
    def _update_drafts(session: ChangeSession) -> None:
        user_messages = [item["content"] for item in session.conversation if item["role"] == "user"]
        session.intent_summary = "No user intent captured yet." if not user_messages else "Current requested change:\n- " + "\n- ".join(user_messages[-3:])
        latest = user_messages[-1] if user_messages else "No direct request captured."
        session.implementation_prompt_draft = (
            "Implement the following change in the supplied project boundary.\n\n"
            f"Intent summary:\n{session.intent_summary}\n\n"
            f"Most recent request:\n{latest}\n\n"
            "Required evidence:\n"
            "- identify files or artifacts changed;\n"
            "- report validation performed;\n"
            "- distinguish observed results from assumptions;\n"
            "- report remaining risks and do not claim completion without evidence.\n"
        )

    @staticmethod
    def _conversation_prompt(session: ChangeSession) -> str:
        transcript = "\n".join(f"{item['role'].upper()}: {item['content']}" for item in session.conversation)
        return f"Refine this requested change without executing it.\n\nIntent:\n{session.intent_summary}\n\nConversation:\n{transcript}"

    @staticmethod
    def _review_prompt(session: ChangeSession) -> str:
        return (
            "Review the implementation evidence against the frozen requested change. Identify omissions, weak claims, risks, and likely regressions.\n\n"
            f"Frozen prompt SHA-256: {session.frozen_implementation_sha256}\n"
            f"Frozen prompt:\n{session.frozen_implementation_prompt}\n\n"
            f"Implementation result:\n{json.dumps(session.implementation_result, indent=2, ensure_ascii=False)}\n"
        )

    @staticmethod
    def _audit_prompt(session: ChangeSession) -> str:
        return (
            "Independently audit the implementation and the review. Focus on correctness, regressions, unsupported assumptions, and unverified completion claims.\n\n"
            f"Intent:\n{session.intent_summary}\n\nReview findings:\n{session.review_notes or 'No review notes captured.'}\n"
        )

    @staticmethod
    def _synthesis_prompt(session: ChangeSession) -> str:
        return (
            "Return a concise evidence-grounded conclusion: what changed, what is verified, what remains weak, warnings, and the best next step.\n\n"
            f"Intent:\n{session.intent_summary}\n\nReview:\n{session.review_notes}\n\n"
            f"Audit:\n{json.dumps(session.audit_result, indent=2, ensure_ascii=False)}\n"
        )
