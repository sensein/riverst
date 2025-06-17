#!/usr/bin/env python3

from openai import OpenAI
import sys

client = OpenAI()

def cancel_batch(batch_id: str):
    """
    Cancels a batch job.
    
    Args:
        batch_id (str): The batch job ID to cancel
    """
    try:
        # Cancel the batch
        cancelled_batch = client.batches.cancel(batch_id)
        
        print(f"✅ Batch {batch_id} has been cancelled")
        print(f"Status: {cancelled_batch.status}")
        
        if hasattr(cancelled_batch, 'request_counts'):
            counts = cancelled_batch.request_counts
            print(f"Request counts:")
            print(f"  Total: {counts.total}")
            print(f"  Completed: {counts.completed}")
            print(f"  Failed: {counts.failed}")
            
            if counts.completed > 0:
                print(f"\n💡 Note: {counts.completed} requests were completed before cancellation.")
                print("You can still retrieve partial results if needed.")
        
        return cancelled_batch
        
    except Exception as e:
        print(f"❌ Error cancelling batch: {e}")
        return None

def main():
    if len(sys.argv) != 2:
        print("Usage: python batch_cancel.py <batch_id>")
        print("Example: python batch_cancel.py batch_684839f54f588190a62ed22f7609906e")
        sys.exit(1)
    
    batch_id = sys.argv[1]
    
    # Confirm cancellation
    response = input(f"Are you sure you want to cancel batch {batch_id}? (y/N): ")
    if response.lower() != 'y':
        print("Cancellation aborted.")
        sys.exit(0)
    
    cancel_batch(batch_id)

if __name__ == "__main__":
    main()