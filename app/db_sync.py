from app.checkpoint import (
    load_last_id,
    save_last_id
)

from app.mySQL_DB import get_connection

import os
import time


# =========================
# GET ALL TABLES + PRIMARY KEYS
# =========================

def get_tables_with_pk(cursor):
    """
    Returns a dict of {table_name: pk_column}.
    Tables with no detectable primary key are skipped.
    """

    # MySQL 8 returns information_schema column names UPPERCASE in result rows,
    # so we alias to predictable lowercase keys.
    cursor.execute("""
        SELECT table_name AS name
        FROM information_schema.tables
        WHERE table_schema = DATABASE()
        AND table_type = 'BASE TABLE'
    """)

    table_names = [row["name"] for row in cursor.fetchall()]

    print("\n=== Tables Found ===")

    result = {}

    for table_name in table_names:

        cursor.execute("""
            SELECT column_name AS name,
                   CASE
                       WHEN column_key = 'PRI'                THEN 1
                       WHEN column_name = 'id'                THEN 2
                       WHEN extra LIKE '%%auto_increment%%'   THEN 3
                       ELSE 4
                   END AS priority
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
            AND table_name = %s
            AND (
                column_key = 'PRI'
                OR column_name = 'id'
                OR extra LIKE '%%auto_increment%%'
            )
            ORDER BY priority ASC
            LIMIT 1
        """, (table_name,))

        pk_row = cursor.fetchone()

        if pk_row:
            pk_col = pk_row["name"]
            result[table_name] = pk_col
            print(f" - {table_name}  (pk: {pk_col})")
        else:
            print(f" - {table_name}  (SKIPPED — no id/pk/auto_increment column)")

    return result


# =========================
# ETA FORMATTER
# =========================

def _format_eta(seconds):
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds / 60:.1f}m"
    else:
        return f"{seconds / 3600:.1f}h"


# =========================
# MAIN SYNC FUNCTION
# =========================

def sync_database():

    try:

        conn = get_connection()

        cursor = conn.cursor(dictionary=True)

        tables = get_tables_with_pk(cursor)

        if not tables:
            print("No tables found.")
            return

        # --- Pre-fetch all new rows across every table ---
        # This lets us know the exact total before embedding starts.

        table_rows = {}
        total_rows = 0

        for table_name, pk_col in tables.items():

            last_id = load_last_id(table_name)

            cursor.execute(
                f"SELECT * FROM `{table_name}` WHERE `{pk_col}` > %s ORDER BY `{pk_col}` ASC",
                (last_id,)
            )

            rows = cursor.fetchall()
            table_rows[table_name] = rows
            total_rows += len(rows)

            print(
                f"  {table_name}: {len(rows)} new rows"
            )

        if total_rows == 0:
            print("\nNo new rows to embed.")
            cursor.close()
            conn.close()
            return

        print(f"\n{'=' * 50}")
        print(f"  STARTING EMBEDDING — {total_rows} rows total")
        print(f"{'=' * 50}\n")

        from app.rag import add_texts_bulk

        # Batch size for Chroma writes. Each write embeds the whole batch in
        # one GPU pass and persists once. ~100 rows is a good balance between
        # memory and per-call overhead.
        BATCH_SIZE = int(os.getenv("SYNC_BATCH_SIZE", "100"))

        rows_done = 0
        session_start = time.time()

        def _row_to_item(table_name, row, pk_col):
            pk_val = row.get(pk_col, "")
            parts = [f"{k}: {v}" for k, v in row.items() if v is not None]
            row_text = " | ".join(parts)
            risk_value = (
                row.get("risk_description")
                or row.get("risk_desc")
                or row.get("risk")
                or row.get("case_name", "")
            )
            text = (
                f"\nTABLE NAME: {table_name}\n\n"
                f"THIS RECORD REPRESENTS A DATABASE ENTRY.\n\n"
                f"RECORD ID:\n{pk_val}\n\n"
                f"IMPORTANT FIELDS:\n\n"
                f"CASE NUMBER:\n{row.get('case_number', '')}\n\n"
                f"CASE NAME:\n{row.get('case_name', '')}\n\n"
                f"RISK DESCRIPTION:\n{risk_value}\n\n"
                f"FULL DATABASE RECORD:\n{row_text}\n"
            )
            return {
                "text": text,
                "source": f"{table_name}_{pk_val}",
            }

        for table_name, pk_col in tables.items():

            rows = table_rows[table_name]

            if not rows:
                print(f"  Skipping {table_name} — no new rows.\n")
                continue

            print(f"\n--- {table_name} ({len(rows)} rows) ---")

            batch = []

            def _flush(batch_to_flush):
                nonlocal rows_done
                if not batch_to_flush:
                    return
                flush_start = time.time()
                try:
                    add_texts_bulk(batch_to_flush, collection_name=table_name)
                except Exception as e:
                    print(f"  BATCH ERROR in {table_name}: {e}")
                rows_done += len(batch_to_flush)
                elapsed_total = time.time() - session_start
                avg_per_row = elapsed_total / max(rows_done, 1)
                remaining = total_rows - rows_done
                eta_seconds = remaining * avg_per_row
                eta_str = (
                    "done"
                    if remaining <= 0
                    else f"ETA {_format_eta(eta_seconds)}"
                )
                print(
                    f"  [{rows_done}/{total_rows}] "
                    f"flushed {len(batch_to_flush)} rows from {table_name} | "
                    f"{time.time() - flush_start:.2f}s | "
                    f"{eta_str}"
                )

            for row in rows:
                batch.append(_row_to_item(table_name, row, pk_col))
                if len(batch) >= BATCH_SIZE:
                    _flush(batch)
                    batch = []

            _flush(batch)

            new_last_id = rows[-1][pk_col]
            save_last_id(table_name, new_last_id)
            print(
                f"  Checkpoint saved: {table_name} up to ID {new_last_id}"
            )

        total_elapsed = time.time() - session_start

        print(f"\n{'=' * 50}")
        print(
            f"  DONE — {rows_done}/{total_rows} rows embedded "
            f"in {_format_eta(total_elapsed)}"
        )
        print(f"{'=' * 50}\n")

        cursor.close()
        conn.close()

    except Exception as e:

        print("DATABASE SYNC ERROR:")
        print(e)
        raise
