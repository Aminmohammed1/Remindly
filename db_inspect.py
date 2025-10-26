import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()  # Load environment variables

try:
    # Connect to the main Supabase PostgreSQL database
    conn = psycopg2.connect(
        host=os.getenv("HOST"),
        database=os.getenv("DBNAME"),
        user=os.getenv("USER"),
        password=os.getenv("PASSWORD"),
        port=os.getenv("PORT")
    )
    conn.autocommit = True
    cur = conn.cursor()

    # 1️⃣ List all databases
    print("📚 Databases:")
    cur.execute("SELECT datname FROM pg_database WHERE datistemplate = false;")
    for db in cur.fetchall():
        print("  -", db[0])

    # 2️⃣ List all schemas
    print("\n📂 Schemas:")
    cur.execute("SELECT schema_name FROM information_schema.schemata;")
    for schema in cur.fetchall():
        print("  -", schema[0])

    # 3️⃣ List all tables in public schema
    print("\n🧾 Tables in 'public' schema:")
    cur.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        ORDER BY table_name;
    """)
    tables = cur.fetchall()
    if tables:
        for table in tables:
            print("  -", table[0])
    else:
        print("  (no tables found)")

    cur.close()
    conn.close()
except Exception as e:
    print("❌ Failed to connect or fetch:", e)
