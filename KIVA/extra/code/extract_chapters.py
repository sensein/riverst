"""This module contains utilities for extracting chapters' text and titles from Bruce's JSON files."""

import json
import re
import os
import unicodedata
from typing import Dict, Any, Tuple

# --- Text cleaning and extraction helpers ---

CONTROL_CHARS_RE = re.compile(r"[\x00-\x1F\x7F]")  # ASCII control chars


def normalize_quotes(s: str) -> str:
    # Replace curly single quotes (‘ ’) and double quotes (“ ”)
    s = s.replace("“", '"').replace("”", '"')
    s = s.replace("‘", "'").replace("’", "'")
    return s


def clean_text(s: str) -> str:
    """Normalize and clean text by removing control chars and collapsing whitespace."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = CONTROL_CHARS_RE.sub(" ", s)
    s = s.replace("\u00A0", " ")  # non-breaking space
    s = re.sub(r"\s+", " ", s)
    s = normalize_quotes(s)
    return s.strip()


def extract_chapter_title_and_text(raw_text: str) -> Tuple[str, str]:
    """Extract chapter title (in **bold** or first line) and the body text."""
    if not raw_text or not raw_text.strip():
        return ("", "")
    text = raw_text.lstrip()

    # Markdown title
    m = re.match(r"^\s*\*\*(.+?)\*\*\s*\n+", text)
    if m:
        return (m.group(1).strip(), text[m.end() :])  # noqa: E203

    # First line as title
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip():
            return (line.strip(), "\n".join(lines[i + 1 :]))  # noqa: E203
    return ("", text)


def simplify_book_title(title: str) -> str:
    """Convert book title to lowercase, underscores, and safe characters."""
    title = title.lower().strip()
    title = re.sub(r"[^a-z0-9 _-]", "", title)
    title = re.sub(r"\s+", "_", title)
    return title or "book"


# --- Main processing function ---


def parse_and_save(data: Dict[str, Any], output_root="../chapters") -> None:
    rc = data.get("reading_context", {}) or {}
    book_title = clean_text(rc.get("book_title", ""))
    book_author = clean_text(rc.get("book_author", ""))
    chapters_in = rc.get("chapters", []) or []

    # Prepare output folder
    folder_name = simplify_book_title(book_title)
    output_dir = os.path.join(output_root, folder_name)
    os.makedirs(output_dir, exist_ok=True)

    for idx, ch in enumerate(chapters_in, start=1):
        raw_text = ch.get("text", "") or ""
        title, body = extract_chapter_title_and_text(raw_text)
        title_clean = clean_text(title or f"Chapter {idx}")
        body_clean = clean_text(body)

        # Create file-safe name
        filename = f"chapter_{idx:02d}.json"
        filepath = os.path.join(output_dir, filename)

        chapter_data = {
            "book_title": book_title,
            "book_author": book_author,
            "chapter_number": idx,
            "chapter_title": title_clean,
            "text": body_clean,
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(chapter_data, f, ensure_ascii=True, indent=2)

        print(f"✅ Saved: {filepath}")


# --- Batch processing of all JSON files ---

if __name__ == "__main__":
    books_dir = "../books"
    output_root = "../chapters"
    os.makedirs(output_root, exist_ok=True)

    json_files = [f for f in os.listdir(books_dir) if f.endswith(".json")]

    if not json_files:
        print("⚠️ No JSON files found in:", books_dir)
    else:
        for fname in json_files:
            path = os.path.join(books_dir, fname)
            print(f"\n📖 Processing: {fname}")
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                parse_and_save(data, output_root)
            except Exception as e:
                print(f"❌ Error processing {fname}: {e}")
