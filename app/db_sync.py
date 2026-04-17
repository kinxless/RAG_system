from app.checkpoint import (
    load_last_id,
    save_last_id
)

from app.rag import add_text
from app.mySQL_DB import get_connection


def sync_database():

    try:

        conn = get_connection()

        cursor = conn.cursor(
            dictionary=True
        )


        # =========================
        # GET TABLES
        # =========================

        cursor.execute(
            "SHOW TABLES"
        )

        tables = cursor.fetchall()


        if not tables:

            print("No tables found.")
            return


        # =========================
        # PROCESS TABLES
        # =========================

        for table_dict in tables:

            table_name = list(
                table_dict.values()
            )[0]


            print(
                f"\nChecking table: {table_name}"
            )


            last_id = load_last_id(
                table_name
            )


            query = f"""
            SELECT *
            FROM {table_name}
            WHERE id > %s
            ORDER BY id ASC
            """


            cursor.execute(
                query,
                (last_id,)
            )


            rows = cursor.fetchall()


            if not rows:

                print(
                    f"No new rows in {table_name}."
                )

                continue


            # =========================
            # PROCESS ROWS
            # =========================

            for row in rows:

                try:

                    parts = []

                    for k, v in row.items():

                        if v is None:
                            continue

                        parts.append(
                            f"{k}: {v}"
                        )


                    # =====================================
                    # UPDATED TEXT FORMAT (THIS IS THE FIX)
                    # =====================================

                    row_text = " | ".join(parts)

                    risk_value = (
                        row.get("risk_description")
                        or row.get("risk_desc")
                        or row.get("risk")
                        or row.get("case_name", "")
                    )

                    text = f"""
TABLE NAME: {table_name}

THIS RECORD REPRESENTS A DATABASE ENTRY.

RECORD ID:
{row.get("id", "")}

IMPORTANT FIELDS:

CASE NUMBER:
{row.get("case_number", "")}

CASE NAME:
{row.get("case_name", "")}

RISK DESCRIPTION:
{risk_value}

FULL DATABASE RECORD:
{row_text}
"""


                    doc_id = (
                        f"{table_name}_"
                        f"{row['id']}"
                    )


                    print(
                        f"Embedding row "
                        f"{row['id']} "
                        f"from {table_name}"
                    )


                    add_text(

                        text,

                        doc_id,

                        collection_name=table_name

                    )


                except Exception as e:

                    print(
                        f"Row error "
                        f"{row['id']} "
                        f"in {table_name}: {e}"
                    )


            # =========================
            # SAVE CHECKPOINT
            # =========================

            new_last_id = rows[-1]["id"]

            save_last_id(
                table_name,
                new_last_id
            )


            print(
                f"Synced {table_name} "
                f"up to ID {new_last_id}"
            )


        cursor.close()

        conn.close()


    except Exception as e:

        print("DATABASE SYNC ERROR:")

        print(e)
