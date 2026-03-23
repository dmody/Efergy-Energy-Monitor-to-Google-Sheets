#!/usr/bin/env python3
"""
Diagnostic script to check if a sensor is writing data to a SQLite database.
Run on the Raspberry Pi:  python3 debug_sensor_db.py [path_to_db]

If no path is given, it searches common locations for .db / .sqlite files.
"""

import sqlite3
import sys
import os
import glob
from datetime import datetime, timedelta


def find_databases():
    """Search common Pi locations for SQLite files."""
    search_paths = [
        os.path.expanduser("~"),
        "/home/pi",
        "/var/lib",
        "/opt",
        "/tmp",
        "/srv",
    ]
    extensions = ("*.db", "*.sqlite", "*.sqlite3")
    found = set()
    for base in search_paths:
        for ext in extensions:
            found.update(glob.glob(os.path.join(base, "**", ext), recursive=True))
    return sorted(found)


def is_sqlite(path):
    """Check if a file is actually a SQLite database."""
    try:
        with open(path, "rb") as f:
            header = f.read(16)
        return header[:6] == b"SQLite"
    except Exception:
        return False


def inspect_database(db_path):
    """Print schema, row counts, and recent data for all tables."""
    print(f"\n{'='*60}")
    print(f"DATABASE: {db_path}")
    print(f"  Size: {os.path.getsize(db_path) / 1024:.1f} KB")
    print(f"  Modified: {datetime.fromtimestamp(os.path.getmtime(db_path))}")
    print(f"{'='*60}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # List tables
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cur.fetchall()]

    if not tables:
        print("  (no tables found)")
        conn.close()
        return

    for table in tables:
        print(f"\n--- Table: {table} ---")

        # Column info
        cur.execute(f"PRAGMA table_info('{table}')")
        columns = cur.fetchall()
        col_names = [c["name"] for c in columns]
        print(f"  Columns: {', '.join(col_names)}")

        # Row count
        cur.execute(f"SELECT COUNT(*) FROM '{table}'")
        count = cur.fetchone()[0]
        print(f"  Total rows: {count}")

        if count == 0:
            print("  ** NO DATA — sensor may not be writing **")
            continue

        # Find timestamp-like columns
        time_cols = [c for c in col_names if any(
            kw in c.lower() for kw in ("time", "date", "ts", "created", "updated", "stamp")
        )]

        if time_cols:
            tc = time_cols[0]
            # Most recent entry
            cur.execute(f"SELECT * FROM '{table}' ORDER BY '{tc}' DESC LIMIT 5")
            rows = cur.fetchall()
            print(f"\n  Last 5 entries (ordered by {tc}):")
            for row in rows:
                print(f"    {dict(row)}")

            # Check for recent data (last 1 hour)
            last_val = rows[0][tc] if rows else None
            if last_val:
                print(f"\n  Most recent {tc}: {last_val}")
                try:
                    # Try parsing as ISO timestamp
                    if isinstance(last_val, (int, float)):
                        last_dt = datetime.fromtimestamp(last_val)
                    else:
                        last_dt = datetime.fromisoformat(str(last_val).replace("Z", "+00:00"))
                    age = datetime.now(last_dt.tzinfo) if last_dt.tzinfo else datetime.now()
                    gap = age - last_dt
                    print(f"  Data age: {gap}")
                    if gap > timedelta(hours=1):
                        print(f"  ** WARNING: No data in the last {gap}. Sensor may be offline! **")
                    else:
                        print(f"  OK: Sensor reported within the last hour.")
                except Exception:
                    print(f"  (could not parse timestamp to check freshness)")

            # Count entries in last 24h (best effort)
            try:
                cur.execute(
                    f"SELECT COUNT(*) FROM '{table}' WHERE '{tc}' > datetime('now', '-1 day')"
                )
                recent = cur.fetchone()[0]
                print(f"  Rows in last 24h (datetime compare): {recent}")
            except Exception:
                pass
        else:
            # No timestamp column, just show last 5 rows
            cur.execute(f"SELECT * FROM '{table}' LIMIT 5")
            rows = cur.fetchall()
            print(f"\n  Sample rows (no timestamp column detected):")
            for row in rows:
                print(f"    {dict(row)}")

    conn.close()


def main():
    if len(sys.argv) > 1:
        # User provided a specific database path
        db_path = sys.argv[1]
        if not os.path.exists(db_path):
            print(f"Error: {db_path} does not exist")
            sys.exit(1)
        inspect_database(db_path)
    else:
        # Search for databases
        print("No database path provided. Searching for SQLite files...")
        dbs = find_databases()
        sqlite_dbs = [d for d in dbs if is_sqlite(d)]

        if not sqlite_dbs:
            print("\nNo SQLite databases found in common locations.")
            print("Try running with the explicit path:")
            print("  python3 debug_sensor_db.py /path/to/your/database.db")
            print("\nTo find it yourself:")
            print("  find / -name '*.db' -o -name '*.sqlite' 2>/dev/null")
            sys.exit(1)

        print(f"\nFound {len(sqlite_dbs)} SQLite database(s):\n")
        for i, db in enumerate(sqlite_dbs):
            print(f"  [{i+1}] {db}")

        print()
        for db in sqlite_dbs:
            inspect_database(db)


if __name__ == "__main__":
    main()
