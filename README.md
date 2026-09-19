# Governed Change Workbench

A file-backed coordinator for a change request’s implementation, review, audit and synthesis. It freezes phase inputs, requires explicit dispatch authorization, and keeps the resulting records available after the conversation moves on.

## Try it

Python 3.11 or newer.

```sh
python -m pip install -e .
python -m governed_change_workbench.cli ./demo-sessions
python -m examples.failure_and_retry
```

The first command creates a complete synthetic lifecycle and prints a session ID with `status: synthesis_complete`. The second returns `after_failure: implementation_ready`, `after_retry: implementation_complete`, and `preserved_failures: 1`. Its failed-attempt artifact remains after the successful retry.

## How it works

Freezing the exact inputs and preserving stage evidence makes a handoff inspectable after the conversation has moved on. Read the [mechanism and implementation notes](docs/MECHANISM.md) for the specific boundaries and source links.

## Scope

A runner is a callable `(phase, prompt) -> dict`; [failure_and_retry.py](examples/failure_and_retry.py) is a complete small adapter example. “Complete” is a reported runner outcome. The workbench does not independently prove code correctness, authenticate users or sandbox the runner. Run one coordinator per local store.

## Verify

`python -m pytest` runs the behavior tests (install `pytest` first). The runnable example above provides a separate first-use check.

MIT licensed; see [LICENSE.md](LICENSE.md). Origin and release boundaries are documented in [ORIGIN.md](ORIGIN.md) and [SECURITY.md](SECURITY.md).
## Inspect the example result

Open the [saved synthetic result](examples/captured-result.json) alongside its [input and demonstration](examples/failure_and_retry.py). The result is from the bundled synthetic example; local machine paths and temporary run identifiers are excluded from public projections.
