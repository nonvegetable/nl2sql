# NL2SQL
Natural-language database querying desktop application.

NL2SQL is a desktop-first interface for asking natural-language questions against SQLite or PostgreSQL databases, validating the resulting SQL, and executing read-only queries with a controlled results experience. The application runs a local Python engine behind a Tauri shell, keeps database credentials in the OS credential store, and only exposes localhost communication paths for the runtime boundary.

## What the application does

- Converts natural-language questions to SQL with a schema-aware retrieval pipeline
- Validates every generated or edited SQL statement with SQLGlot before execution
- Executes read-only queries against the selected database connection
- Keeps a local history of successful and failed queries with metadata
- Synchronizes schema information for tables, columns, keys, and foreign relationships
- Lets users review and edit generated SQL before running it
- Uses secure storage for passwords and avoids persisting plaintext database credentials

## Desktop architecture

The current desktop beta is built as:

- Tauri shell in the `desktop/` directory
- Local Python engine in `engine/`
- SQLite metadata store with platform-managed data directories
- SQLAlchemy-backed adapters for relational databases
- Safe read-only query validation before execution

The engine is intentionally localhost-only in production. The front end communicates with the actual runtime port allocated by the desktop app, not a fixed port assumption.

## Supported platforms

The beta release targets:

- Linux x64
- Windows x64
- macOS Intel (x64)
- macOS Apple Silicon (arm64)

## Supported databases

Tested in this repository at the beta stage:

- SQLite
- PostgreSQL

Architecturally supported but not fully beta-validated in the CI matrix:

- MySQL
- MariaDB
- SQL Server

Planned:

- Oracle
- BigQuery

## Supported LLM providers

The application supports provider-neutral SQL generation through the configured local or cloud model stack, including:

- OpenAI
- Anthropic
- Gemini
- Ollama
- LM Studio
- OpenAI-compatible endpoints

The application does not bundle model weights and expects a provider or local runtime to already be available.

## Installation

### Desktop app

Download the beta release artifacts from the GitHub Releases page for your platform.

### Local development

```bash
git clone https://github.com/nonvegetable/nl2sql.git
cd nl2sql
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[all]"
uvicorn engine.api:app --host 127.0.0.1 --port 47821
cd desktop
npm ci
npm run dev
```

## Quick start

1. Launch the desktop app.
2. Add a database connection.
3. Test and save the connection.
4. Sync the schema.
5. Ask a question in natural language.
6. Review the generated SQL.
7. Execute the query.
8. Inspect history and results.

## Database connection

The app supports SQLite and PostgreSQL as the beta-validated paths. The connection wizard accepts either a direct SQLAlchemy URL or field-based connection details such as host, port, username, password, database, schema, and SSL settings.

Passwords are kept in the platform credential store and are never persisted in plaintext in the SQLite metadata database. The app never logs credentials and should not expose raw connection URLs containing secrets in the UI or history.

## Schema synchronization

Schema sync collects:

- tables
- columns
- types
- nullability
- primary keys
- foreign keys
- indexes
- views when supported
- catalog and schema metadata when available

The sync process stores a schema fingerprint and keeps a lightweight per-connection schema catalog. It also removes stale entries when objects are deleted or renamed.

## Asking questions

The engine retrieves relevant schema context using lexical metadata and semantic retrieval when available. The question and matched schema are then passed to the configured model for SQL generation. Generated SQL is validated before it is executed.

## SQL review

The generated SQL is visible in the SQL editor before execution. You can inspect, revise, or re-run it manually. The app does not execute arbitrary SQL until validation succeeds.

## Query execution

The SQL validation path is intentionally read-only:

- SELECT, WITH, UNION, INTERSECT, and EXCEPT are allowed
- DML and DDL are rejected
- multiple statements are rejected
- comments are scanned for destructive keywords
- SQLGlot parsing is required before execution

The application keeps row limits and response-size bounds to avoid unbounded result materialization.

## Security model

The application is designed around a read-only SQL boundary. The engine rejects mutation attempts such as INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE, GRANT, REVOKE, MERGE, EXEC, and multiple statements, and it enforces the validation path through SQLGlot AST checks.

Use SELECT-only database credentials in production and never run the app with broader write privileges than required.

## Local models

The app can use local runtimes such as LM Studio or Ollama, or a configured cloud provider. Model availability and status depend on the selected runtime and authentication configuration.

## Development

- Python engine: `engine/`
- Desktop frontend: `desktop/`
- Desktop config: `desktop/src-tauri/`
- Tests: `tests/`
- Docs: `docs/`

## Testing

```bash
python -m pytest -q
cd desktop
npm ci
npm run build
cd src-tauri
cargo check
```

## Building

The repo includes CI and release workflows for building the sidecar and packaging the desktop app. The Linux sidecar is built with PyInstaller and bundled into the Tauri app.

## Known limitations

- This is a beta; it is meant for testing and feedback
- Oracle and BigQuery are not fully tested or supported in this release
- Code signing and notarization are not configured
- Automatic application updates are not configured
- Local model availability depends on external services or providers

## Roadmap

Planned work includes broader integration coverage for MySQL/MariaDB and SQL Server, more robust provider management, and expanded schema and query debugging automation.

## Legacy Streamlit surface

The repository still contains a legacy Streamlit/demo entry surface, but the supported installation and runtime path for the beta is the desktop application. The Streamlit surface is not the primary installation flow.

* Host
* Port (5432 for PostgreSQL)
* Username
* Password
* Database Name

---

## 3. Sync the Database Schema

Click:

```
Sync Schema to Vector DB
```

The application will:

1. Connect to your database.
2. Extract tables, columns, and relationships.
3. Generate embeddings using your configured embedding provider.
4. Store those embeddings inside ChromaDB.

This step enables semantic schema retrieval for accurate SQL generation.

---

## 4. Ask Questions

Once synchronization completes, simply ask questions such as:

> Show me total revenue grouped by payment types for last month.

The engine will:

1. Retrieve the relevant schema context.
2. Generate SQL.
3. Execute it safely.
4. Automatically repair invalid SQL if needed.
5. Display both the results and visualizations.

---

# Security & Guardrails

## Read-Only Database Access

Always connect using database credentials that have **SELECT-only permissions**.

Never provide administrator credentials.

---

## Automatic Error Recovery

If an invalid SQL statement is generated:

* The database rejects it.
* The backend captures the exception.
* The LLM receives the error details.
* A corrected query is generated automatically.
* The corrected query is executed.

The application continues running without crashing.

---

## Protection Against Destructive Queries

Queries such as:

* `DROP`
* `DELETE`
* `UPDATE`
* `ALTER`

should never succeed when using properly configured read-only credentials.

Even if the LLM generates a destructive query, the database blocks execution, the backend logs the failure, and the application remains safe.

---

# Tech Stack

* **Frontend:** Streamlit
* **Backend:** Python
* **Database Connectivity:** SQLAlchemy
* **Vector Database:** ChromaDB
* **Embeddings:** LM Studio / Ollama / OpenAI
* **LLMs:** LM Studio, Ollama, OpenAI, Claude, Gemini
* **Database Support:** PostgreSQL, MySQL
* **Containerization:** Docker & Docker Compose