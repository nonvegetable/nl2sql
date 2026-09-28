# Architecture

The production path is split into three processes and one shared Python package:

- `desktop/`: React, TypeScript, Vite, and Tauri 2 UI/runtime.
- `engine/`: Python API, pooled SQLAlchemy connections, SQLGlot validation, and provider integrations.
- `legacy`: the current Streamlit experience remains at the repository root during migration.

Tauri launches the packaged `nl2sql-engine` sidecar on loopback. The UI communicates through versioned `/api/v1` endpoints. The engine never executes model output directly: SQL is parsed, checked as a single read-only statement, bounded, and only then sent to SQLAlchemy.

The current API keeps connection records in memory while the persistence and platform credential-store layer is being completed. Public connection responses intentionally omit URLs and secrets.
