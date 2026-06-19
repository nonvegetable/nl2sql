"""
Synchronizes the live PostgreSQL database schema with a local ChromaDB vector store.
Extracts table names, columns, and foreign key relationships to build semantic context.
"""

import os

import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect

# Load environment variables for the database
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("SECURITY AUDIT FAILED: 'DATABASE_URL' is missing. Please define it in your .env file.")

# Universal Embedding Resolution
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "ollama").lower()

if EMBEDDING_PROVIDER == "openai":
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
         raise ValueError("Missing OPENAI_API_KEY in .env for OpenAI embeddings.")
    embed_fn = embedding_functions.OpenAIEmbeddingFunction(
        api_key=openai_api_key,
        model_name=os.getenv("EMBEDDING_MODEL_NAME", "text-embedding-3-small")
    )
else: # Default to local Ollama
    embed_fn = embedding_functions.OllamaEmbeddingFunction(
        url=os.getenv("OLLAMA_URL", "http://localhost:11434/api/embeddings"),
        model_name=os.getenv("EMBEDDING_MODEL_NAME", "mxbai-embed-large")
    )

# 1. Initialize SQLAlchemy Engine and Inspector
engine = create_engine(DATABASE_URL)
inspector = inspect(engine)

# 2. Initialize your local Persistent ChromaDB Client
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection(
    name="database_schema_metadata", 
    embedding_function=embed_fn
)
# 3. Create empty lists to hold our dynamically generated data
dynamic_documents = []
dynamic_metadatas = []
dynamic_ids = []

try:
    # Pull the live list of tables directly from PostgreSQL
    table_names = inspector.get_table_names()
    print(f"Connected! Inspecting database tables: {table_names}\n")

    for table_name in table_names:
        # --- Build the Column Description String ---
        columns = inspector.get_columns(table_name)
        col_descriptions = []
        for col in columns:
            col_descriptions.append(f"{col['name']} ({col['type']})")
        
        # Combine columns into a single readable string segment
        column_string = ", ".join(col_descriptions)
        
        # --- Build Foreign Key Relationships (if any exist) ---
        fk_constraints = inspector.get_foreign_keys(table_name)
        fk_string = ""
        if fk_constraints:
            fk_desc = []
            for fk in fk_constraints:
                fk_desc.append(f"{fk['constrained_columns']} references {fk['referred_table']}({fk['referred_columns']})")
            fk_string = f" Foreign Keys: {', '.join(fk_desc)}."

        # 4. Construct the descriptive Document string dynamically
        document_text = f"Table '{table_name}' has columns {column_string}.{fk_string}"
        
        # Append our generated pieces into our array blocks
        dynamic_documents.append(document_text)
        dynamic_metadatas.append({"table_name": table_name})
        dynamic_ids.append(f"schema_chunk_{table_name}")
        
        print(f"Generated Dynamic Chunk for: {table_name}")

    # 5. Push the dynamically created arrays straight into ChromaDB
    if dynamic_documents:
        collection.add(
            documents=dynamic_documents,
            metadatas=dynamic_metadatas,
            ids=dynamic_ids
        )
        print("\n🎉 Local ChromaDB successfully synced with live PostgreSQL schemas!")

except Exception as e:
    print(f"An error occurred during synchronization: {e}")