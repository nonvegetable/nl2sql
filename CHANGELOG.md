# Changelog

## v0.1.0-alpha

Alpha release for testing and feedback.

### Highlights

- Tauri 2 desktop foundation with a Python sidecar engine
- Persistent connection metadata, schema state, and query history
- OS credential-store boundary for database passwords
- SQLite, PostgreSQL, MySQL/MariaDB, and SQL Server adapter architecture
- Connection wizard, schema synchronization, and SQL editing
- Natural-language SQL generation boundary with mock/provider support
- Connection-scoped schema retrieval and Chroma vector-store interface
- SQLGlot read-only validation, row limits, and bounded result materialization
- Linux, Windows, and macOS release workflow definitions

### Known Limitations

- Oracle and BigQuery are planned adapters and are not production-tested in this alpha.
- Code signing and notarization credentials are not configured.
- Automatic application updates are not configured.
- A model download manager is not included; configure an external provider such as LM Studio, Ollama, OpenAI, Anthropic, or Gemini.
- Live LLM generation requires provider configuration and credentials or a running local provider.
- Linux packaging is locally verifiable; Windows and macOS artifacts require their respective GitHub-hosted runners.
