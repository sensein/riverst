# NON BATCH


from openai import OpenAI
import json
import string
from collections import Counter
import os
from tqdm import tqdm

client = OpenAI()

def filter_words(text: str) -> str:
    """
    Filters out words shorter than 4 characters, removes punctuation, 
    and excludes those that occur more than twice.

    Args:
        text (str): The input text from which to filter words.

    Returns:
        str: A string of filtered words joined by spaces.
    """
    words = text.split()
    cleaned_words = [word.strip(string.punctuation) for word in words]
    filtered_words = [word for word in cleaned_words if len(word) >= 4]
    word_counts = Counter(filtered_words)
    unique_words = set([word for word in filtered_words if word_counts[word] <= 2])
    return " ".join(unique_words)

def select_vocab_words(text: str) -> dict:
    """
    Extracts Tier 2 vocabulary words from input text using GPT-4.

    Args:
        text (str): The input text.

    Returns:
        dict: Dictionary with keys 'easy', 'medium', and 'hard' mapping to word lists.
    """
    system_message = (
        "You are a helpful assistant that returns only valid JSON. "
        "Extract high-quality Tier 2 vocabulary words from the provided text. "
        "Do not duplicate words across levels. "
        "Choose only Tier 2 words and categorize them as easy, medium, or hard. "
        "Include as many valid words as possible in each category, but only if they appear in the original text exactly as written. "
        "The expected output format is as follows: \n"
        "{\n"
        "  \"easy\": [\"word1\", \"word2\", \"...\"],\n"
        "  \"medium\": [\"word1\", \"word2\", \"...\"],\n"
        "  \"hard\": [\"word1\", \"word2\", \"...\"]\n"
        "}"
    )

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": text}
        ],
        temperature=0.3,
    )

    content = response.choices[0].message.content

    try:
        vocab = json.loads(content)
        for level in ["easy", "medium", "hard"]:
            if not isinstance(vocab.get(level), list):
                raise ValueError(f"'{level}' must be a list.")
            vocab[level] = [word for word in vocab[level] if word in text]
        return vocab
    except (json.JSONDecodeError, ValueError) as e:
        raise ValueError(f"Invalid response structure: {e}\nResponse content: {content}")




def add_vocab_to_paginated_story(state: dict) -> dict:
    """
    Adds vocabulary words to a paginated story.

    Args:
        state (dict): The reading context structure as it exists in the json file.

    Returns:
        dict: The updated story with vocabulary words added.
    """
    story = state.get("reading_context")
    
    
    for chapter in tqdm(story.get("chapters", []), desc=f"Processing {story.get('book_title')}"):
        
        text = chapter.get("text", "")
        filtered_text = filter_words(text)
        vocab = select_vocab_words(filtered_text)
        
        chapter["vocab_words"] = {
            "easy": vocab.get("easy", []),
            "medium": vocab.get("medium", []),
            "hard": vocab.get("hard", [])
        }
    return story



if __name__ == "__main__":
    path_to_books = "../../assets/books"
    for dir in os.listdir(path_to_books):
        dir_path = os.path.join(path_to_books, dir)
        if os.path.isdir(dir_path):
            for file in os.listdir(dir_path):
                if file.endswith(".json"):
                    file_path = os.path.join(dir_path, file)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        story = json.load(f)
                    updated_story = add_vocab_to_paginated_story(story)
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(updated_story, f, ensure_ascii=False, indent=4)