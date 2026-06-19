# 🤖 NL2SQL Enterprise Dashboard

Next-Gen Database Intelligence. Ask your database questions in natural language and get instantaneous visualization—powered locally and securely.

## 🌟 Overview
This project is an end-to-end Natural Language to SQL (NL2SQL) pipeline. It leverages a local **Ollama** LLM and a **ChromaDB** semantic search layer to generate accurate, dialect-specific PostgreSQL queries. The queries are safely executed against a read-only database connection, and the results are automatically charted on an interactive **Streamlit** dashboard.

## 🏗️ Architecture
1. **User Input:** User submits a natural language question via the Streamlit UI.
2. **Schema Retrieval (RAG):** The prompt is embedded and queried against ChromaDB to find the most semantically relevant database tables and structural constraints.
3. **Local LLM generation:** The context and query are piped through to a local LLM (e.g., `qwen3:4b` or `llama3`) via the Ollama API, separated cleanly into `system` rules and `user` data.
4. **Read-Only Execution & Agentic Auto-Fix:** The generated PostgreSQL is piped through a strictly read-only SQLAlchemy engine. If a SQL syntax error (`ProgrammingError`) occurs, the error is immediately caught and piped *back* to the LLM to dynamically self-correct up to 3 times.
5. **Intelligent UI Mapping:** The returned dataframe is processed intuitively by the frontend—automatically mapping it to key metrics, pie charts, bar graphs, scatter plots, or time-series curves using Plotly.

## 🚀 Installation & Setup

### 1. Prerequisites
- Python 3.10+
- [Ollama](https://ollama.com/) installed on your machine.
- PostgreSQL database.

### 2. Pull Local Models
Make sure to download the necessary embedding and generation models into your local Ollama instance:
```bash
# Embedding Model (used by ChromaDB)
ollama pull mxbai-embed-large

# Generation Model (used for SQL Translation)
ollama pull qwen3:4b
```

### 3. Clone and Install Dependencies
```bash
git clone https://github.com/your-username/nl2sql.git
cd nl2sql

# Create and activate virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`

# Install requirements
pip install -r requirements.txt
```

### 4. Configure Environment Variables
We use a dual-connection mechanism for security. You must configure your environment before running the app.
1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```
2. Open `.env` and fill in your actual database credentials. Make sure `READONLY_DATABASE_URL` is tied to a user restricted strictly to `SELECT` permissions to prevent injection or corruption!

### 5. Sync the Semantic Schema
Run the script to inspect your live PostgreSQL database and sync its structure into the local ChromaDB vector store:
```bash
python sync_schema.py
```

### 6. Launch the Dashboard
Run the Streamlit application:
```bash
python -m streamlit run app.py
```
Open your browser to `http://localhost:8501` to start querying!
