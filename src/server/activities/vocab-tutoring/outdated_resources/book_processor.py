import json
import string
import os
import time
import argparse
import pickle
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from openai import OpenAI
import spacy

nlp = spacy.load("en_core_web_lg")


@dataclass
class VocabWord:
    """Represents a vocabulary word with its context."""

    word: str
    sentence: str
    context_description: str

    def to_dict(self):
        return asdict(self)


@dataclass
class ProcessedChapter:
    """Represents a processed chapter with summary and vocab."""

    chapter_summary: str
    image: Optional[str]
    vocab_words: Dict[str, List[VocabWord]]

    def to_dict(self):
        return {
            "chapter_summary": self.chapter_summary,
            "image": self.image,
            "vocab_words": {
                grade: [word.to_dict() for word in words]
                for grade, words in self.vocab_words.items()
            },
        }


@dataclass
class BatchJob:
    """Represents a batch job for tracking."""

    batch_id: str
    input_path: str
    output_path: str
    book_data: Dict
    status: str = "pending"

    def to_dict(self):
        return {
            "batch_id": self.batch_id,
            "input_path": self.input_path,
            "output_path": self.output_path,
            "status": self.status,
        }


class BookProcessor:
    """Processes books to extract vocabulary, create summaries, and provide context using batch processing."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the BookProcessor with OpenAI client."""
        self.client = OpenAI(api_key=api_key) if api_key else OpenAI()
        self.batch_tracking_file = ".batch_tracking.json"

    def load_book(self, file_path: str) -> Dict:
        """Load a book from JSON file."""
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_book(self, book_data: Dict, output_path: str):
        """Save processed book to JSON file."""
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(book_data, f, ensure_ascii=False, indent=4)

    def load_batch_tracking(self) -> Dict[str, Dict]:
        """Load batch tracking information."""
        if os.path.exists(self.batch_tracking_file):
            with open(self.batch_tracking_file, "r") as f:
                return json.load(f)
        return {}

    def save_batch_tracking(self, tracking: Dict[str, Dict]):
        """Save batch tracking information."""
        with open(self.batch_tracking_file, "w") as f:
            json.dump(tracking, f, indent=2)

    def filter_words(self, text: str) -> str:
        """Remove short words, punctuation, and overly common words."""
        words = text.split()
        cleaned_words = [word.strip(string.punctuation) for word in words]
        filtered_words = [word for word in cleaned_words if len(word) >= 4]
        word_counts = Counter(filtered_words)
        unique_words = set([word for word in filtered_words if word_counts[word] <= 2])
        return " ".join(unique_words)

    def find_word_sentence(self, word: str, sents: List[Any]) -> Optional[str]:
        """Find the exact sentence containing the vocabulary word."""
        for sent in sents:
            # First check if word appears as substring
            if word.lower() in sent.text.lower():
                # Then verify it's a complete word match, not part of another word
                # Check both token text and lemma forms
                for token in sent:
                    if (
                        token.text.lower() == word.lower()
                        or token.lemma_.lower() == word.lower()
                    ):
                        return sent.text.strip()
        return None

    def get_sent_context(self, chapter_text: str, sentence: str) -> str:
        """Get the context window around a sentence (previous 1000 chars or from chapter start)."""
        # Find where the sentence starts in the chapter
        sentence_start = chapter_text.find(sentence)

        if sentence_start == -1:
            # If exact match not found, return first 1000 chars as fallback
            return chapter_text[:1000]

        # Get start position for context (1000 chars before sentence or chapter start)
        context_start = max(0, sentence_start - 1000)

        # Get end position (include the sentence plus a bit after for context)
        context_end = min(len(chapter_text), sentence_start + len(sentence) + 200)

        return chapter_text[context_start:context_end]

    def create_batch_requests(self, book_data: Dict) -> List[Dict]:
        """Create batch API requests for all processing tasks."""
        requests = []
        reading_context = book_data.get("reading_context", {})
        chapters = reading_context.get("chapters", [])
        book_title = reading_context.get("book_title", "Unknown")
        book_author = reading_context.get("book_author", "Unknown")

        # Request for book summary
        book_text = " ".join([ch.get("text", "")[:1000] for ch in chapters[:3]])
        requests.append(
            {
                "custom_id": "book_summary",
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": "gpt-4o-mini",
                    "messages": [
                        {
                            "role": "system",
                            "content": """You are a literature teacher creating book summaries for students.
Create a comprehensive summary (5-7 sentences) that captures:
1. The main plot and conflict
2. Key characters and their roles
3. The central theme or lesson
4. The story's resolution
Be engaging and informative.""",
                        },
                        {
                            "role": "user",
                            "content": (
                                f"Book: {book_title} by {book_author}\n\n"
                                f"Sample text: {book_text}\n\n"
                                f"Provide an overall summary of this book."
                            ),
                        },
                    ],
                    "temperature": 0.5,
                    "max_tokens": 300,
                },
            }
        )

        # Requests for chapter summaries and context
        for i, chapter in enumerate(chapters):
            chapter_text = chapter.get("text", "")

            # Chapter summary request
            requests.append(
                {
                    "custom_id": f"chapter_summary_{i}",
                    "method": "POST",
                    "url": "/v1/chat/completions",
                    "body": {
                        "model": "gpt-4o-mini",
                        "messages": [
                            {
                                "role": "system",
                                "content": """You are a literature teacher creating chapter summaries for students.
Create a concise but complete summary (3-5 sentences) that captures:
1. The main events that happen
2. Key character actions or decisions
3. How this chapter moves the story forward
Be clear and specific, avoiding vague language.""",
                            },
                            {
                                "role": "user",
                                "content": (
                                    f"Book: {book_title}\n\n"
                                    f"Chapter text: {chapter_text}\n\n"
                                    f"Provide a summary of this chapter."
                                ),
                            },
                        ],
                        "temperature": 0.5,
                        "max_tokens": 200,
                    },
                }
            )

            # Vocabulary context requests
            vocab_dict = chapter.get("vocab_words", {})
            sents = list(nlp(chapter_text).sents)

            for grade_level, words in vocab_dict.items():
                for word in words:
                    sentence = self.find_word_sentence(word, sents)
                    if sentence:
                        requests.append(
                            {
                                "custom_id": f"vocab_context_{i}_{grade_level}_{word}",
                                "method": "POST",
                                "url": "/v1/chat/completions",
                                "body": {
                                    "model": "gpt-4o-mini",
                                    "messages": [
                                        {
                                            "role": "system",
                                            "content": (
                                                "You are a reading comprehension specialist who "
                                                "provides context for vocabulary sentences.\n"
                                                "Given a sentence from a story and the chapter it "
                                                "appears in, provide a brief (1-2 sentence) description\n"
                                                "of the context: what is this sentence doing for the story.\n"
                                                "Be specific but concise. Focus on helping a student "
                                                "understand when and why this word is being used."
                                            ),
                                        },
                                        {
                                            "role": "user",
                                            "content": (
                                                f"Book: {book_title}\n\n"
                                                f"Chapter context: {self.get_sent_context(chapter_text, sentence)}\n\n"
                                                f'Sentence to contextualize: "{sentence}"\n\n'
                                                f"Provide a brief context description for this sentence."
                                            ),
                                        },
                                    ],
                                    "temperature": 0.5,
                                    "max_tokens": 150,
                                },
                            }
                        )

        return requests

    def submit_batch(self, requests: List[Dict]) -> str:
        """Submit batch to OpenAI and return batch ID."""
        # Save requests to JSONL file
        batch_file_path = "batch_requests.jsonl"
        with open(batch_file_path, "w") as f:
            for request in requests:
                f.write(json.dumps(request) + "\n")

        # Upload file
        with open(batch_file_path, "rb") as f:
            file_response = self.client.files.create(file=f, purpose="batch")

        # Create batch
        batch = self.client.batches.create(
            input_file_id=file_response.id,
            endpoint="/v1/chat/completions",
            completion_window="24h",
        )

        # Clean up temp file
        os.remove(batch_file_path)

        return batch.id

    def check_batch_status(self, batch_id: str) -> Tuple[str, Optional[Dict]]:
        """Check batch status and return (status, results if completed)."""
        try:
            batch = self.client.batches.retrieve(batch_id)

            if batch.status == "completed":
                # Download results
                result_file_id = batch.output_file_id
                results = self.client.files.content(result_file_id).text

                # Parse results
                results_dict = {}
                for line in results.strip().split("\n"):
                    if line:
                        try:
                            result = json.loads(line)
                            custom_id = result.get("custom_id")
                            # Check if response was successful
                            if "response" in result and "body" in result["response"]:
                                content = result["response"]["body"]["choices"][0][
                                    "message"
                                ]["content"]
                                results_dict[custom_id] = content
                            else:
                                print(f"Warning: No valid response for {custom_id}")
                                results_dict[custom_id] = None
                        except (json.JSONDecodeError, KeyError) as e:
                            print(f"Warning: Failed to parse result line: {e}")
                            continue

                return "completed", results_dict

            elif batch.status == "failed":
                return "failed", None

            else:
                # Still processing (in_progress, validating, finalizing, etc.)
                return batch.status, None

        except Exception as e:
            print(f"Error checking batch {batch_id}: {e}")
            return "error", None

    def process_batch_results(self, book_data: Dict, results: Dict, output_path: str):
        """Process batch results and save the book."""
        reading_context = book_data.get("reading_context", {})
        chapters = reading_context.get("chapters", [])
        book_title = reading_context.get("book_title", "Unknown")
        book_author = reading_context.get("book_author", "Unknown")

        # Process results
        processed_chapters = []
        for i, chapter in enumerate(chapters):
            chapter_text = chapter.get("text", "")
            vocab_dict = chapter.get("vocab_words", {})
            image = chapter.get("image", None)

            # Get chapter summary
            chapter_summary = results.get(
                f"chapter_summary_{i}", "Chapter summary unavailable."
            )

            # Build enhanced vocabulary
            enhanced_vocab = {}
            sents = list(nlp(chapter_text).sents)

            for grade_level, words in vocab_dict.items():
                enhanced_words = []
                for word in words:
                    sentence = self.find_word_sentence(word, sents)
                    if sentence:
                        context_key = f"vocab_context_{i}_{grade_level}_{word}"
                        context = results.get(context_key)
                        if context:  # Only add if we got a valid context
                            enhanced_words.append(
                                VocabWord(
                                    word=word,
                                    sentence=sentence,
                                    context_description=context,
                                )
                            )
                        else:
                            print(
                                f"Warning: No context found for word '{word}' in chapter {i}"
                            )
                enhanced_vocab[grade_level] = enhanced_words

            processed_chapters.append(
                ProcessedChapter(
                    chapter_summary=chapter_summary,
                    image=image,
                    vocab_words=enhanced_vocab,
                ).to_dict()
            )

        # Get book summary
        book_summary = results.get("book_summary", "Book summary unavailable.")

        # Create new book structure
        processed_book = {
            "reading_context": {
                "indexable_by": reading_context.get("indexable_by", "chapters"),
                "book_title": book_title,
                "book_author": book_author,
                "book_summary": book_summary,
                "chapters": processed_chapters,
            }
        }

        # Save
        self.save_book(processed_book, output_path)
        print(f"✅ Saved to: {output_path}")

    def submit_all_batches(self, input_dir: str, output_dir: str):
        """Submit batch jobs for all unprocessed books."""
        print(f"🎯 Submitting batch jobs for books from: {input_dir}")
        print(f"📁 Output directory: {output_dir}")

        tracking = self.load_batch_tracking()
        books_submitted = 0
        books_skipped = 0

        for root, dirs, files in os.walk(input_dir):
            for file in files:
                if file.endswith(".json"):
                    input_path = os.path.join(root, file)

                    # Create corresponding output path
                    relative_path = os.path.relpath(input_path, input_dir)
                    output_path = os.path.join(output_dir, relative_path)

                    # Check if already processed or in progress
                    if os.path.exists(output_path):
                        print(f"⏭️  Skipping (already exists): {relative_path}")
                        books_skipped += 1
                    elif input_path in tracking and tracking[input_path]["status"] in [
                        "pending",
                        "in_progress",
                        "validating",
                        "finalizing",
                    ]:
                        print(f"⏭️  Skipping (batch in progress): {relative_path}")
                        books_skipped += 1
                    else:
                        # Submit new batch
                        try:
                            print(f"📖 Submitting batch for: {relative_path}")
                            book_data = self.load_book(input_path)
                            requests = self.create_batch_requests(book_data)
                            batch_id = self.submit_batch(requests)

                            # Save tracking info with book data
                            tracking[input_path] = {
                                "batch_id": batch_id,
                                "output_path": output_path,
                                "status": "pending",
                                "submitted_at": time.time(),
                            }

                            # Also save book data separately for later processing
                            book_data_file = f".book_data_{batch_id}.pkl"
                            with open(book_data_file, "wb") as f:
                                pickle.dump(book_data, f)

                            books_submitted += 1
                            print(f"   Batch ID: {batch_id}")

                        except Exception as e:
                            print(f"❌ Failed to submit batch for {relative_path}: {e}")

        # Save tracking
        self.save_batch_tracking(tracking)

        print("\n📊 Submission Summary:")
        print(f"✅ Books submitted: {books_submitted}")
        print(f"⏭️  Books skipped: {books_skipped}")

    def check_all_batches(self):
        """Check status of all submitted batches and process completed ones."""
        tracking = self.load_batch_tracking()

        if not tracking:
            print("❌ No batch jobs found. Run with --submit first.")
            return

        print(f"📊 Checking {len(tracking)} batch jobs...")

        completed = 0
        failed = 0
        in_progress = 0
        processed = 0

        for input_path, job_info in tracking.items():
            batch_id = job_info["batch_id"]
            output_path = job_info["output_path"]
            current_status = job_info.get("status", "unknown")

            # Skip if already processed
            if current_status == "processed":
                processed += 1
                continue

            print(f"\n📖 Checking: {os.path.basename(input_path)}")
            print(f"   Batch ID: {batch_id}")

            status, results = self.check_batch_status(batch_id)
            print(f"   Status: {status}")

            if status == "completed":
                completed += 1

                # Load book data
                book_data_file = f".book_data_{batch_id}.pkl"
                if os.path.exists(book_data_file):
                    with open(book_data_file, "rb") as f:
                        book_data = pickle.load(f)

                    # Process results
                    print("   Processing results...")
                    self.process_batch_results(book_data, results, output_path)

                    # Update tracking
                    job_info["status"] = "processed"
                    job_info["completed_at"] = time.time()

                    # Clean up book data file
                    os.remove(book_data_file)
                else:
                    print("   ⚠️ Book data file not found, cannot process")
                    job_info["status"] = "error"

            elif status == "failed":
                failed += 1
                job_info["status"] = "failed"
                print("   ❌ Batch failed")

            elif status == "error":
                failed += 1
                job_info["status"] = "error"

            else:
                in_progress += 1
                job_info["status"] = status

        # Save updated tracking
        self.save_batch_tracking(tracking)

        print("\n📊 Status Summary:")
        print(f"✅ Completed this run: {completed}")
        print(f"📝 Previously processed: {processed}")
        print(f"⏳ Still in progress: {in_progress}")
        print(f"❌ Failed: {failed}")

        if in_progress > 0:
            print(f"\n⏳ {in_progress} batch(es) still processing. Check again later.")
        else:
            print("\n🎉 All batches have been processed!")


def main():
    """Main entry point with CLI arguments."""
    parser = argparse.ArgumentParser(description="Process books using OpenAI batch API")
    parser.add_argument(
        "--submit",
        action="store_true",
        help="Submit batch jobs for all unprocessed books",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check status of submitted batches and process completed ones",
    )
    parser.add_argument(
        "--input-dir",
        default="../../assets/books",
        help="Input directory containing books",
    )
    parser.add_argument(
        "--output-dir",
        default="../../assets/processed_books",
        help="Output directory for processed books",
    )
    parser.add_argument(
        "--reset", action="store_true", help="Reset batch tracking (use with caution)"
    )

    args = parser.parse_args()

    processor = BookProcessor()

    if args.reset:
        if os.path.exists(processor.batch_tracking_file):
            os.remove(processor.batch_tracking_file)
            print("✅ Batch tracking reset")
        # Clean up any orphaned book data files
        for file in os.listdir("."):
            if file.startswith(".book_data_") and file.endswith(".pkl"):
                os.remove(file)
                print(f"✅ Removed {file}")

    if args.submit:
        processor.submit_all_batches(args.input_dir, args.output_dir)
    elif args.check:
        processor.check_all_batches()
    else:
        print("Please specify either --submit or --check")
        print("\nUsage:")
        print(
            "  python script.py --submit              # Submit batch jobs for all books"
        )
        print(
            "  python script.py --check               # Check batch status and process results"
        )
        print("  python script.py --reset               # Reset batch tracking")
        print("\nOptional:")
        print("  --input-dir PATH   # Input directory (default: ../../assets/books)")
        print(
            "  --output-dir PATH  # Output directory (default: ../../assets/processed_books)"
        )


if __name__ == "__main__":
    main()
