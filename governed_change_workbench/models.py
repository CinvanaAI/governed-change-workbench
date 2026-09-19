"""Durable domain records for a governed change lifecycle."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class ChangeSession:
    session_id: str
    title: str
    status: str
    created_at: str
    updated_at: str
    revision: int = 0
    conversation: list[dict[str, str]] = field(default_factory=list)
    intent_summary: str = ""
    implementation_prompt_draft: str = ""
    frozen_implementation_prompt: str = ""
    frozen_implementation_sha256: str = ""
    implementation_result: dict[str, Any] = field(default_factory=dict)
    review_notes: str = ""
    audit_prompt_draft: str = ""
    frozen_audit_prompt: str = ""
    frozen_audit_sha256: str = ""
    audit_result: dict[str, Any] = field(default_factory=dict)
    synthesis_summary: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ChangeSession":
        if not isinstance(payload, dict):
            raise ValueError("Session payload must be an object.")
        return cls(
            session_id=str(payload.get("session_id") or ""),
            title=str(payload.get("title") or "Untitled Change Session"),
            status=str(payload.get("status") or "conversation"),
            created_at=str(payload.get("created_at") or ""),
            updated_at=str(payload.get("updated_at") or ""),
            revision=int(payload.get("revision") or 0),
            conversation=[
                {"role": str(item.get("role") or "unknown"), "content": str(item.get("content") or "")}
                for item in payload.get("conversation", [])
                if isinstance(item, dict)
            ],
            intent_summary=str(payload.get("intent_summary") or ""),
            implementation_prompt_draft=str(payload.get("implementation_prompt_draft") or ""),
            frozen_implementation_prompt=str(payload.get("frozen_implementation_prompt") or ""),
            frozen_implementation_sha256=str(payload.get("frozen_implementation_sha256") or ""),
            implementation_result=dict(payload.get("implementation_result") or {}),
            review_notes=str(payload.get("review_notes") or ""),
            audit_prompt_draft=str(payload.get("audit_prompt_draft") or ""),
            frozen_audit_prompt=str(payload.get("frozen_audit_prompt") or ""),
            frozen_audit_sha256=str(payload.get("frozen_audit_sha256") or ""),
            audit_result=dict(payload.get("audit_result") or {}),
            synthesis_summary=str(payload.get("synthesis_summary") or ""),
            warnings=[str(item) for item in payload.get("warnings", []) if str(item).strip()],
        )


@dataclass(frozen=True, slots=True)
class PhaseEvidence:
    phase: str
    status: str
    result_type: str
    result_bytes: int
    artifact_sha256: str
