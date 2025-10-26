from supabase import create_client
import os

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

create_table_sql = """
CREATE TABLE IF NOT EXISTS "UserTasks" (
    id BIGSERIAL PRIMARY KEY,
    phone_number VARCHAR(20) NOT NULL,
    task TEXT NOT NULL,
    created_at_timestamp TIMESTAMPTZ DEFAULT NOW(),
    trigger_timestamp TIMESTAMPTZ NOT NULL,
    call_intent BOOLEAN DEFAULT FALSE
);
"""

# Execute the SQL
response = supabase.rpc("sql", {"query": create_table_sql}).execute()  # If using RPC
print(response)