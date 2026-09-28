# Security

Generated SQL is validated with SQLGlot before execution. Multiple statements and mutation/DDL statements are rejected, and unbounded reads receive a dialect-aware `LIMIT`.

Use a database principal with `SELECT` permissions only. The API does not return connection URLs and query history stores normalized SQL and metadata, never result rows or credentials. API keys and passwords must not be placed in logs, issue reports, or prompts.

The remaining production work is platform secure-storage integration (Windows Credential Manager, macOS Keychain, and Linux Secret Service) and signed updater configuration. Those are release requirements, not enabled claims of this prototype slice.
