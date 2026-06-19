"""
Core NL2SQL generation and execution engine.
Implements a RAG pipeline retrieving schema from ChromaDB, constructing a prompt
for a local Ollama model, and securely executing the resulting SQL query with
an agentic self-correction loop.
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

engine = create_engine(READONLY_DATABASE_URL)

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "qwen3:4b")
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "ollama").lower()

def call_llm(system_prompt: str, user_prompt: str) -> str:
    """Universal LLM wrapper supporting Ollama, OpenAI, Anthropic, and Gemini."""
    if LLM_PROVIDER == "openai":
        import openai
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("Configuration Error: 'OPENAI_API_KEY' is missing in .env for OpenAI provider.")
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=LLM_MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        return response.choices[0].message.content.strip()
        
    elif LLM_PROVIDER == "anthropic":
        import anthropic
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("Configuration Error: 'ANTHROPIC_API_KEY' is missing in .env for Anthropic provider.")
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=LLM_MODEL_NAME,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=2048
        )
        return response.content[0].text.strip()
        
    elif LLM_PROVIDER in ["gemini", "google", "google-genai"]:
        import google.generativeai as genai
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("Configuration Error: 'GEMINI_API_KEY' is missing in .env for Gemini provider.")
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name=LLM_MODEL_NAME,
            system_instruction=system_prompt
        )
        response = model.generate_content(user_prompt)
        return response.text.strip()
        
    else: # Default local Ollama
        import ollama
        response = ollama.chat(
            model=LLM_MODEL_NAME, 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        return response['message']['content'].strip()

# =====================================================================
# 1. INITIALIZE CHROMADB CLIENT
# =====================================================================
# Target the local folder where your synced vectors live
client = chromadb.PersistentClient(path="./chroma_db")

# Universal Embedding Resolution
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

# Fetch the existing collection populated during your ingestion script
collection = client.get_collection(
    name="database_schema_metadata", 
    embedding_function=embed_fn
)

# =====================================================================
# 2. STEP 2.1: SCHEMA RETRIEVAL FUNCTION
# =====================================================================
def retrieve_relevant_schemas(user_question: str, n_results: int = 2) -> str:
    """
    Queries ChromaDB with the natural language string to find the top N
    most semantically relevant database table structures.
    """
    # Query the collection
    results = collection.query(
        query_texts=[user_question],
        n_results=n_results
    )
    
    # Extract text strings from the retrieved documents list
    retrieved_docs = results['documents'][0]
    
    # Combine the schemas into a clean, single block of text context
    schema_context = "\n\n".join(retrieved_docs)
    return schema_context

# =====================================================================
# 3. STEP 2.2: MASTER PROMPT CONSTRUCTOR & LLM EXECUTION
# =====================================================================
def sanitize_sql(raw_llm_response: str) -> str:
    """
    Cleans up the LLM response by stripping out conversational text 
    and extracting the raw SQL query.
    """
    # 1. Try to extract code from markdown block if present
    sql_match = re.search(r"```(?:sql|SQL)?\n?(.*?)```", raw_llm_response, re.DOTALL)
    if sql_match:
        sql = sql_match.group(1).strip()
    else:
        # Fallback: Just return the raw text, cleaned up slightly
        sql = raw_llm_response.strip()
    
    # 2. Programmatically wipe out remaining markdown fences just in case 
    sql = re.sub(r"^```(?:sql|SQL)?", "", sql, flags=re.IGNORECASE)
    sql = re.sub(r"```$", "", sql, flags=re.IGNORECASE)
    
    # Remove leading/trailing whitespace
    return sql.strip()

def generate_sql_query(user_question: str) -> str:
    """
    Retrieves the context, builds the Master Prompt, and requests the
    LLM to output the exact SQL query required.
    """
    # Step 2.1: Extract only the relevant tables (defaulting to top 2 tables)
    retrieved_schema = retrieve_relevant_schemas(user_question, n_results=2)
    
    # Step 2.2: Construct the Dialect-Specific Master Prompt Template
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

    print("\n--- [DEBUG: System Prompt Sent to LLM] ---")
    print(system_role)
    print("\n--- [DEBUG: User Prompt Sent to LLM] ---")
    print(user_message)
    print("-------------------------------------------\n")

    # Call the universal LLM router
    raw_response = call_llm(system_role, user_message)
    
    # Apply programmatic regex sanitizer to remove unwanted markdown fences or conversational text
    return sanitize_sql(raw_response)

# =====================================================================
# 4. STEP 3: SECURE EXECUTION & SELF-CORRECTION
# =====================================================================
def execute_sql_with_self_correction(user_question: str, max_retries: int = 3):
    print(f"\nUser Prompt: '{user_question}'")
    generated_sql = generate_sql_query(user_question)
    
    print("--- [Initial Generated SQL Output] ---")
    print(generated_sql)
    print("--------------------------------------")
    
    for attempt in range(max_retries):
        try:
            with engine.connect() as connection:
                print(f"Attempting to execute SQL... (Attempt {attempt + 1}/{max_retries})")
                result = connection.execute(text(generated_sql))
                rows = result.fetchall()
                
                print("\n🎉 SQL Executed Successfully!")
                print(f"Rows returned: {len(rows)}")
                
                # Format results for readability
                if len(rows) > 0:
                    column_names = list(result.keys())
                    return {"sql": generated_sql, "results": [dict(zip(column_names, row)) for row in rows]}
                return {"sql": generated_sql, "results": []}
                
        except ProgrammingError as e:
            error_msg = str(e)
            print(f"\n[⚠️ SQL Execution Error] {error_msg}")
            
            if attempt == max_retries - 1:
                print("🚨 Max retries reached. Failing gracefully.")
                return {"sql": generated_sql, "error": error_msg}
                
            print("Auto-patching SQL via LLM...")
            
            # Agentic Self-Correction Loop
            fix_prompt = f"""
The following PostgreSQL query contains an error. 
Query: {generated_sql}
Error message from PostgreSQL: {error_msg}

Please fix the query so it is valid PostgreSQL syntax. Return ONLY the raw SQL code.
            """.strip()

            system_fix_role = "You are an expert PostgreSQL analyst. Output only the fixed, valid SQL query without markdown or explanations."
            raw_response = call_llm(system_fix_role, fix_prompt)
            
            generated_sql = sanitize_sql(raw_response)
            print(f"---\n[Patched SQL Output]\n{generated_sql}\n---")

# =====================================================================
# 5. RUN A LIVE TEST CASE
# =====================================================================
if __name__ == "__main__":
    sample_query = "Show me the total sales for clothing items last quarter."
    final_output = execute_sql_with_self_correction(sample_query)
    
    print("\n=== FINAL RESULT ===")
    print(final_output)