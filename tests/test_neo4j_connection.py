from app.neo4j_config import get_driver

def test():
    try:
        driver = get_driver()

        with driver.session() as session:
            result = session.run("RETURN 'CONNECTED' AS msg")

            for record in result:
                print(record["msg"])

        driver.close()

        print("Neo4j connection SUCCESS")

    except Exception as e:
        print("Neo4j FAILED:", e)

if __name__ == "__main__":
    test()
