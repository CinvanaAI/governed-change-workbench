import json
import subprocess
import sys

import pytest

from governed_change_workbench import ChangeWorkbench, RunnerFailedError


def success(phase, prompt):
    return {"run_outcome": "complete", "raw_output": "Synthetic successful result."}


def prepare(workbench, phase):
    session = workbench.create("A synthetic change.")
    if phase == "conversation":
        return session, workbench.consult
    session = workbench.freeze_implementation(session.session_id)
    if phase == "implementation":
        return session, workbench.dispatch_implementation
    session = workbench.dispatch_implementation(session.session_id, success, authorize=True)
    if phase == "review":
        return session, workbench.review
    session = workbench.review(session.session_id, success, authorize=True)
    session = workbench.freeze_audit(session.session_id)
    if phase == "audit":
        return session, workbench.dispatch_audit
    session = workbench.dispatch_audit(session.session_id, success, authorize=True)
    return session, workbench.synthesize


@pytest.mark.parametrize("phase", ["conversation", "implementation", "review", "audit", "synthesis"])
def test_failed_phase_does_not_advance_and_retry_preserves_evidence(tmp_path, phase):
    workbench = ChangeWorkbench(tmp_path)
    session, dispatch = prepare(workbench, phase)
    failure = {"run_outcome": "failed", "raw_output": "No changes made."}
    for _ in range(2):
        with pytest.raises(RunnerFailedError):
            dispatch(session.session_id, lambda p, q: failure, authorize=True)
        assert workbench.require(session.session_id).status == session.status
    artifacts = list((tmp_path / session.session_id / "artifacts").glob(f"{phase}_failed_*.json"))
    assert len(artifacts) == 2
    assert all(json.loads(path.read_text()) == failure for path in artifacts)
    result = dispatch(session.session_id, success, authorize=True)
    assert result.status == ("conversation" if phase == "conversation" else f"{phase}_complete")
    assert all(path.exists() for path in artifacts)


@pytest.mark.parametrize("result", [{}, {"run_outcome": "unknown"}, {"run_outcome": []}, {"run_outcome": "complete", "bad": float('nan')}])
def test_invalid_result_does_not_complete(tmp_path, result):
    workbench = ChangeWorkbench(tmp_path)
    session, dispatch = prepare(workbench, "implementation")
    with pytest.raises((ValueError, TypeError)):
        dispatch(session.session_id, lambda p, q: result, authorize=True)
    assert workbench.require(session.session_id).status == "implementation_ready"
    assert len(list((tmp_path / session.session_id / "artifacts").glob("implementation_failed_*.json"))) == 1


def test_runner_exception_records_type_without_private_message(tmp_path):
    workbench = ChangeWorkbench(tmp_path)
    session, dispatch = prepare(workbench, "implementation")
    def fail(phase, prompt):
        raise OSError("private-message-marker")
    with pytest.raises(OSError):
        dispatch(session.session_id, fail, authorize=True)
    evidence = next((tmp_path / session.session_id / "artifacts").glob("implementation_failed_*.json"))
    assert "private-message-marker" not in evidence.read_text()
    assert json.loads(evidence.read_text())["error_type"] == "OSError"
    assert workbench.require(session.session_id).status == "implementation_ready"


def test_documented_module_command_executes_complete_demo(tmp_path):
    run = subprocess.run([sys.executable, "-m", "governed_change_workbench.cli", str(tmp_path)], capture_output=True, text=True, check=True)
    output = json.loads(run.stdout)
    assert output["status"] == "synthesis_complete"
    assert (tmp_path / output["session_id"] / "session.json").is_file()
