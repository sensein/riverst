# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands
- Run server: `python main.py [--host HOSTNAME] [--port PORT] [--verbose]`
- Virtual env: `conda create -n riverst python=3.11 -y && conda activate riverst`
- Install: `pip install --no-deps piper-tts && pip install -r requirements.txt`
- Lint: `flake8 .`
- Type check: `mypy .`

## Code Style
- Type hints required for all functions and variables
- Google-style docstrings for classes and functions
- 4-space indentation, 100 character line limit
- snake_case for variables/functions, CamelCase for classes
- Async/await pattern for most I/O operations
- Properly handle errors with try/except blocks
- Organize imports: stdlib, third-party, local (alphabetically within groups)
- Prefer composition over inheritance
- Use f-strings for string formatting
- Use descriptive variable names

## Debugging Notes
- Flow transitions: Added `TRANSITION_DEBUG` logs in handlers.py to track node transitions
- Flow initialization: Added `DEBUG` logs in flow_component_factory.py
- Function calls: Added `FUNCTION_DEBUG` logs in bot.py to monitor LLM function calls
- 5/26/2025: Added monitoring for conversation flow transitions to debug issue with warm-up to vocabulary transition