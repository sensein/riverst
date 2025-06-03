# Server

A FastAPI server.

## Running the Server

1. Set up and activate your virtual environment:

```bash
conda create -n riverst python=3.11 -y
conda activate riverst
pip install --no-deps piper-tts && pip install -r requirements.txt
```

2. Copy `env.example` to `.env` and configure params.

3. [OPTIONAL] If you want to use `llama3.2` (or any `ollama` llm), you should first [install ollama on your machine](https://ollama.com/) and then run

```bash
ollama run llama3.2
```

4. [OPTIONAL] If you want to use `piper`, you should first download the voice model(s) you want from [here](https://github.com/rhasspy/piper/blob/9b1c6397698b1da11ad6cca2b318026b628328ec/VOICES.md) and then run 

```bash
git clone https://github.com/rhasspy/piper.git
cd piper/src/python_run
python3 -m piper.http_server --model <path_to_voices_folder>/en_GB-alba-medium.onnx --port 5001
python3 -m piper.http_server --model <path_to_voices_folder>/en_GB-alan-medium.onnx --port 5002
```

5. Run the server:

```bash
python server.py
```

## Utilities

### Gutenberg Book Converter

The server includes a utility to convert Project Gutenberg HTML books into the riverst JSON format. This allows you to add new books to the system.

#### Single File Conversion

```bash
# Convert a single HTML file
python -m utils.gutenberg_converter path/to/book.html

# Convert a zip file containing HTML and images
python -m utils.gutenberg_converter path/to/book.zip

# With custom output directory
python -m utils.gutenberg_converter path/to/book.html --output-dir custom/output/path

# Force overwrite existing files
python -m utils.gutenberg_converter path/to/book.html --force
```

#### Batch Processing

You can easily convert multiple books at once by placing the zip files in the `utils/book_converter/raw_downloads` directory and running:

```bash
# Process all books in the raw_downloads directory
python -m utils.gutenberg_converter --batch

# Force overwrite existing files
python -m utils.gutenberg_converter --batch --force
```

#### How to Get Books from Project Gutenberg

1. Go to [Project Gutenberg](https://www.gutenberg.org/) and find a book
2. Click on "Read this book online: HTML"
3. Download the HTML version (usually available as a zip file)
4. Place the zip file in `utils/book_converter/raw_downloads/`
5. Run the batch converter

The converter will:
1. Extract files from zip archives (if applicable)
2. Find and parse the HTML content
3. Extract chapters and organize content
4. Create the proper directory structure (book_name/audios/)
5. Generate vocabulary words for each chapter
6. Copy any associated images to an 'images' subdirectory
7. Create a properly formatted JSON file as required by the riverst system

Example:

```bash
# Single file conversion
python -m utils.gutenberg_converter assets/books/pg16-h/pg16-images.html

# Batch conversion
python -m utils.gutenberg_converter --batch
```

This will create/update the appropriate directories in `/assets/books/` with the converted content.