from app.rag import add_text
from app.pdf_loader import load_pdf


def ingest_pdf(file_path, collection_name="ai_papers"):
    print(f"Ingesting {file_path}")

    text = load_pdf(file_path)

    add_text(
        text,
        file_path,
        collection_name=collection_name
    )

    print(f"Ingestion complete -> {collection_name}")
