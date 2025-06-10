# Book Vocabulary Extraction Guide

This guide shows you how to automatically extract and categorize vocabulary words from your digital book collection using AI-powered analysis.

## What This System Does

The vocabulary extraction system analyzes your story chapters and automatically identifies **Tier 2 vocabulary words** using research-based criteria. Tier 2 words are:

- **Cross-domain academic and literary words** that occur widely across genres, marking written style rather than casual conversation
- **Precision enhancers** that add nuance beyond basic conversational vocabulary (Tier 1)
- **Not technical jargon** (Tier 3) but sophisticated enough to merit instruction
- **Examples include:**
  - Academic: *analyze, coordinate, duration, significant, establish, contrast, factor*
  - Literary: *remorse, solace, surreptitious, stride, fortunate, acquire, contemplate*

The system **excludes:**
- **Tier 1 words**: High-frequency conversational words (*walk, get, big, happy, said*)
- **Tier 3 words**: Technical discipline-specific terms (*photosynthesis, algorithm, protagonist*)
- **Proper nouns**: Names, places, brands
- **Very rare/archaic words**: Words unlikely to be encountered again

For each chapter, the system extracts vocabulary and organizes words into three grade-appropriate levels:
- **Grade 4**: Accessible Tier 2 vocabulary words appropriate for 4th grade reading level
- **Grade 5**: Intermediate Tier 2 words suitable for 5th grade complexity
- **Grade 6**: Advanced Tier 2 vocabulary appropriate for 6th grade level

**Target extraction rate**: 8-12 high-quality Tier 2 words per 10,000 words of text (adjusted based on text richness).

## Before You Start

### Prerequisites
- Python 3.7 or higher
- OpenAI API account and API key
- Your books stored as JSON files with chapter structure

### Required Python packages:
```bash
pip install openai pandas tqdm
```

### Set up your OpenAI API key:
```bash
export OPENAI_API_KEY="your-api-key-here"
```

### Expected File Structure
Your books should be organized like this:
```
assets/
└── books/
    ├── book1/
    │   └── story.json
    ├── book2/
    │   └── story.json
    └── book3/
        └── story.json
```

Each JSON file should have this structure:
```json
{
  "reading_context": {
    "book_title": "The Great Adventure",
    "chapters": [
      {
        "text": "Chapter content goes here...",
        "title": "Chapter 1"
      }
    ]
  }
}
```

After processing, vocabulary will be added:
```json
{
  "reading_context": {
    "book_title": "The Great Adventure", 
    "chapters": [
      {
        "text": "Chapter content goes here...",
        "title": "Chapter 1",
        "vocab_words": {
          "grade_4": ["word1", "word2"],
          "grade_5": ["word1", "word2"],
          "grade_6": ["word1", "word2"] 
        }
      }
    ]
  }
}
```

## Two Processing Options

Choose the approach that best fits your needs:

### Option 1: Real-Time Processing (Recommended for Getting Started)
**Best for:** Small collections (< 500 chapters), immediate results, testing the system

- ✅ See results immediately as each chapter is processed
- ✅ Simple single-script workflow
- ✅ Easy to stop and restart
- ✅ Real-time progress monitoring
- ❌ Higher cost (full API pricing)
- ❌ Slower for large collections
- ❌ Subject to rate limits

### Option 2: Batch Processing (Recommended for Large Collections)  
**Best for:** Large collections (500+ chapters), cost optimization, production use

- ✅ 50% lower cost through batch pricing
- ✅ Process hundreds of chapters simultaneously
- ✅ Higher rate limits, no throttling
- ✅ Continues processing even if your computer goes offline
- ❌ Results take a few hours (up to 24h, usually much faster)
- ❌ More complex multi-step workflow

## Quick Start: Real-Time Processing

Perfect for testing the system or processing smaller collections.

### 1. Run the extraction script

**Option A: Standard processing**
```bash
python extract_vocabulary.py
```

**Option B: Research-enhanced processing (recommended)**
```bash
python extract_vocabulary_improved.py
```

The improved version includes:
- ✅ Research-based Tier 2 criteria from Beck & McKeown, Coxhead, et al.
- ✅ Better filtering of Tier 1 (high-frequency) and Tier 3 (technical) words
- ✅ Quality statistics and extraction rate monitoring
- ✅ Enhanced validation and error handling

### 2. Monitor progress
You'll see a progress bar for each book being processed:
```
Processing The Great Adventure: 100%|██████| 15/15 [02:30<00:00, 10.2s/chapter]
✅ Completed: ../../assets/books/adventure/story.json
Processing Mystery Manor: 45%|████▌     | 9/20 [01:15<01:30, 8.2s/chapter]
```

### 3. Handle interruptions
If the script stops for any reason, simply run it again. It will skip chapters that already have vocabulary words.

## Advanced: Batch Processing for Large Collections

Ideal for processing large collections efficiently and cost-effectively.

### Step 1: Start Batch Processing
```bash
python batch_vocab_start.py
```

This will:
- Scan all your books and count chapters to process
- Create batch tasks for OpenAI's Batch API
- Upload tasks and submit the batch job
- Generate tracking files with timestamps

Example output:
```
Creating batch tasks...
Created 1,247 batch tasks
Batch tasks saved to: vocab_batch_tasks_20241210_143022.jsonl
Metadata saved to: vocab_batch_metadata_20241210_143022.json
Uploading batch file to OpenAI...
File uploaded with ID: file-abc123
Creating batch job...
Batch job created with ID: batch-def456
Status: validating

Batch info saved to: vocab_batch_info_20241210_143022.json

To check status, run:
python batch_vocab_check.py batch-def456

When complete, run:
python batch_vocab_complete.py vocab_batch_info_20241210_143022.json
```

### Step 2: Monitor Progress (Optional)
Check batch status anytime:
```bash
python batch_vocab_check.py batch-def456
```

Example output:
```
Batch ID: batch-def456
Status: in_progress
Created at: 2024-12-10 14:30:22
Request counts:
  Total: 1247
  Completed: 892
  Failed: 0
  Progress: 71.5%
⏳ Batch is in progress...
```

### Step 3: Process Results When Complete
Once the batch shows "completed" status:
```bash
python batch_vocab_complete.py vocab_batch_info_20241210_143022.json
```

This will:
- Download all results from OpenAI
- Map vocabulary back to the correct chapters
- Update your original JSON files
- Provide a completion summary

Example output:
```
Processing batch batch-def456...
Batch status: completed
Loaded metadata for 1247 tasks
Results saved to: vocab_batch_results_20241210_143022.jsonl
Parsed 1247 results
Updating 45 files...
Batch processing complete!
Updated 45 files
Added vocabulary to 1247 chapters
```

## What You Get

After processing, each chapter in your books will have vocabulary words added:

```json
{
  "reading_context": {
    "book_title": "The Great Adventure",
    "chapters": [
      {
        "text": "The intrepid explorer ventured through the treacherous mountain pass...",
        "title": "Chapter 1",
        "vocab_words": {
          "grade_4": ["explorer", "mountain", "journey"],
          "grade_5": ["intrepid", "ventured", "treacherous"],
          "grade_6": ["perilous", "arduous", "expedition"]
        }
      }
    ]
  }
}
```

## Quality Control

The system implements research-based quality controls following Beck & McKeown's vocabulary frameworks:

### Evidence-Based Filtering
- **Tier 1 Exclusion**: Removes high-frequency conversational words (first 2,000 most common spoken words)
- **Tier 3 Exclusion**: Filters out technical discipline-specific terminology  
- **Cross-Domain Validation**: Prioritizes words useful across multiple academic and literary contexts
- **Frequency Analysis**: Targets words that appear often enough in school texts to merit instruction

### Text Processing
- **Lemmatization**: Groups word variants (e.g., "analyzing" → "analyze")
- **Context Validation**: Only includes words that actually appear in the source text
- **Proper Noun Filtering**: Excludes names, places, and brand terms
- **Precision Focus**: Prioritizes words that add nuance beyond basic vocabulary

### Academic Standards
- **Cross-Disciplinary Focus**: Includes academic words useful across subjects (*coordinate, establish, factor*)
- **Literary Enrichment**: Captures vivid narrative vocabulary (*remorse, solace, surreptitious*)
- **Grade-Level Appropriateness**: Categorizes vocabulary by developmental reading levels (grades 4-6)
- **Instructional Value**: Selects words that enhance both comprehension and expression
- **Research-Based**: Follows Beck & McKeown's three-tier vocabulary framework

### Error Handling
- **JSON Validation**: Ensures properly formatted responses from AI processing
- **Duplicate Prevention**: No word appears across multiple grade levels
- **Content Verification**: Validates extracted words against original text
- **Fallback Processing**: Handles edge cases and processing errors gracefully

## Cost Estimation

### Real-Time Processing
- Approximate cost: $0.01-0.03 per chapter (depending on chapter length)
- For 1000 chapters: ~$10-30

### Batch Processing  
- Approximate cost: $0.005-0.015 per chapter (50% discount)
- For 1000 chapters: ~$5-15

*Costs may vary based on OpenAI's current pricing and chapter length.*

## Troubleshooting

### Common Issues

**"No chapters found to process"**
- Check that your JSON files have the correct structure
- Verify the `reading_context.chapters` path exists
- Ensure chapters have `text` content

**"API key not found"**
- Set your OpenAI API key: `export OPENAI_API_KEY="your-key"`
- Or create a `.env` file with `OPENAI_API_KEY=your-key`

**Real-time processing is slow**
- Consider switching to batch processing for large collections
- Check your internet connection
- Verify you're not hitting rate limits

**Batch processing stuck in "validating"**
- This is normal and usually takes 1-5 minutes
- If stuck for over 10 minutes, check with `batch_vocab_check.py`

**Some chapters missing vocabulary**
- Chapters with very short text may not yield vocabulary words
- Check that the chapter text contains appropriate vocabulary
- Very simple text may not have Tier 2 words

### Getting Help

**Check processing logs:**
- Real-time: Look for error messages in terminal output
- Batch: Check the completion script output for detailed errors

**Verify file structure:**
```bash
# Check a sample file structure
python -c "import json; print(json.dumps(json.load(open('path/to/book.json')), indent=2)[:500])"
```

**Test with a single book:**
- Copy one book to a test directory
- Update the script paths to process just that book
- Verify the output before processing your full collection
