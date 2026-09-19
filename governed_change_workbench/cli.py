"""Run the deterministic evidence demo without configuring a provider."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .service import ChangeWorkbench


def _runner(phase: str, prompt: str) -> dict:
    return {
        "run_outcome": "complete",
        "raw_output": f"Deterministic {phase} evidence for a {len(prompt)}-character prompt.",
        "runner": "offline-demo",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a complete offline governed change-workbench run.")
    parser.add_argument("root", type=Path, help="Empty or existing local session store")
    parser.add_argument("--request", default="Add a bounded export command and verify it.")
    args = parser.parse_args()
    workbench = ChangeWorkbench(args.root)
    session = workbench.create(args.request)
    session = workbench.freeze_implementation(session.session_id)
    session = workbench.dispatch_implementation(session.session_id, _runner, authorize=True)
    session = workbench.review(session.session_id, _runner, authorize=True)
    session = workbench.freeze_audit(session.session_id)
    session = workbench.dispatch_audit(session.session_id, _runner, authorize=True)
    session = workbench.synthesize(session.session_id, _runner, authorize=True)
    print(json.dumps({"session_id": session.session_id, "status": session.status, "revision": session.revision}, indent=2))


if __name__ == "__main__":
    main()
