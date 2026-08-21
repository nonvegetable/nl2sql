"""
Synchronizes the live PostgreSQL database schema with a local ChromaDB vector store.
Extracts table names, columns, and foreign key relationships to build semantic context.
"""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect

from providers import open_schema_collection

def sync_database_schema(db_url: str = None):
    # Load environment variables for the database
    load_dotenv()
    effective_url = db_url or os.getenv("DATABASE_URL")
    if not effective_url:
        raise ValueError("SECURITY AUDIT FAILED: 'DATABASE_URL' is missing. Please define it in your .env file.")

    # 1. Initialize SQLAlchemy Engine and Inspector
    engine = create_engine(effective_url)
    inspector = inspect(engine)

    # 2. Open (or rebuild) the schema collection for the active embedding provider
    collection = open_schema_collection(create=True)
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
            collection.upsert(
                documents=dynamic_documents,
                metadatas=dynamic_metadatas,
                ids=dynamic_ids
            )
            print("\nLocal ChromaDB successfully synced with live PostgreSQL schemas!")

    except Exception as e:
        print(f"An error occurred during synchronization: {e}")

if __name__ == "__main__":
    sync_database_schema()