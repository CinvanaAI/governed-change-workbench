import json
import tempfile
from pathlib import Path

from governed_change_workbench import ChangeWorkbench


def deterministic_runner(phase: str, prompt: str) -> dict:
    return {
        "run_outcome": "complete",
        "raw_output": f"Offline {phase} result for a {len(prompt)}-character prompt.",
        "evidence": {"runner": "deterministic-demo", "phase": phase},
    }


with tempfile.TemporaryDirectory() as temporary:
    workbench = ChangeWorkbench(Path(temporary))
    session = workbench.create("Add a bounded export command and prove it with tests.")
    session = workbench.freeze_implementation(session.session_id)
    session = workbench.dispatch_implementation(session.session_id, deterministic_runner, authorize=True)
    session = workbench.review(session.session_id, deterministic_runner, authorize=True)
    session = workbench.freeze_audit(session.session_id)
    session = workbench.dispatch_audit(session.session_id, deterministic_runner, authorize=True)
    session = workbench.synthesize(session.session_id, deterministic_runner, authorize=True)
    print(json.dumps(session.to_payload(), indent=2))
