# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands
- Run app: `python app.py` (accessible at http://127.0.0.1:5000/)
- Install dependencies: `pip install flask`

## Code Style Guidelines
- Python: Follow PEP 8 style guide
- JavaScript: 4-space indentation, camelCase for variables/functions
- Error handling: Use try/except with specific exceptions in Python, try/catch in JS
- Function naming: Descriptive, verb_noun format for Python, camelCase for JS
- Comments: Use section headers with `// ==== Section Name ====` format
- HTML/CSS: Use Bootstrap components and classes for UI elements

## File Structure
- app.py: Flask backend with JSON generation logic
- static/js/script.js: Main UI functionality
- static/js/file-loader.js: File handling
- templates/index.html: Main application interface
- static/output/: Generated JSON files destination