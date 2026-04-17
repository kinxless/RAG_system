from app.mySQL_DB import get_connection
from app.neo4j_config import get_driver
import re
import time

# ----------------------------
# Keyword Extraction
# ----------------------------

def get_keywords(text, max_keywords=15):
    if not text:
        return []

    words = re.findall(r"\b[a-zA-Z]{4,}\b", text.lower())

    seen = set()
    keywords = []

    for w in words:
        if w not in seen:
            seen.add(w)
            keywords.append(w)

        if len(keywords) >= max_keywords:
            break

    return keywords


# ----------------------------
# Neo4j Write Logic
# ----------------------------

def create_doc(tx, doc_id, keywords):
    """
    Creates:
    - Document node
    - Keyword nodes
    - HAS_KEYWORD relationships
    - Weighted CO_OCCURS_WITH relationships
    """

    # ----------------------------
    # Create Document
    # ----------------------------

    tx.run(
        """
        MERGE (d:Document {id: $doc_id})
        """,
        doc_id=doc_id
    )

    # ----------------------------
    # Create Keywords + HAS_KEYWORD
    # ----------------------------

    tx.run(
        """
        UNWIND $keywords AS kw

        MERGE (k:Keyword {name: kw})

        WITH k, kw
        MATCH (d:Document {id: $doc_id})

        MERGE (d)-[:HAS_KEYWORD]->(k)
        """,
        doc_id=doc_id,
        keywords=keywords
    )

    # ----------------------------
    # Create Weighted Co-occurrence
    # ----------------------------

    pairs = []

    for i in range(len(keywords)):
        for j in range(i + 1, len(keywords)):

            pairs.append({
                "kw1": keywords[i],
                "kw2": keywords[j]
            })

    if pairs:

        tx.run(
            """
            UNWIND $pairs AS pair

            MATCH (k1:Keyword {name: pair.kw1})
            MATCH (k2:Keyword {name: pair.kw2})

            MERGE (k1)-[r:CO_OCCURS_WITH]-(k2)

            ON CREATE SET r.weight = 1
            ON MATCH SET r.weight = r.weight + 1
            """,
            pairs=pairs
        )


# ----------------------------
# Graph Builder
# ----------------------------

def build_graph():

    print("Connecting to MySQL...")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT id, content
        FROM rlm_documents
        """
    )

    rows = cursor.fetchall()

    print(f"Documents found: {len(rows)}")

    driver = get_driver()

    failed = 0

    for i, row in enumerate(rows):

        doc_id = row["id"]
        content = row["content"]

        print(f"Processing doc: {doc_id}")

        try:

            keywords = get_keywords(content)

            if not keywords:
                continue

            with driver.session() as session:

                session.execute_write(
                    create_doc,
                    doc_id,
                    keywords
                )

        except Exception as e:

            failed += 1

            print(
                f"FAILED doc {doc_id}: {e}"
            )

            # prevent hammering Neo4j
            time.sleep(0.5)

    driver.close()
    cursor.close()
    conn.close()

    print("\nGraph build complete.")
    print(f"Failed documents: {failed}")


# ----------------------------
# Entry Point
# ----------------------------

if __name__ == "__main__":
    build_graph()
