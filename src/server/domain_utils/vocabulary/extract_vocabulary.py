#!/usr/bin/env python3

from openai import OpenAI
import json
import string
from collections import Counter
import os
from tqdm import tqdm

client = OpenAI()

def filter_words(text: str) -> str:
    """Remove short words, punctuation, and overly common words."""
    words = text.split()
    cleaned_words = [word.strip(string.punctuation) for word in words]
    filtered_words = [word for word in cleaned_words if len(word) >= 4]
    word_counts = Counter(filtered_words)
    unique_words = set([word for word in filtered_words if word_counts[word] <= 2])
    return " ".join(unique_words)

def select_vocab_words(text: str) -> dict:
    """Extract Tier 2 vocabulary words using research-based criteria."""
    system_message = """You are a vocabulary extraction specialist that returns only valid JSON.

TASK: Extract high-quality Tier 2 vocabulary words from the provided text and categorize by grade level.

TIER 2 DEFINITION - Words that:
• Occur widely across domains and genres, marking written style rather than casual talk
• Add precision or nuance beyond basic conversational words
• Are NOT discipline-specific technical terms (those are Tier 3)
• Include both cross-disciplinary academic words AND vivid literary words
• Appear frequently enough in school texts to merit instruction

TIER 2 EXAMPLES:
• Academic: analyze, coordinate, duration, significant, establish, contrast, factor
• Literary: remorse, solace, surreptitious, stride, fortunate, acquire, contemplate

EXCLUDE (NOT Tier 2):
• Tier 1 high-frequency words: walk, get, big, happy, said, because, after
• Tier 3 technical terms: photosynthesis, algorithm, metaphor, protagonist
• Proper nouns: names, places, brands
• Very rare or archaic words

GRADE LEVEL CATEGORIZATION:
• Grade 4: Accessible Tier 2 words that 4th graders can handle (fortunate, establish, consider)
• Grade 5: Intermediate Tier 2 words appropriate for 5th grade complexity (coordinate, significant, acquire)
• Grade 6: Advanced Tier 2 words suitable for 6th grade level (surreptitious, contemplate, reluctant)

SELECTION RULES:
1. Only include words that actually appear in the provided text
2. Focus on words that enhance precision and academic/literary expression
3. Prioritize words useful across multiple contexts
4. No duplicates across grade levels
5. Consider vocabulary complexity and developmental appropriateness for each grade

TARGET: Aim for 8-12 high-quality Tier 2 words per 10,000 words of text (adjust based on text richness).

OUTPUT FORMAT:
{
  "grade_4": ["word1", "word2"],
  "grade_5": ["word1", "word2"], 
  "grade_6": ["word1", "word2"]
}"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",  # Using more widely available model
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": text}
        ],
        temperature=0.3,
        response_format={"type": "json_object"}
    )

    content = response.choices[0].message.content
    
    try:
        vocab = json.loads(content)
        for level in ["grade_4", "grade_5", "grade_6"]:
            if not isinstance(vocab.get(level), list):
                vocab[level] = []
            # Validate words actually appear in text
            vocab[level] = [word for word in vocab[level] if word.lower() in text.lower()]
        return vocab
    except (json.JSONDecodeError, ValueError) as e:
        print(f"Invalid response: {e}")
        return {"grade_4": [], "grade_5": [], "grade_6": []}

def process_book(file_path):
    """Process all chapters in a single book."""
    with open(file_path, 'r', encoding='utf-8') as f:
        story = json.load(f)
    
    chapters = story.get("reading_context", {}).get("chapters", [])
    book_title = story.get("reading_context", {}).get("book_title", "Unknown")
    
    print(f"Processing {book_title} ({len(chapters)} chapters)")
    
    total_words = 0
    total_vocab_extracted = 0
    
    for chapter in tqdm(chapters, desc=f"Extracting vocabulary"):
        text = chapter.get("text", "")
        if text.strip():

                
            word_count = len(text.split())
            total_words += word_count
            
            filtered_text = filter_words(text)
            if filtered_text.strip():
                vocab = select_vocab_words(filtered_text)
                chapter["vocab_words"] = vocab
                
                # Count extracted words
                extracted_count = len(vocab["grade_4"]) + len(vocab["grade_5"]) + len(vocab["grade_6"])
                total_vocab_extracted += extracted_count
                
                if extracted_count == 0:
                    print(f"  Warning: No Tier 2 vocabulary found in chapter (may be too simple or too technical)")
    
    # Save updated story
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(story, f, ensure_ascii=False, indent=4)
    
    # Report statistics
    if total_words > 0:
        words_per_vocab = total_words / max(total_vocab_extracted, 1)
        print(f"  📊 Statistics:")
        print(f"    Total words: {total_words:,}")
        print(f"    Tier 2 vocabulary extracted: {total_vocab_extracted}")
        print(f"    Rate: 1 Tier 2 word per {words_per_vocab:.0f} words")
        print(f"    Target rate: 1 per 833-1,250 words (research-based)")

def main():
    path_to_books = "../../assets/books"
    
    print("🎯 Starting research-based Tier 2 vocabulary extraction...")
    print("📚 Using evidence-based criteria from Beck & McKeown, Coxhead, et al.")
    
    books_processed = 0
    books_skipped = 0
    
    for dir_name in os.listdir(path_to_books):
        dir_path = os.path.join(path_to_books, dir_name)
        if os.path.isdir(dir_path):
            for file_name in os.listdir(dir_path):
                if file_name.endswith(".json"):
                    file_path = os.path.join(dir_path, file_name)
                    print(f"\n📖 Processing: {file_path}")
                    try:
                        process_book(file_path)
                        print(f"✅ Completed: {file_path}")
                        books_processed += 1
                    except Exception as e:
                        print(f"❌ Error processing {file_path}: {e}")
                        books_skipped += 1
    
    print(f"\n🎉 Vocabulary extraction complete!")
    print(f"📊 Summary:")
    print(f"  ✅ Books processed: {books_processed}")
    print(f"  ❌ Books skipped (errors): {books_skipped}")
    print(f"\n💡 Quality notes:")
    print(f"  • Focused on cross-domain academic and literary words")
    print(f"  • Excluded high-frequency conversational words (Tier 1)")
    print(f"  • Excluded technical discipline-specific terms (Tier 3)")
    print(f"  • Target: 8-12 Tier 2 words per 10,000 text words")

if __name__ == "__main__":
    main()