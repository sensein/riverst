# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is Riverst

Riverst is a platform for building, running, and analyzing interactive speech-driven user-avatar conversations. It enables real-time multimodal avatar interactions and automated post-session analysis. Built on [Pipecat](https://github.com/pipecat-ai/pipecat) for real-time AI pipelines and WebRTC for audio/video transport.

## Repository Structure

```
src/
  server/         # FastAPI backend (Python 3.11+)
  client/react/   # React 19 + TypeScript frontend
  flow-builder/   # Flask app for visually creating flow JSON configs
notes/            # Guides and documentation
KIVA/             # Educational content assets
```

## Development Commands

### Server (Python)

```bash
cd src/server
conda create -n riverst python=3.11
conda activate riverst
conda install -c conda-forge "ffmpeg=7.*"
pip install -r requirements.txt
python main.py                    # Runs on port 7860
```

### Client (React)

```bash
cd src/client/react
npm install
npm run dev          # Dev server on port 5173
npm run build        # Production build
npm run lint         # ESLint
npm run type-check   # TypeScript validation
npm run format       # Prettier
```

### Flow Builder

```bash
cd src/flow-builder
pip install flask
python app.py        # Runs on http://127.0.0.1:5000/
```

### Full Stack via Docker

```bash
docker compose up --build
# Server: port 7860, Frontend: port 5173
```

### Code Quality

```bash
pre-commit install          # Set up hooks (do this once)
pre-commit run --all-files  # Run Black, Flake8, ESLint, Prettier
```

Python max line length is 120 (see `.flake8`). Use Google-style docstrings.

## Architecture

### Request Flow

1. User selects an activity → frontend fetches from `GET /api/activities`
2. User configures session → `POST /api/session` with config JSON
3. WebRTC negotiation → `POST /api/offer`
4. Backend loads the activity's `flow_config.json` and initializes Pipecat pipeline
5. Conversation runs: STT → LLM (following flow logic) → TTS → lipsync → avatar render
6. Session end → data saved to `src/server/sessions/`, optional senselab analysis

### Backend (`src/server/`)

- **`main.py`** — FastAPI app, route definitions, session/offer endpoints
- **`bot/core/`** — `bot_runner.py`, `component_factory.py`, `pipeline_orchestrator.py`, `event_manager.py`
- **`bot/components/`** — LLM tools, memory, transcription handlers
- **`bot/flows/`** — Flow state machine: loaders, handlers, models (wraps `pipecat-ai-flows`)
- **`bot/processors/`** — Audio/video/speech processing (lipsync, analyzers, buffers)
- **`bot/transport/`** — WebRTC transport and service config
- **`bot/monitoring/`** — Metrics logging and profiling
- **`authorization/`** — Google OAuth + JWT token management
- **`activities/`** — Pre-built activities, each with `session_config.json` and `flow_config.json`
- **`assets/activity_groups.json`** — Registry of all available activities

### Frontend (`src/client/react/`)

React 19 + TypeScript. Uses `@pipecat-ai/client-react` for the real-time agent connection, Three.js for avatar rendering, and Ant Design for UI. Authentication state via React Context.

Key areas: `ActivityCard`, `AvatarInteraction`, session management, WebRTC connection handling.

### Activities System

Each activity lives in `src/server/activities/<name>/` and contains:
- `session_config.json` — UI schema for user-facing settings
- `flow_config.json` — Conversation flow graph (nodes, transitions, prompts)

The Flow Builder (`src/flow-builder/`) is a visual tool for creating/editing flow JSON configs. See `src/server/activities/ACTIVITY_CREATION_GUIDE.md` for how to create new activities.

## Environment Setup

Copy and fill in `.env.example` files:
- `src/server/.env` — `OPENAI_API_KEY`, `HF_TOKEN`, optional TURN server creds, Google OAuth keys
- `src/client/react/.env` — server endpoint config

## Key Dependencies

- **Pipecat** (`pipecat-ai==0.0.89`) — real-time AI pipeline framework; supports OpenAI, Anthropic, Ollama for LLM; ElevenLabs, Kokoro, Silero for TTS; Whisper/Google for STT
- **pipecat-ai-flows** — conversation flow/state management
- **senselab** — post-session speech analysis and behavioral metrics
- **small-webrtc** — WebRTC transport layer

## Platform Notes

- Supported OS: macOS (Apple Silicon) and Ubuntu Linux. Not Windows.
- Sessions are stored in `src/server/sessions/` (gitignored).
- No automated test suite; testing is done via pre-commit hooks and manual integration testing.

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
at `specs/009-sandbox-s3-transcripts/plan.md`.
<!-- SPECKIT END -->
