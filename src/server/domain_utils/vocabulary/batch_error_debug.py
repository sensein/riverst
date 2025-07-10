#!/usr/bin/env python3

from openai import OpenAI
import json
import sys
import os
from tqdm import tqdm
from collections import defaultdict

client = OpenAI()

def validate_vocab_response(content: str, original_text: str) -> dict:
    """
    Validates and cleans the vocabulary response from GPT-4.
    
    Args:
        content (str): The raw response content
        original_text (str): The original filtered text to validate against
        
    Returns:
        dict: Validated vocabulary dictionary
    """
    try:
        vocab = json.loads(content)
        
        # Ensure structure
        for level in ["easy", "medium", "hard"]:
            if not isinstance(vocab.get(level), list):
                vocab[level] = []
            # Filter to only include words that appear in original text
            vocab[level] = [word for word in vocab[level] if word in original_text]
        
        return vocab
    except (json.JSONDecodeError, ValueError) as e:
        print(f"Invalid vocab response: {e}")
        return {"easy": [], "medium": [], "hard": []}

def process_batch_results(batch_info_file: str):
    """
    Processes completed batch results and updates the original JSON files.
    
    Args:
        batch_info_file (str): Path to the batch info JSON file
    """
    
    # Load batch info
    with open(batch_info_file, 'r') as f:
        batch_info = json.load(f)
    
    batch_id = batch_info["batch_id"]
    metadata_file = batch_info["metadata_file"]
    
    print(f"Processing batch {batch_id}...")
    
    # Check batch status
    batch_job = client.batches.retrieve(batch_id)
    print(f"Batch status: {batch_job.status}")
    
    if batch_job.status != "completed":
        print(f"Batch is not completed yet. Current status: {batch_job.status}")
        if batch_job.status == "failed":
            print("Batch failed!")
            if hasattr(batch_job, 'errors'):
                print(f"Errors: {batch_job.errors}")
        return
    
    # Check if any requests actually completed
    if hasattr(batch_job, 'request_counts'):
        counts = batch_job.request_counts
        print(f"Request counts - Total: {counts.total}, Completed: {counts.completed}, Failed: {counts.failed}")
        
        if counts.completed == 0:
            print("❌ No requests completed successfully!")
            print("All requests failed. Use batch_error_debug.py to investigate:")
            print(f"python batch_error_debug.py {batch_id}")
            return
    
    # Check if output file exists
    if not hasattr(batch_job, 'output_file_id') or not batch_job.output_file_id:
        print("❌ No output file available - all requests likely failed.")
        print("Use batch_error_debug.py to investigate:")
        print(f"python batch_error_debug.py {batch_id}")
        return
    
    # Load metadata
    with open(metadata_file, 'r') as f:
        metadata = json.load(f)
    
    print(f"Loaded metadata for {len(metadata)} tasks")
    
    # Download results
    result_file_id = batch_job.output_file_id
    try:
        result_content = client.files.content(result_file_id).content
    except Exception as e:
        print(f"❌ Error downloading results: {e}")
        return
    
    # Save results to local file
    timestamp = batch_info["timestamp"]
    result_file_name = f"vocab_batch_results_{timestamp}.jsonl"
    
    with open(result_file_name, 'wb') as file:
        file.write(result_content)
    
    print(f"Results saved to: {result_file_name}")
    
    # Parse results
    results = []
    with open(result_file_name, 'r') as file:
        for line in file:
            json_object = json.loads(line.strip())
            results.append(json_object)
    
    print(f"Parsed {len(results)} results")
    
    # Group results by file for efficient processing
    file_updates = defaultdict(dict)
    
    for result in tqdm(results, desc="Processing results"):
        custom_id = result['custom_id']
        
        if custom_id not in metadata:
            print(f"Warning: No metadata found for {custom_id}")
            continue
        
        task_metadata = metadata[custom_id]
        file_path = task_metadata["file_path"]
        chapter_index = task_metadata["chapter_index"]
        
        # Extract vocabulary from result
        if 'response' in result and 'body' in result['response']:
            response_body = result['response']['body']
            if 'choices' in response_body and len(response_body['choices']) > 0:
                content = response_body['choices'][0]['message']['content']
                
                # We need the original filtered text to validate vocab
                # We'll re-read and re-filter here for validation
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        story_data = json.load(f)
                    
                    chapters = story_data.get("reading_context", {}).get("chapters", [])
                    if chapter_index < len(chapters):
                        from batch_vocab_start import filter_words  # Import our filter function
                        original_text = chapters[chapter_index].get("text", "")
                        filtered_text = filter_words(original_text)
                        
                        vocab = validate_vocab_response(content, filtered_text)
                        
                        # Store the update
                        if file_path not in file_updates:
                            file_updates[file_path] = {}
                        
                        file_updates[file_path][chapter_index] = {
                            "easy": vocab.get("easy", []),
                            "medium": vocab.get("medium", []),
                            "hard": vocab.get("hard", [])
                        }
                
                except Exception as e:
                    print(f"Error processing result for {custom_id}: {e}")
                    continue
        else:
            print(f"Invalid result format for {custom_id}")
    
    # Apply updates to files
    print(f"Updating {len(file_updates)} files...")
    
    for file_path, chapter_updates in tqdm(file_updates.items(), desc="Updating files"):
        try:
            # Load current file
            with open(file_path, 'r', encoding='utf-8') as f:
                story_data = json.load(f)
            
            # Apply chapter updates
            chapters = story_data.get("reading_context", {}).get("chapters", [])
            
            for chapter_index, vocab_words in chapter_updates.items():
                if chapter_index < len(chapters):
                    chapters[chapter_index]["vocab_words"] = vocab_words
                else:
                    print(f"Warning: Chapter index {chapter_index} out of range for {file_path}")
            
            # Save updated file
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(story_data, f, ensure_ascii=False, indent=4)
                
        except Exception as e:
            print(f"Error updating file {file_path}: {e}")
    
    print("Batch processing complete!")
    print(f"Updated {len(file_updates)} files")
    
    # Summary
    total_chapters = sum(len(updates) for updates in file_updates.values())
    print(f"Added vocabulary to {total_chapters} chapters")

def main():
    if len(sys.argv) != 2:
        print("Usage: python batch_vocab_complete.py <batch_info_file>")
        print("Example: python batch_vocab_complete.py vocab_batch_info_20241210_143022.json")
        sys.exit(1)
    
    batch_info_file = sys.argv[1]
    
    if not os.path.exists(batch_info_file):
        print(f"Error: Batch info file '{batch_info_file}' not found")
        sys.exit(1)
    
    process_batch_results(batch_info_file)

if __name__ == "__main__":
    main()