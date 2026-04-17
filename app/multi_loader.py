import os
import json


# Supported text file extensions
TEXT_EXTENSIONS = {

    ".txt",
    ".md",
    ".py",
    ".json",
    ".yaml",
    ".yml",
    ".html",
    ".css",
    ".js"

}


def load_text_file(file_path):

    try:

        with open(
            file_path,
            "r",
            encoding="utf-8",
            errors="ignore"
        ) as f:

            return f.read()

    except Exception as e:

        print(
            "Skipped text file error:",
            file_path
        )

        return None


def load_ipynb(file_path):

    try:

        with open(
            file_path,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        text = ""

        for cell in data.get("cells", []):

            if "source" in cell:

                text += "".join(
                    cell["source"]
                )

                text += "\n\n"

        return text

    except Exception:

        print(
            "Skipped notebook error:",
            file_path
        )

        return None


def load_pdf_safe(file_path):

    try:

        # Lazy import prevents circular import
        from app.pdf_loader import load_pdf

        return load_pdf(file_path)

    except Exception:

        print(
            "Skipped broken PDF:",
            file_path
        )

        return None


def load_file(file_path):

    ext = os.path.splitext(
        file_path
    )[1].lower()


    # PDF files
    if ext == ".pdf":

        return load_pdf_safe(
            file_path
        )


    # Notebook files
    elif ext == ".ipynb":

        return load_ipynb(
            file_path
        )


    # Text-like files
    elif ext in TEXT_EXTENSIONS:

        return load_text_file(
            file_path
        )


    else:

        # Unsupported file
        return None
