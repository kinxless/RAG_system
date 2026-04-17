import mysql.connector


def get_connection():

    return mysql.connector.connect(
        host="127.0.0.1",
        user="root",
        password="",  # try empty password first
        database="rag_trial"
    )


def get_rows_after(last_id):

    conn = get_connection()

    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT id, content
        FROM rag_trial_table
        WHERE id > %s
        ORDER BY id ASC
    """

    cursor.execute(query, (last_id,))

    rows = cursor.fetchall()

    cursor.close()

    conn.close()

    return rows