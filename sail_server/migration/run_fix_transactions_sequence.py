#!/usr/bin/env python3
"""
Run fix_transactions_sequence migration via Python.

Fixes the transactions.id sequence when it's out of sync with existing data,
which causes UniqueViolation (duplicate key) errors on INSERT.

Usage:
    From project root (loads .env.dev if POSTGRE_URI not set):
    python sail_server/migration/run_fix_transactions_sequence.py

    Or set POSTGRE_URI env var explicitly.
"""
import os
import sys

# Load .env.dev if POSTGRE_URI not set
if not os.environ.get("POSTGRE_URI"):
    try:
        import dotenv
        dotenv.load_dotenv(".env.dev", encoding="utf-8")
    except ImportError:
        pass

from sqlalchemy import create_engine, text


def main():
    uri = os.environ.get("POSTGRE_URI")
    if not uri:
        print("Error: POSTGRE_URI environment variable is not set")
        sys.exit(1)

    if uri.startswith("postgresql://"):
        uri = uri.replace("postgresql://", "postgresql+psycopg://", 1)

    engine = create_engine(uri)
    with engine.connect() as conn:
        with conn.begin():
            # Get sequence name
            seq_result = conn.execute(
                text("SELECT pg_get_serial_sequence('transactions', 'id')")
            )
            seq_name = seq_result.scalar()
            if not seq_name:
                print("Creating transactions_id_seq...")
                conn.execute(text(
                    "CREATE SEQUENCE IF NOT EXISTS transactions_id_seq "
                    "OWNED BY transactions.id"
                ))
                seq_name = "transactions_id_seq"

            # Get max id
            max_result = conn.execute(
                text("SELECT COALESCE(MAX(id), 0) FROM transactions")
            )
            max_id = max_result.scalar()
            new_val = max_id + 1

            # Reset sequence
            conn.execute(
                text(f"SELECT setval(:seq, :val, false)"),
                {"seq": seq_name, "val": new_val}
            )
            print(f"Sequence {seq_name} set to {new_val} (max id was {max_id})")


if __name__ == "__main__":
    main()
