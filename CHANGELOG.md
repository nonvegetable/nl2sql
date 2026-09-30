# Changelog

## v0.2.0-beta

Beta desktop release for testing and feedback.

### Highlights

- Desktop beta shell with real Overview, Query, Connections, Schema, History, Providers, and Settings views
- Dynamic localhost-only engine startup with a production-safe Tauri CSP and sidecar readiness handling
- Persistent local metadata, per-connection schema state, and query history without storing plaintext credentials
- SQLite and PostgreSQL as the supported and tested database paths in this beta
- Connection management with secure secret storage, test/save/delete flows, and schema synchronization
- Deterministic schema retrieval plus lexical/metadata ranking with safe fallback when vector retrieval is unavailable
- SQLGlot-based read-only validation, execution limits, truncation warnings, and history status tracking
- Cross-platform GitHub Actions and packaging workflow updates for the beta release

### Known Limitations

- MySQL/MariaDB and SQL Server are supported architecturally but are not fully covered by this beta test matrix unless the CI environment provides the services.
- Oracle and BigQuery remain planned adapters and are not production-tested.
- Code signing and notarization are not configured for the desktop bundles.
- Automatic app updates are not configured.
- Local model management is still external to the application; configure LM Studio, Ollama, or a cloud provider before live generation.
- This beta is suitable for testing and feedback, not an unqualified production guarantee.
