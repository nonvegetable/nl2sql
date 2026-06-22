"""
Core NL2SQL generation and execution engine.
Implements a RAG pipeline retrieving schema from ChromaDB, constructing a prompt
for a local Ollama model or Cloud API, and securely executing the resulting SQL 
query with an agentic self-correction loop.
"""

import os
import re

import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError

# =====================================================================
# 0. INITIALIZE CONFIGURATION & DATABASE
# =====================================================================
load_dotenv()
READONLY_DATABASE_URL = os.getenv("READONLY_DATABASE_URL")

if not READONLY_DATABASE_URL:
    raise ValueError("SECURITY AUDIT FAILED: 'READONLY_DATABASE_URL' is missing. Please define it in your .env file.")

default_engine = create_engine(READONLY_DATABASE_URL)
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "ollama").lower()

def call_llm(system_prompt: str, user_prompt: str, provider: str = None, model_name: str = None) -> str:
    """Universal LLM wrapper supporting Ollama, OpenAI, Anthropic, and Gemini dynamically."""
    active_provider = (provider or os.getenv("LLM_PROVIDER", "ollama")).lower()
    active_model = model_name or os.getenv("LLM_MODEL_NAME", "qwen3:4b")

    if active_provider == "openai":
        import openai
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("Configuration Error: 'OPENAI_API_KEY' is missing in .env for OpenAI provider.")
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=active_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        return response.choices[0].message.content.strip()
        
    elif active_provider == "anthropic":
        import anthropic
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("Configuration Error: 'ANTHROPIC_API_KEY' is missing in .env for Anthropic provider.")
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=active_model,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=2048
        )
        return response.content[0].text.strip()
        
    elif active_provider in ["gemini", "google", "google-genai"]:
        import google.generativeai as genai
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("Configuration Error: 'GEMINI_API_KEY' is missing in .env for Gemini provider.")
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name=active_model,
            system_instruction=system_prompt
        )
        response = model.generate_content(user_prompt)
        return response.text.strip()
        
    else: # Default local Ollama
        import ollama
        response = ollama.chat(
            model=active_model, 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        return response['message']['content'].strip()

# =====================================================================
# 1. INITIALIZE CHROMADB CLIENT
# =====================================================================
client = chromadb.PersistentClient(path="./chroma_db")

if EMBEDDING_PROVIDER == "openai":
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
         raise ValueError("Configuration Error: 'OPENAI_API_KEY' is missing in .env for OpenAI embeddings.")
    embed_fn = embedding_functions.OpenAIEmbeddingFunction(
        api_key=openai_api_key,
        model_name=os.getenv("EMBEDDING_MODEL_NAME", "text-embedding-3-small")
    )
else:
    embed_fn = embedding_functions.OllamaEmbeddingFunction(
        url=os.getenv("OLLAMA_URL", "http://localhost:11434/api/embeddings"),
        model_name=os.getenv("EMBEDDING_MODEL_NAME", "mxbai-embed-large")
    )

collection = client.get_collection(
    name="database_schema_metadata", 
    embedding_function=embed_fn
)

# =====================================================================
# 2. SCHEMA RETRIEVAL FUNCTION
# =====================================================================
def retrieve_relevant_schemas(user_question: str, n_results: int = 2) -> str:
    results = collection.query(query_texts=[user_question], n_results=n_results)
    return "\n\n".join(results['documents'][0])

# =====================================================================
# 3. MASTER PROMPT CONSTRUCTOR & SANITIZATION
# =====================================================================
def sanitize_sql(raw_llm_response: str) -> str:
    """
    Cleans up the LLM response by stripping out conversational text 
    and extracting the raw SQL query safely.
    """
    # Programmatic creation of triple backticks avoids markdown parser breakage
    triple_ticks = "```"
    sql_match = re.search(rf"{triple_ticks}(?:sql|SQL)?\n?(.*?){triple_ticks}", raw_llm_response, re.DOTALL)
    
    if sql_match:
        sql = sql_match.group(1).strip()
    else:
        sql = raw_llm_response.strip()
    
    # Safely clear left-over fences
    sql = re.sub(rf"^{triple_ticks}(?:sql|SQL)?", "", sql, flags=re.IGNORECASE)
    sql = re.sub(rf"{triple_ticks}$", "", sql, flags=re.IGNORECASE)
    return sql.strip()

def generate_sql_query(user_question: str, provider: str = None, model_name: str = None) -> str:
    retrieved_schema = retrieve_relevant_schemas(user_question, n_results=2)
    
    system_role = """
You are an expert PostgreSQL analyst. Your sole purpose is to output valid, optimized, and executable PostgreSQL queries.
CRITICAL CONSTRAINTS:
1. You must use valid PostgreSQL syntax. Do NOT use SQLite functions like DATE('now'). Use CURRENT_DATE, DATE_TRUNC, or INTERVAL arithmetic for dates.
2. Return ONLY the raw SQL code.
3. Do not include markdown code blocks (like ```sql), explanations, or opening/closing commentary.
    """.strip()

    user_message = f"""
Given the following PostgreSQL database schema:
{retrieved_schema}

Translate this user question into a valid, optimized, and executable PostgreSQL query:
{user_question}
    """.strip()

    raw_response = call_llm(system_role, user_message, provider=provider, model_name=model_name)
    return sanitize_sql(raw_response)

# =====================================================================
# 4. SECURE EXECUTION & SELF-CORRECTION LOOP
# =====================================================================
def execute_sql_with_self_correction(user_question: str, max_retries: int = 3, db_url: str = None, provider: str = None, model_name: str = None):
    """Generates and securely runs query with dynamic model overrides and target connection pools."""
    generated_sql = generate_sql_query(user_question, provider=provider, model_name=model_name)
    active_engine = create_engine(db_url) if db_url else default_engine
    
    for attempt in range(max_retries):
        try:
            with active_engine.connect() as connection:
                result = connection.execute(text(generated_sql))
                rows = result.fetchall()
                
                if len(rows) > 0:
                    column_names = list(result.keys())
                    return {"sql": generated_sql, "results": [dict(zip(column_names, row)) for row in rows]}
                return {"sql": generated_sql, "results": []}
                
        except ProgrammingError as e:
            error_msg = str(e)
            if attempt == max_retries - 1:
                return {"sql": generated_sql, "error": error_msg}
                
            fix_prompt = f"""
The following PostgreSQL query contains an error. 
Query: {generated_sql}
Error message from PostgreSQL: {error_msg}

Please fix the query so it is valid PostgreSQL syntax. Return ONLY the raw SQL code.
            """.strip()

            system_fix_role = "You are an expert PostgreSQL analyst. Output only the fixed, valid SQL query without markdown or explanations."
            raw_response = call_llm(system_fix_role, fix_prompt, provider=provider, model_name=model_name)
            generated_sql = sanitize_sql(raw_response)
        except Exception as e:
            # Fallback for connection-level or general python driver issues
            return {"sql": generated_sql, "error": str(e)}