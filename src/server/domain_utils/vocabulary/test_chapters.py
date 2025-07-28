#!/usr/bin/env python3

from utils.book_converter.gutenberg_converter import extract_chapters_from_html


def main():
    book_data = extract_chapters_from_html(
        "/Users/bruceatwood/Desktop/riverst/src/server/utils/book_converter/raw_downloads/pg12-images.html"
    )
    print(f'Found {len(book_data["chapters"])} chapters:')
    for i, chapter in enumerate(book_data["chapters"]):
        print(f'Chapter {i+1}: {chapter["title"]}')


if __name__ == "__main__":
    main()
