# Security

- Session data may contain source code, prompts, review notes, and private product information. Choose the store root deliberately and do not publish runtime sessions by default.
- Every external phase call requires `authorize=True`; this prevents accidental dispatch but is not user authentication.
- The runner is a trust boundary. It owns network credentials, repository permissions, tool access, isolation, and execution safety.
- Runner results must be JSON objects, JSON-serializable, and smaller than 900 kilobytes.
- Session IDs and artifact names cannot contain paths.
- Session and artifact files use atomic replacement. Event records are append-only and flushed, but the journal is not a cryptographically signed log.
- Event records intentionally omit prompt/result values and retain only phase, status, type, size, timestamp, and artifact hash.
- No shell, Git, network, or model adapter is included in this repository.
