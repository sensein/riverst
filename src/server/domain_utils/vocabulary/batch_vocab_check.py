#!/usr/bin/env python3

from openai import OpenAI
import sys
from datetime import datetime

client = OpenAI()

def check_batch_status(batch_id: str):
    """
    Checks the status of a batch job.
    
    Args:
        batch_id (str): The batch job ID
    """
    try:
        batch_job = client.batches.retrieve(batch_id)
        
        print(f"Batch ID: {batch_job.id}")
        print(f"Status: {batch_job.status}")
        print(f"Created at: {datetime.fromtimestamp(batch_job.created_at).strftime('%Y-%m-%d %H:%M:%S')}")
        
        if hasattr(batch_job, 'request_counts'):
            counts = batch_job.request_counts
            print(f"Request counts:")
            print(f"  Total: {counts.total}")
            print(f"  Completed: {counts.completed}")
            print(f"  Failed: {counts.failed}")
            
            if counts.total > 0:
                progress = (counts.completed / counts.total) * 100
                print(f"  Progress: {progress:.1f}%")
        
        if batch_job.status == "completed":
            print(f"Output file ID: {batch_job.output_file_id}")
            if hasattr(batch_job, 'completed_at'):
                completion_time = datetime.fromtimestamp(batch_job.completed_at).strftime('%Y-%m-%d %H:%M:%S')
                print(f"Completed at: {completion_time}")
        
        elif batch_job.status == "failed":
            print("❌ Batch failed!")
            if hasattr(batch_job, 'errors') and batch_job.errors:
                print("Errors:")
                for error in batch_job.errors:
                    print(f"  - {error}")
        
        elif batch_job.status == "in_progress":
            print("⏳ Batch is in progress...")
            if hasattr(batch_job, 'expires_at'):
                expires_at = datetime.fromtimestamp(batch_job.expires_at).strftime('%Y-%m-%d %H:%M:%S')
                print(f"Expires at: {expires_at}")
        
        elif batch_job.status == "validating":
            print("🔍 Batch is being validated...")
        
        elif batch_job.status == "finalizing":
            print("🏁 Batch is finalizing...")
        
        else:
            print(f"Status: {batch_job.status}")
        
        return batch_job.status
        
    except Exception as e:
        print(f"Error checking batch status: {e}")
        return None

def main():
    if len(sys.argv) != 2:
        print("Usage: python batch_vocab_check.py <batch_id>")
        print("Example: python batch_vocab_check.py batch_abc123")
        sys.exit(1)
    
    batch_id = sys.argv[1]
    status = check_batch_status(batch_id)
    
    if status == "completed":
        print("\n✅ Batch completed! You can now run the completion script.")
    elif status in ["failed", "expired", "cancelled"]:
        print(f"\n❌ Batch ended with status: {status}")
    else:
        print(f"\n⏳ Batch is still processing. Current status: {status}")
        print("Check again later or wait for completion.")

if __name__ == "__main__":
    main()