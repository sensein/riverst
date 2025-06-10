#!/usr/bin/env python3

from openai import OpenAI
import json
import string
from collections import Counter
import os
from tqdm import tqdm
from datetime import datetime

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

def create_batch_tasks(path_to_books: str) -> tuple[list, dict]:
    """
    Creates batch tasks for all chapters in all books.
    
    Returns:
        tuple: (tasks_list, metadata_dict)
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
    
    tasks = []
    metadata = {}
    task_counter = 0
    
    for dir_name in tqdm(os.listdir(path_to_books), desc="Scanning directories"):
        dir_path = os.path.join(path_to_books, dir_name)
        if os.path.isdir(dir_path):
            for file_name in os.listdir(dir_path):
                if file_name.endswith(".json"):
                    file_path = os.path.join(dir_path, file_name)
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            story = json.load(f)
                        
                        reading_context = story.get("reading_context", {})
                        chapters = reading_context.get("chapters", [])
                        
                        for chapter_idx, chapter in enumerate(chapters):
                            text = chapter.get("text", "")
                            if text.strip():  # Only process chapters with content
                                filtered_text = filter_words(text)
                                if filtered_text.strip():  # Only if there are words to process
                                    custom_id = f"task-{task_counter}"
                                    
                                    # Store metadata for reconstruction
                                    metadata[custom_id] = {
                                        "file_path": file_path,
                                        "chapter_index": chapter_idx,
                                        "dir_name": dir_name,
                                        "file_name": file_name
                                    }
                                    
                                    # Create batch task
                                    task = {
                                        "custom_id": custom_id,
                                        "method": "POST",
                                        "url": "/v1/chat/completions",
                                        "body": {
                                            "model": "gpt-4o-mini",
                                            "temperature": 0.3,
                                            "response_format": { 
                                                "type": "json_object"
                                            },
                                            "messages": [
                                                {"role": "system", "content": system_message},
                                                {"role": "user", "content": filtered_text}
                                            ]
                                        }
                                    }
                                    
                                    tasks.append(task)
                                    task_counter += 1
                    
                    except Exception as e:
                        print(f"Error processing {file_path}: {e}")
                        continue
    
    return tasks, metadata

def main():
    path_to_books = "../../assets/books"
    
    print("Creating batch tasks...")
    tasks, metadata = create_batch_tasks(path_to_books)
    
    if not tasks:
        print("No tasks to process!")
        return
    
    print(f"Created {len(tasks)} batch tasks")
    
    # Create timestamp for unique filenames
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save batch tasks to JSONL file
    batch_file_name = f"vocab_batch_tasks_{timestamp}.jsonl"
    with open(batch_file_name, 'w') as file:
        for task in tasks:
            file.write(json.dumps(task) + '\n')
    
    # Save metadata for later use
    metadata_file_name = f"vocab_batch_metadata_{timestamp}.json"
    with open(metadata_file_name, 'w') as file:
        json.dump(metadata, file, indent=2)
    
    print(f"Batch tasks saved to: {batch_file_name}")
    print(f"Metadata saved to: {metadata_file_name}")
    
    # Upload file to OpenAI
    print("Uploading batch file to OpenAI...")
    batch_file = client.files.create(
        file=open(batch_file_name, "rb"),
        purpose="batch"
    )
    
    print(f"File uploaded with ID: {batch_file.id}")
    
    # Create batch job
    print("Creating batch job...")
    batch_job = client.batches.create(
        input_file_id=batch_file.id,
        endpoint="/v1/chat/completions",
        completion_window="24h"
    )
    
    print(f"Batch job created with ID: {batch_job.id}")
    print(f"Status: {batch_job.status}")
    
    # Save batch info for the completion script
    batch_info = {
        "batch_id": batch_job.id,
        "batch_file_id": batch_file.id,
        "metadata_file": metadata_file_name,
        "batch_file": batch_file_name,
        "timestamp": timestamp,
        "total_tasks": len(tasks)
    }
    
    batch_info_file = f"vocab_batch_info_{timestamp}.json"
    with open(batch_info_file, 'w') as file:
        json.dump(batch_info, file, indent=2)
    
    print(f"Batch info saved to: {batch_info_file}")
    print("\nTo check status, run:")
    print(f"python batch_vocab_check.py {batch_job.id}")
    print("\nWhen complete, run:")
    print(f"python batch_vocab_complete.py {batch_info_file}")

if __name__ == "__main__":
    main()