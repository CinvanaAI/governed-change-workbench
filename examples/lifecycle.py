"""Show frozen inputs, denied calls, failed retry and full completion offline."""
import hashlib
import json
import tempfile
from pathlib import Path
from governed_change_workbench import ChangeWorkbench, RunnerFailedError

with tempfile.TemporaryDirectory(prefix="change-lifecycle-") as temporary:
    root = Path(temporary)
    workbench = ChangeWorkbench(root)
    session = workbench.create("Add an empty-input check to a synthetic text normalizer.")
    sid = session.session_id
    states = [session.status]
    frozen = workbench.freeze_implementation(sid)
    states.append(frozen.status)
    calls = []
    def complete(phase, prompt):
        result = {"run_outcome": "complete", "raw_output": "Synthetic " + phase + " response; no project was changed."}
        calls.append({"phase": phase, "prompt": prompt, "result": result})
        return result
    try:
        workbench.dispatch_implementation(sid, complete)
    except PermissionError:
        pass
    else:
        raise AssertionError("Unauthorized callback was invoked")
    assert not calls
    try:
        workbench.dispatch_implementation(sid, lambda phase, prompt: {"run_outcome": "failed", "raw_output": "Synthetic failed attempt."}, authorize=True)
    except RunnerFailedError:
        pass
    else:
        raise AssertionError("Failed attempt advanced")
    workbench = ChangeWorkbench(root)
    assert workbench.require(sid).status == "implementation_ready"
    for operation in (workbench.dispatch_implementation, workbench.review):
        states.append(operation(sid, complete, authorize=True).status)
    audit = workbench.freeze_audit(sid)
    states.append(audit.status)
    for operation in (workbench.dispatch_audit, workbench.synthesize):
        states.append(operation(sid, complete, authorize=True).status)
    final = ChangeWorkbench(root).require(sid)
    assert final.status == "synthesis_complete"
    assert hashlib.sha256(calls[0]["prompt"].encode()).hexdigest() == frozen.frozen_implementation_sha256
    assert hashlib.sha256(calls[2]["prompt"].encode()).hexdigest() == audit.frozen_audit_sha256
    failures = list((root / sid / "artifacts").glob("implementation_failed_*.json"))
    assert len(failures) == 1
    print(json.dumps({"states": states, "unauthorized_calls": 0, "failed_attempt_preserved": True,
        "restart_before_retry": True, "frozen_hashes_match_dispatched_text": True,
        "calls": calls, "final_status_after_restart": final.status,
        "real_project_changes": False}, indent=2))
