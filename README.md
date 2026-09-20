# Governed Change Workbench

Keep a proposed change, the exact instructions approved for execution, and the later review/audit evidence in a persistent sequence. The important distinction is between **talking about a change, freezing its input, dispatching it, and recording what came back**.

This came from the transcript evaluator's change-workbench subsystem. The public library keeps its state/evidence mechanism while leaving the old UI, database integration and provider inventory behind. [Origin](ORIGIN.md)

## Follow a whole lifecycle

Python 3.11+, from this checkout:

```sh
python -m pip install -e .
python -m examples.lifecycle
python -m governed_change_workbench.cli ./demo-sessions
python -m pip install pytest
python -m pytest -q
```

[The walkthrough](examples/lifecycle.py) uses a temporary local store and a synthetic runner. [Its captured output](examples/lifecycle-result.json) contains all dispatched prompts/results, the phase sequence, a refused unauthorized call, a failed attempt preserved across a new service instance, and the successful retry. No project is changed.

The CLI retains a fresh synthetic session under `demo-sessions/change-.../`. Inspect `session.json`, `events.jsonl` and `artifacts/`; they show the stored session, artifact hashes, and exact frozen inputs/results.

## State and evidence

| Current state | Operation | Next state |
| --- | --- | --- |
| conversation | Freeze implementation prompt | implementation_ready |
| implementation_ready | Authorized completed implementation | implementation_complete |
| implementation_complete | Authorized completed review | review_complete |
| review_complete | Freeze audit prompt | audit_ready |
| audit_ready | Authorized completed audit | audit_complete |
| audit_complete | Authorized completed synthesis | synthesis_complete |

[service.py](governed_change_workbench/service.py) checks these transitions. Freeze captures the prompt and its SHA-256. A runner receives `(phase, prompt)` and must return a JSON-serializable dictionary with `run_outcome: "complete"` or `"failed"`. Failed/invalid results retain failure evidence and keep the phase retryable. Authorization is required per dispatch; it is a caller's explicit choice, not user authentication.

## Connect a runner

```python
from pathlib import Path
from governed_change_workbench import ChangeWorkbench

workbench = ChangeWorkbench(Path("example-sessions"))
session = workbench.create("Review a synthetic greeting change.")
workbench.freeze_implementation(session.session_id)
def runner(phase, prompt):
    return {"run_outcome": "complete", "raw_output": "Synthetic response only."}
result = workbench.dispatch_implementation(session.session_id, runner, authorize=True)
assert result.status == "implementation_complete"
```

Replace that callable with a separately controlled executor or reviewer. “Complete” is the runner's report, not independent proof that files changed or tests passed. The library neither grants a sandbox nor checks a real codebase.

## Persistence boundaries

[storage.py](governed_change_workbench/storage.py) contains session paths, replaces individual files atomically and appends hash/size events. A whole phase spans multiple files; it is not a transaction. Use one coordinator per store. Raw conversation and runner artifacts can contain private text even though event rows minimize values.

The [older retry example](examples/failure_and_retry.py) also works and deliberately leaves its temporary evidence directory for inspection. The new lifecycle example cleans its disposable store.

A useful next step is crash recovery across the artifact/session/event boundary, with explicit recovery rules rather than assuming an atomic file write makes a whole phase atomic.

[Mechanism](docs/MECHANISM.md) · [Failure tests](tests/test_failed_phases.py) · [Security](SECURITY.md) · [License](LICENSE.md)
