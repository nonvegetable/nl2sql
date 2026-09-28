# NL2SQL Enterprise Engine (with Agentic Self-Correction)

A robust, database-agnostic data pipeline that translates natural language questions into executable SQL queries, runs them securely against a relational database, and automatically visualizes the results.

This project is designed to be **model-agnostic** and **database-agnostic**. The default local stack is **LM Studio** (OpenAI-compatible API on `localhost:1234`). Ollama, OpenAI, Anthropic (Claude), and Gemini remain fully supported. The application supports both the built-in mock PostgreSQL database and your own PostgreSQL/MySQL databases, whether hosted locally or remotely.

## Production application path

The repository now contains a Tauri 2 desktop shell in `desktop/` and a versioned local engine API in `engine/`. The existing Streamlit dashboard remains available as a migration/demo surface. The engine validates every query with SQLGlot before execution, uses pooled SQLAlchemy connections, and exposes `/api/v1` health, connection, schema, query, and history endpoints.

Run the engine with `uvicorn engine.api:app --host 127.0.0.1 --port 47821`, then start the desktop frontend with `cd desktop && npm install && npm run dev`. See `docs/architecture.md`, `docs/security.md`, and `docs/releasing.md` for the current boundaries and packaging workflow. The desktop sidecar, secure credential storage, signed updates, and cross-platform CI are release work still to be completed; they are not represented as finished features here.

---

# Features

## Multi-LLM Routing

Instantly switch between local AI models (LM Studio by default, or Ollama) and cloud providers (OpenAI, Claude, Gemini) directly from the dashboard. Local runtimes list the models actually available on the machine. Cloud providers ask for an API key, then list that account's chat models so you can pick one.

## Agentic Self-Correction Loop

If the LLM generates invalid SQL, the backend automatically:

1. Executes the query safely.
2. Catches any SQL exceptions.
3. Extracts the error message.
4. Sends the error back to the LLM.
5. Generates a corrected SQL query.
6. Retries execution automatically.

This significantly improves reliability while reducing manual intervention.

## Dynamic Schema Vectorization

The application uses **ChromaDB** to semantically index your database schema.

Instead of exposing the entire schema to the LLM, only the most relevant tables and columns are retrieved based on the user's question, which:

* Reduces token usage
* Improves SQL accuracy
* Minimizes hallucinations
* Scales to enterprise-sized databases

## Bring Your Own Database (BYOD)

Connect to any PostgreSQL or MySQL database (local or remote) directly from the Streamlit UI without modifying the source code.

---

# Getting Started (Docker Deployment)

The easiest and most reliable way to run the project is with Docker.

The included `docker-compose.yml` starts:

* Streamlit frontend
* Python backend
* PostgreSQL sandbox database

## Prerequisites

* Docker Desktop installed and running
* **LM Studio** installed and serving a local model (default for this project)
* *(Optional)* Ollama, if you prefer that local runtime instead of LM Studio

---

## Step 1 — Clone the Repository

```bash
git clone https://github.com/yourusername/nl2sql.git
cd nl2sql
```

---

## Step 2 — Configure Environment Variables

Duplicate the example environment file:

```bash
cp .env.example .env
```

Open `.env` and configure your providers.

### Cloud Models

You can paste an API key in the Streamlit sidebar when you select OpenAI, Claude (Anthropic), or Gemini. The dashboard then lists chat models for that key and asks which one to use. Keys stay in the current session unless you also put them in `.env`:

```text
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=
```

### Local LM Studio (Default)

No API keys are required. Start the local server and load any chat model you already have installed:

```bash
lms server start
lms load google/gemma-4-e2b
```

The dashboard queries port 1234 and uses **whatever chat model is currently loaded**. If nothing is loaded, it shows an error telling you to load one. Embedding models (like nomic-embed) are not listed as generation models.

Ensure the following values are set:

```text
LLM_PROVIDER=lmstudio
LM_STUDIO_BASE_URL=http://localhost:1234/v1
EMBEDDING_PROVIDER=lmstudio
EMBEDDING_MODEL_NAME=text-embedding-nomic-embed-text-v1.5
```

`LLM_MODEL_NAME` is optional. If you set it, it is only used when that model is already loaded; otherwise the loaded model on port 1234 is used.

Schema embeddings use LM Studio's bundled **nomic-embed-text-v1.5**. After switching from Ollama embeddings, re-run **Sync Schema to Vector DB** so Chroma is rebuilt with the new embedding space.

### Local Ollama (optional)

Switch the provider to **Ollama** in the sidebar. The dashboard queries `http://localhost:11434` (or `OLLAMA_HOST`) and asks which pulled chat model to use. If Ollama is not running, or no chat model is pulled, it shows an error telling you what to do:

```bash
ollama serve
ollama pull llama3.2
```

Optional `.env` values:

```text
LLM_PROVIDER=ollama
OLLAMA_HOST=http://localhost:11434
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL_NAME=mxbai-embed-large
```

---

## Step 3 — Launch the Application

Build and start the containers:

```bash
docker-compose up --build
```

Once everything starts successfully, open:

```text
http://localhost:8501
```

---

# Using Your Own Database

By default, Docker connects to the included PostgreSQL sandbox.

You can instead connect to your own database hosted:

* Locally
* AWS RDS
* Neon
* Supabase
* DigitalOcean
* Azure
* Google Cloud SQL
* Any VPS

The backend uses **SQLAlchemy** with the appropriate database driver (e.g., `psycopg2`) to establish a secure TCP/IP connection.

---

## 1. Configure Network Access

For remote databases:

* Allow incoming connections from the machine running this application.
* Whitelist the IP address in your firewall or cloud security group.
* If SSL is required, append:

```text
?sslmode=require
```

to your PostgreSQL connection string.

---

## 2. Connect Through the Dashboard

Open the Streamlit sidebar and select:

```
Database Connection
→ Manual Configuration
```

Enter:

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