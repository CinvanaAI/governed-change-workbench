# Origin

This package was extracted from the `change_workbench` subsystem of the March 2026 Transcript Model Evaluator.

The source subsystem already modeled a durable conversation, implementation prompt, provider execution, review, audit, and synthesis session with saved artifacts. The public extraction removes the application database, Tk UI, provider inventory, live run evidence, and model configuration.

The extraction strengthens the boundary with explicit state guards, authorization gates, atomic session/artifact writes, contained identifiers, frozen-prompt hashes, bounded JSON results, injectable runners, a value-minimizing event journal, and deterministic tests.
