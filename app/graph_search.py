from app.neo4j_config import get_driver
import re


# ----------------------------
# Keyword Extraction
# ----------------------------

def extract_keywords(text, max_keywords=5):
    """
    Extract keywords from user query
    """

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
# Graph Search Logic
# ----------------------------

def graph_search(query, limit=10):
    """
    Graph-based retrieval using weighted relationships
    """

    driver = get_driver()

    keywords = extract_keywords(query)

    print("\nQuery keywords:", keywords)

    if not keywords:
        print("No valid keywords found.")
        return []

    cypher = """
    MATCH (k:Keyword)
    WHERE k.name IN $keywords

    MATCH (k)-[r:CO_OCCURS_WITH]-(related:Keyword)

    WITH related, sum(r.weight) AS score
    ORDER BY score DESC

    MATCH (d:Document)-[:HAS_KEYWORD]->(related)

    RETURN DISTINCT
           d.id AS doc_id,
           related.name AS keyword,
           score

    LIMIT $limit
    """

    results = []

    with driver.session() as session:

        records = session.run(
            cypher,
            keywords=keywords,
            limit=limit
        )

        for record in records:

            results.append({
                "doc_id": record["doc_id"],
                "keyword": record["keyword"],
                "score": record["score"]
            })

    driver.close()

    return results


# ----------------------------
# Manual Test Mode
# ----------------------------

if __name__ == "__main__":

    query = input("\nEnter query: ")

    results = graph_search(query)

    print("\nTop Results:\n")

    for r in results:

        print(r)
