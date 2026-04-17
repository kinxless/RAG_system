from pathlib import Path
import traceback

from app.multi_loader import load_file
from app.mySQL_DB import get_connection


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASET_FOLDER = PROJECT_ROOT / "archive"
BATCH_SIZE = 5


def insert_dataset():
    print("\n===== RLM DATASET INGESTION STARTED =====\n")

    conn = get_connection()
    cursor = conn.cursor()

    inserted_count = 0
    skipped_count = 0
    error_count = 0
    batch_counter = 0

    for root, _dirs, files in DATASET_FOLDER.walk():
        print(f"\nScanning folder: {root}")

        for file in files:
            file_path = root / file
            print(f"\nReading file: {file_path}")

            try:
                text = load_file(str(file_path))
                if not text:
                    print("Skipped (unsupported or empty):", file)
                    skipped_count += 1
                    continue

                category = root.name

                cursor.execute(
                    """
                    INSERT INTO rlm_documents
                    (content, source, category)
                    VALUES (%s, %s, %s)
                    """,
                    (text, str(file_path), category),
                )

                inserted_count += 1
                batch_counter += 1
                print("Inserted:", file)

                if batch_counter >= BATCH_SIZE:
                    conn.commit()
                    print(f"Committed batch of {BATCH_SIZE} files")
                    batch_counter = 0

            except Exception as e:
                print("\nERROR processing:", file_path)
                print(str(e))
                traceback.print_exc()
                error_count += 1

    conn.commit()
    cursor.close()
    conn.close()

    print("\n===== INGESTION COMPLETE =====")
    print("Inserted files :", inserted_count)
    print("Skipped files  :", skipped_count)
    print("Errored files  :", error_count)


if __name__ == "__main__":
    insert_dataset()
