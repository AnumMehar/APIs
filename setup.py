
import os
import subprocess
import psycopg2
from dotenv import load_dotenv


def setup_local_db():
    print("--- Healthcare Local Database Setup ---")
    load_dotenv()

    local_url = os.getenv("DATABASE_URL")
    if not local_url:
        print("Error: LOCAL_DATABASE_URL not found in .env.")
        return

    # Set Prisma environment variable
    os.environ["SUPABASE_URL"] = local_url
    os.environ["DIRECT_URL"] = local_url
    print(f"Targeting Local DB: {local_url}")

    try:
        print("Generating Prisma Client...")
        # subprocess.run(["prisma", "generate"], check=True)
        subprocess.run(
            ["prisma", "generate", "--schema=prisma/schema_local.prisma"],
            check=True
        )

        print("Directly checking local PostgreSQL for 'user' table...")

        # Connect directly to Postgres to check for your specific table
        conn = psycopg2.connect(local_url)
        cur = conn.cursor()
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'user'
            );
        """)
        user_table_exists = cur.fetchone()[0]
        cur.close()
        conn.close()

        if not user_table_exists:
            print("Project tables not found. Initializing local database schema...")
            # Use 'db push' to force create the tables from your schema.prisma
            # push_result = subprocess.run(["prisma", "db", "push", "--accept-data-loss"], capture_output=True, text=True)
            push_result = subprocess.run(
                        ["prisma", "db", "push", "--schema=prisma/schema_local.prisma", "--accept-data-loss"],
                        env=os.environ,
                        check=True
            )

            if push_result.returncode == 0:
                print("SUCCESS: Local tables (user, screenings, reports, etc.) created.")
            else:
                print(f"Error during push: {push_result.stderr}")
        else:
            print("Project tables already exist. Skipping to protect data.")

    except Exception as e:
        print(f"Setup Error: {e}")
        print("\nTIP: If you get a 'psycopg2' error, run: pip install psycopg2-binary")


if __name__ == "__main__":
    setup_local_db()