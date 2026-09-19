# Governed Change Workbench: mechanism

[ChangeWorkbench](../governed_change_workbench/service.py) enforces phase order and requires each runner to return JSON with `run_outcome: "complete"` or `"failed"`. A failed result raises `RunnerFailedError`, saves a unique failed-attempt artifact and leaves the current phase ready to retry. Invalid results and exceptions save their error type without serializing arbitrary exception messages. [SessionStore](../governed_change_workbench/storage.py) persists session snapshots, artifacts and a value-minimizing event journal.

## Limits that matter

A runner is a callable `(phase, prompt) -> dict`; [failure_and_retry.py](../examples/failure_and_retry.py) is a complete small adapter example. “Complete” is a reported runner outcome. The workbench does not independently prove code correctness, authenticate users or sandbox the runner. Run one coordinator per local store.

## Demonstration contract

Input: A synthetic change request and an injected phase runner.

Expected observation: A durable synthesis_complete session; explicit failed results remain retryable with saved evidence.

The bundled example uses synthetic material. Its observed output establishes that bounded path, not every possible integration.
