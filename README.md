# Natural Language to SQL (NL2SQL) Engine with Self-Correction

A robust, database-agnostic data pipeline that translates natural language questions into executable SQL queries, runs them against a database, and visualizes the results. Built with an agentic self-correction loop, the system automatically catches SQL syntax or execution errors, passes them back to the LLM with the schema context, and repairs the query before rendering the final dashboard.

---

## Architecture & Features

- **Multi-Container Infrastructure:** Orchestrated with Docker Compose to cleanly separate the application tier from the data tier.
- **Database-Agnostic Design:** Boots instantly as a stateless service. Users can dynamically connect their own databases via the UI sidebar, or rely on the pre-configured production pipeline.
- **Agentic Self-Correction Loop:** If the database engine returns an execution error, the pipeline catches the exception, pairs it with the structural DDL schema, and prompts the LLM for an automated correction.
- **Security-First Execution:** Implements strict read-only user database connections to natively prevent SQL injection or destructive (`DROP`, `DELETE`, `UPDATE`) commands.
- **Semantic Schema Routing:** Utilizes ChromaDB as a vector database to index and fetch relevant database metadata, reducing context window bloat for large schemas.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend / UI | Streamlit |
| LLM Orchestration | Python, LangChain, OpenAI API |
| Vector Database | ChromaDB |
| Relational Database | PostgreSQL |
| Containerization | Docker & Docker Compose |

---

## Quick Start (Docker Deployment)

The fastest way to spin up the entire application, database, and vector store environment is using Docker.

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running.
- An OpenAI API Key.

### Setup

**1. Clone the repository:**

```bash
git clone https://github.com/nonvegetable/nl2sql.git
cd nl2sql
```

**2. Configure your environment variables:**

Duplicate the example environment file and add your credentials:

```bash
cp .env.example .env
```

Open `.env` and insert your API key:

```
OPENAI_API_KEY=your_actual_openai_api_key_here
```

> Note: `READONLY_DATABASE_URL` is automatically managed inside the Docker network by Docker Compose.

**3. Launch the platform:**

```bash
docker-compose up --build
```

**4. Access the application:**

Once the build completes and all containers are running, open:

```
http://localhost:8501
```

---

## Local Development (Without Docker)

To run the application directly on your machine using a virtual environment:

**1. Create and activate a virtual environment:**

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

**2. Install dependencies:**

```bash
pip install -r requirements.txt
```

**3. Synchronize the schema vectors:**

Ensure your local database credentials are set in `.env`, then initialize the semantic vector store:

```bash
python sync_schema.py
```

**4. Run the app:**

```bash
streamlit run app.py
```

---

## Security & Guardrails

This project treats database access with strict enterprise guardrails:

**Network Isolation:** The PostgreSQL database container only exposes its port internally to the application network layer unless explicitly configured otherwise.

**Principle of Least Privilege:** The application container connects using a designated `readonly_user` profile, ensuring malicious or accidental modifications to data are structurally blocked at the engine layer.