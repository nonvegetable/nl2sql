# NL2SQL Enterprise Engine (with Agentic Self-Correction)

A robust, database-agnostic data pipeline that translates natural language questions into executable SQL queries, runs them securely against a relational database, and automatically visualizes the results.

This project is designed to be **model-agnostic** and **database-agnostic**. You can run it entirely locally for free using Ollama or plug in commercial LLM providers such as OpenAI, Anthropic (Claude), and Gemini. The application supports both the built-in mock PostgreSQL database and your own PostgreSQL/MySQL databases, whether hosted locally or remotely.

---

# Features

## Multi-LLM Routing

Instantly switch between local AI models (via Ollama) and cloud providers (OpenAI, Claude, Gemini) directly from the dashboard.

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
* *(Optional but recommended)* Ollama installed if you want to run everything locally without API costs

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

Add one or more API keys:

```text
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=
```

### Local Ollama (Default)

No API keys are required.

Ensure the following values are set:

```text
LLM_PROVIDER=ollama
EMBEDDING_PROVIDER=ollama
```

---

## Step 3 — Install Local Models (Ollama Users)

Pull the language model used for SQL generation:

```bash
ollama pull qwen3:4b
```

Pull the embedding model used for schema vectorization:

```bash
ollama pull mxbai-embed-large
```

---

## Step 4 — Launch the Application

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
* **Embeddings:** Ollama / OpenAI / Gemini
* **LLMs:** Ollama, OpenAI, Claude, Gemini
* **Database Support:** PostgreSQL, MySQL
* **Containerization:** Docker & Docker Compose