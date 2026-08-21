"""
Core NL2SQL generation and execution engine.
Implements a RAG pipeline retrieving schema from ChromaDB, constructing a prompt
for a local LM Studio / Ollama model or Cloud API, and securely executing the
resulting SQL query with an agentic self-correction loop.
"""

import os
import re

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError

from providers import call_llm, open_schema_collection

# =====================================================================
# 0. INITIALIZE CONFIGURATION & DATABASE
# =====================================================================
load_dotenv()
READONLY_DATABASE_URL = os.getenv("READONLY_DATABASE_URL")

# Only create the default engine if the URL exists at boot
default_engine = None
if READONLY_DATABASE_URL:
    default_engine = create_engine(READONLY_DATABASE_URL)

# =====================================================================
# 1. SCHEMA RETRIEVAL FUNCTION
# =====================================================================
def retrieve_relevant_schemas(user_question: str, n_results: int = 2) -> str:
    collection = open_schema_collection()
    results = collection.query(query_texts=[user_question], n_results=n_results)
    return "\n\n".join(results['documents'][0])

# =====================================================================
# 2. MASTER PROMPT CONSTRUCTOR & SANITIZATION
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

def generate_sql_query(user_question: str, provider: str = None, model_name: str = None, api_key: str = None) -> str:
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

    raw_response = call_llm(system_role, user_message, provider=provider, model_name=model_name, api_key=api_key)
    return sanitize_sql(raw_response)

# =====================================================================
# 3. SECURE EXECUTION & SELF-CORRECTION LOOP
# =====================================================================
def execute_sql_with_self_correction(user_question: str, max_retries: int = 3, db_url: str = None, provider: str = None, model_name: str = None, api_key: str = None):
    """Generates and securely runs query with dynamic model overrides and target connection pools."""
    generated_sql = generate_sql_query(user_question, provider=provider, model_name=model_name, api_key=api_key)
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
            raw_response = call_llm(system_fix_role, fix_prompt, provider=provider, model_name=model_name, api_key=api_key)
            generated_sql = sanitize_sql(raw_response)
        except Exception as e:
            # Fallback for connection-level or general python driver issues
            return {"sql": generated_sql, "error": str(e)}