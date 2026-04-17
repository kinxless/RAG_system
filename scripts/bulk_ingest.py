from pathlib import Path

from app.ingest import ingest_pdf


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PDF_FOLDER = PROJECT_ROOT / "archive"
COLLECTION_NAME = "ai_papers"


def ingest_all_pdfs():
    if not PDF_FOLDER.exists():
        raise FileNotFoundError(f"Dataset folder not found: {PDF_FOLDER}")

    pdf_files = sorted([p for p in PDF_FOLDER.iterdir() if p.suffix.lower() == ".pdf"])
    print(f"Found {len(pdf_files)} PDFs")

    for i, pdf_path in enumerate(pdf_files):
        print(f"[{i+1}/{len(pdf_files)}] Processing {pdf_path.name}")
        try:
            ingest_pdf(str(pdf_path), collection_name=COLLECTION_NAME)
        except Exception as e:
            print(f"Error with {pdf_path.name}: {e}")


if __name__ == "__main__":
    ingest_all_pdfs()
