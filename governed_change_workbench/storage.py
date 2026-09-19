"""Contained, atomic persistence and value-minimizing event evidence."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import ChangeSession, PhaseEvidence


SESSION_ID = re.compile(r"^change-[a-f0-9]{12}$")
ARTIFACT_NAME = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,79}$")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


class SessionStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _session_root(self, session_id: str) -> Path:
        if not SESSION_ID.fullmatch(session_id):
            raise ValueError("Invalid session id.")
        candidate = (self.root / session_id).resolve()
        if candidate.parent != self.root:
            raise ValueError("Session path escaped the store root.")
        return candidate

    def list(self) -> list[ChangeSession]:
        sessions: list[ChangeSession] = []
        for path in self.root.iterdir():
            if path.is_dir() and SESSION_ID.fullmatch(path.name):
                try:
                    sessions.append(self.load(path.name))
                except (FileNotFoundError, ValueError, json.JSONDecodeError):
                    continue
        return sorted(sessions, key=lambda item: item.updated_at, reverse=True)

    def load(self, session_id: str) -> ChangeSession:
        path = self._session_root(session_id) / "session.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        session = ChangeSession.from_payload(payload)
        if session.session_id != session_id:
            raise ValueError("Session identity does not match its directory.")
        return session

    def save(self, session: ChangeSession) -> Path:
        session.updated_at = now()
        session.revision += 1
        path = self._session_root(session.session_id) / "session.json"
        payload = json.dumps(session.to_payload(), indent=2, ensure_ascii=False, sort_keys=True).encode("utf-8") + b"\n"
        _atomic_bytes(path, payload)
        return path

    def artifact(self, session_id: str, name: str, payload: Any, *, phase: str, status: str) -> PhaseEvidence:
        if not ARTIFACT_NAME.fullmatch(name):
            raise ValueError("Invalid artifact name.")
        encoded = (
            payload.encode("utf-8")
            if isinstance(payload, str)
            else json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True).encode("utf-8") + b"\n"
        )
        if len(encoded) > 1_000_000:
            raise ValueError("Artifact exceeds the one-megabyte safety bound.")
        path = self._session_root(session_id) / "artifacts" / name
        _atomic_bytes(path, encoded)
        evidence = PhaseEvidence(
            phase=phase,
            status=status,
            result_type="text" if isinstance(payload, str) else type(payload).__name__,
            result_bytes=len(encoded),
            artifact_sha256=hashlib.sha256(encoded).hexdigest(),
        )
        self._append_event(session_id, evidence)
        return evidence

    def _append_event(self, session_id: str, evidence: PhaseEvidence) -> None:
        path = self._session_root(session_id) / "events.jsonl"
        record = {
            "timestamp": now(),
            "phase": evidence.phase,
            "status": evidence.status,
            "result_type": evidence.result_type,
            "result_bytes": evidence.result_bytes,
            "artifact_sha256": evidence.artifact_sha256,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(record, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
