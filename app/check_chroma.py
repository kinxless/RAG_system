import chromadb
import os

print("\n=== CHROMA DEBUG ===\n")

# Show current working directory
print("Current working directory:")
print(os.getcwd())

print("\nChecking if chroma_db folder exists...")

db_path = "../chroma_db"

if os.path.exists(db_path):
    print(f"✅ Found folder: {db_path}")
else:
    print(f"❌ Missing folder: {db_path}")


print("\nConnecting to Chroma...")

client = chromadb.PersistentClient(
    path=db_path
)

collections = client.list_collections()

print("\n=== Collections Found ===\n")

if not collections:

    print("❌ No collections exist.")

else:

    for col in collections:

        print(f"Collection name: {col.name}")

        try:
            count = col.count()
            print(f"Documents inside: {count}")

        except Exception as e:
            print("Error counting docs:", e)

        print()