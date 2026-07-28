# Riverst Rebuild Specification

Status: Draft

Date: 2026-03-07

Branch: `codex/rebuild-spec`

## 1. Purpose

This document specifies how to rebuild Riverst from scratch while preserving the useful behavior present in the current repository and improving the architecture, testability, and deployment model.

The rebuilt system must support:

- real-time avatar conversations over WebRTC
- configurable activities with both free-form and structured flows
- audiobook playback with optional text and subtitle support
- session capture, review, and analysis
- avatar selection and external avatar creation
- researcher/operator workflows for configuring and sharing sessions
- a flow-authoring tool for structured activities

This spec is based on a repository review of the current codebase under `src/client/react`, `src/server`, and `src/flow-builder`.

## 2. Product Summary

Riverst is an interaction platform for speech-based avatar experiences. It combines:

- a React web client for setup, runtime interaction, and session review
- a FastAPI server that exposes auth, activity, content, session, and WebRTC endpoints
- a Pipecat-based bot runtime that assembles STT, LLM, TTS, flow, transcript, recording, and metrics components
- a lightweight Flask flow-builder used to create JSON flow definitions for advanced activities

In practice, the product serves three classes of users:

- end users interacting with avatars
- operators or researchers configuring sessions and reviewing results
- developers or designers authoring activities, flows, and content assets

## 3. Primary Use Cases

### 3.1 Free-form avatar interaction

- A user selects or creates an avatar.
- An operator configures a conversation.
- A shareable link or QR code is generated.
- The participant joins a real-time WebRTC session.
- The avatar responds with speech, optional animation, and optional transcript overlays.

### 3.2 Demo and study sessions

- An operator creates a preconfigured session.
- Participants join without full app navigation.
- Sessions can be ended with a completion identifier for Prolific-style studies.

### 3.3 Structured tutoring activities

- An operator selects a tutoring activity.
- The system loads an activity-specific schema and optional content resource.
- The bot follows a staged flow with checklist-based progression and variable retrieval.
- The session captures learning progress and can reference content such as chapters or vocabulary lists.

### 3.4 Audiobook support

- A user or operator selects a book and chapter.
- The system presents a player with optional audio, text, and word-level highlighting.
- A configurable link can be shared with another user.

### 3.5 Session review and analysis

- Recorded conversation turns are stored as audio plus JSON sidecars.
- Transcripts and aggregated metrics are generated.
- An operator can browse past sessions and inspect per-turn content and summary metrics.

### 3.6 Activity and flow authoring

- Developers define activity schemas and assets.
- Designers create advanced conversation flows in a browser-based editor.
- Flow definitions are stored as JSON and loaded at runtime.

## 4. Current Repository Components

| Component | Current location | Current responsibility | Features present today | Supported use cases |
| --- | --- | --- | --- | --- |
| React web client | `src/client/react` | Main user and operator UI | auth, homepage, avatar selection, avatar creation, activity settings, live session UI, audiobook pages, session list, session detail | all end-user and operator workflows |
| FastAPI API server | `src/server/main.py` | HTTP API and WebRTC offer endpoint | auth endpoints, activities, avatars, resources, session creation, session listing, session detail, audiobook endpoints, session-ending endpoints | all app-backed workflows |
| Bot runtime | `src/server/bot` | Real-time pipeline assembly and execution | Pipecat transport, STT/LLM/TTS selection, memory, transcript capture, audio recording, metrics, video buffering, animation tools | live avatar interaction |
| Activity system | `src/server/activities` and `src/server/assets` | Configurable activities and resources | JSON session schemas, advanced flow configs, content resources, activity grouping | tutoring, demo, free-form setup |
| Flow builder | `src/flow-builder` | JSON flow authoring tool | browser editor, node sequencing, variable definitions, handler generation, file save/load | advanced activity authoring |
| Static assets | `src/client/react/public`, `src/server/assets`, `public` | avatars, animations, logos, screenshots, audiobook assets | built-in avatars, idle animations, icons, logo, audiobook WAVs | avatar UX, demo content, landing docs |
| Authorization module | `src/server/authorization` | Google auth and JWT handling | Google sign-in, bypass auth, whitelist file, rejected login logging | private deployments, dev mode |

## 5. Feature Inventory By Component

### 5.1 Client application

#### Homepage and activity catalog

Current implementation:

- loads grouped activities from `/api/activities`
- shows activity families including avatar customization, free-play, KIVA, and L2 learning
- routes activity cards to configuration or playback pages

Must preserve:

- activity groups driven by server-side JSON
- ability to disable activities without removing code
- activity cards that route to either a settings flow or a direct player/runtime flow

#### Authentication

Current implementation:

- checks `/api/auth/status`
- supports Google auth or automatic bypass auth
- stores JWT in local storage
- wraps authenticated routes in `AuthProvider` and `ProtectedRoute`

Must preserve:

- production-grade auth mode
- development bypass mode
- authenticated API helper
- route protection for operator views

#### Avatar selection and avatar creation

Current implementation:

- built-in avatar library loaded from `/api/avatars`
- 3D preview rendering with React Three Fiber
- Ready Player Me iframe integration for custom avatar creation
- chosen avatar persisted in local storage

Must preserve:

- server-driven built-in avatars
- external avatar creation flow
- preview before selection
- avatar metadata required by voice and lip-sync logic

#### Activity settings and session creation

Current implementation:

- loads JSON schema from activity-specific endpoint
- renders a settings form
- merges form values with selected avatar
- creates a server-side session with `/api/session`
- displays a shareable link and QR code

Must preserve:

- schema-driven configuration UI
- link/QR session sharing
- session bootstrap payload persisted server-side
- clean path from operator setup to participant runtime

#### Real-time avatar interaction runtime

Current implementation:

- unauthenticated route at `/avatar-interaction/:sessionId`
- loads stored session config
- records a device fingerprint
- connects to Pipecat over small-webrtc transport
- renders transcripts and avatar interaction controls
- supports study completion flow with generated completion ID

Must preserve:

- direct-join session route
- resilient reconnect or re-entry behavior
- transcript overlays
- avatar embodiment modes
- session completion state for study workflows

#### Audiobook pages

Current implementation:

- `/listen-to-an-audio-book` lists books and chapters
- `/audio-player` plays a chapter segment by segment
- flags control audio, text, subtitles, and whether in-player settings are shown
- generated links can be shared

Must preserve:

- server-driven book/chapter catalog
- word-level highlighting
- flexible share links
- support for both guided reading and self-study use cases

#### Session review

Current implementation:

- authenticated session list page
- grouping by user ID
- session detail page with transcripts, audio playback, feature modal, and metrics modal

Must preserve:

- operator access to past sessions
- per-turn audio and transcript inspection
- aggregated metrics summary

### 5.2 API server

#### Auth and identity

Endpoints present today:

- `GET /api/auth/status`
- `POST /api/auth/bypass`
- `POST /api/auth/google`
- `GET /api/auth/me`

Responsibilities:

- expose auth mode to the client
- exchange Google token for JWT
- enforce bearer auth on protected endpoints
- support local development without Google auth

#### Session management

Endpoints present today:

- `POST /api/session`
- `GET /api/session_config/{session_id}`
- `GET /api/sessions`
- `GET /api/session/{session_id}`
- `POST /api/session/add_device_fingerprint`
- `GET /api/check_session_ended/{session_id}`
- `GET /api/end_session/{session_id}`

Responsibilities:

- create session IDs and directories
- persist configuration
- expose session outputs for review
- track device fingerprints
- mark sessions complete for study workflows

#### Activity and resource catalog

Endpoints present today:

- `GET /api/activities`
- `GET /api/activities/{activity_name}/session_config`
- `GET /api/resources`
- `GET /api/resources/indices`
- `GET /api/avatars`
- `GET /api/audiobooks`
- `GET /api/audiobook_info`

Responsibilities:

- serve activity group metadata
- serve JSON schema for settings UI
- filter options based on available API keys
- expose built-in avatars and content resources

#### WebRTC bootstrap

Endpoint present today:

- `POST /api/offer`

Responsibilities:

- accept SDP offers
- create or reuse WebRTC peer connections
- launch the bot runtime in the background
- return SDP answers

### 5.3 Bot runtime

#### Pipeline assembly

Current implementation:

- selects classic or end-to-end modality
- supports OpenAI, Ollama, Whisper, Kokoro, and related services depending on config
- assembles Pipecat processors for STT, LLM, TTS, transcript, lip sync, recording, metrics, and video

Must preserve:

- provider pluggability
- config-driven assembly
- separation between transport, model services, processors, and flow layer

#### Avatar behavior and tools

Current implementation:

- tool schema for animations
- tool schema for ending the conversation
- instruction building from task prompt, avatar personality, languages, and animation support

Must preserve:

- runtime-callable tool handlers
- prompt construction from structured config
- animation restrictions defined by activity

#### Memory and continuity

Current implementation:

- short-term memory can resume an interrupted session
- long-term memory can load prior user sessions
- session cleanup occurs when short-term memory is disabled

Must preserve:

- explicit session memory modes
- predictable cleanup behavior
- safe isolation of user context

#### Advanced flows

Current implementation:

- optional flow manager via `pipecat_flows`
- staged progression with checklist verification
- activity and user variables
- indexable content retrieval
- transition logic between nodes

Must preserve:

- stage-based tutoring or guided conversations
- runtime retrieval of structured content
- node-local instructions and tool exposure
- reusable flow definitions independent of code changes

#### Recording and analysis

Current implementation:

- saves user and agent turn WAV files
- stores transcript JSON
- aggregates metrics into `metrics_summary.json`
- optionally triggers audio analysis on disconnect
- saves video buffers when enabled

Must preserve:

- deterministic session artifact layout
- post-session metrics summary
- optional analysis pipeline
- operator-readable session outputs

### 5.4 Flow builder

Current implementation:

- separate Flask app and static browser UI
- creates flow JSON with nodes, checklist items, user fields, variables, handlers, and actions
- supports editing existing files and generating new ones

Must preserve:

- a non-code authoring path for structured activities
- validation of flow shape
- save/load workflow for designers

## 6. Rebuild Goals

The rebuild should keep product behavior but improve the engineering baseline.

### 6.1 Functional goals

- reach feature parity for the existing major use cases
- preserve schema-driven activities and flow-driven tutoring
- preserve session review and analysis outputs
- preserve external avatar creation and built-in avatar support

### 6.2 Engineering goals

- use test-driven development for new modules and endpoints
- standardize Python environment management on `uv`
- provide Docker-based local development and CI execution
- replace weakly typed JSON plumbing with validated contracts where possible
- separate product concerns clearly enough that components can be tested in isolation

### 6.3 Non-goals for the first rebuild

- full Windows support
- immediate migration to a distributed microservice architecture
- replacing every third-party provider at once
- rebuilding the current research content set from scratch

## 7. Repository Review Findings That Affect The Rebuild

- The repository contains both `requirements.txt`-style and `uv`-style Python setup. The rebuild should choose one primary path. `uv` should be the default.
- I did not find an automated test suite in the repository. The rebuild should start with tests around contracts, schema loading, flow execution, and key API routes.
- Session storage is file-system based under `src/server/sessions`. This is fine for local development and research pilots, but the rebuild should define a storage abstraction so local disk is only one backend.
- The React app assumes relative `/api/*` paths and local storage for selected avatar and auth token. That is acceptable for a first pass, but the rebuild should formalize client configuration and state boundaries.
- Advanced flows and activity schemas are powerful but rely on raw JSON shape. The rebuild should add schema validation and compatibility tests for activity packs.
- The flow-builder is useful but isolated from the main app. It should remain a separate tool or be folded into an internal admin surface, but either way it needs explicit ownership.

## 8. Proposed Target Architecture

The first rebuild should remain a modular monolith, not a microservice fleet.

### 8.1 Top-level services

1. `web-client`
2. `api-server`
3. `realtime-runtime`
4. `analysis-worker`
5. `flow-builder`

Recommended implementation approach:

- keep `api-server`, `realtime-runtime`, and `analysis-worker` in one Python repo/package during phase 1
- isolate them by module boundaries and explicit interfaces
- keep `web-client` as a separate frontend package
- keep `flow-builder` as either a separate package or an internal admin app, but with shared schemas

### 8.2 Suggested package layout

```text
riverst/
  apps/
    web-client/
    api-server/
    flow-builder/
  packages/
    activity-contracts/
    session-domain/
    realtime-runtime/
    analysis/
    auth/
    storage/
  docker/
  docs/
```

### 8.3 Architectural boundaries

#### Activity contracts

- activity metadata
- session configuration schema
- resource schema
- flow schema

#### Session domain

- session ID generation
- session lifecycle
- artifact indexing
- completion state

#### Realtime runtime

- transport bootstrap
- model provider factories
- transcript and metrics processors
- flow integration

#### Analysis

- audio feature extraction
- post-session summaries
- optional async worker execution

#### Storage

- local filesystem adapter
- future database or object-store adapter

## 9. Data Model Requirements

### 9.1 Session

Required fields:

- `session_id`
- `user_id`
- `activity_name`
- `created_at`
- `config`
- `status`
- `device_fingerprints`
- `completion_code`

### 9.2 Session artifacts

Required artifact classes:

- turn-level audio files
- transcript events
- per-turn JSON analysis
- metrics log
- metrics summary
- optional video output

### 9.3 Activity definition

Required fields:

- activity name and description
- route intent or activity type
- JSON schema for settings
- optional resource catalog binding
- optional advanced flow binding
- runtime capability flags

### 9.4 Avatar definition

Required fields:

- ID
- model URL
- gender or voice-selection metadata
- optional voice provider IDs
- optional thumbnail/preview metadata

## 10. API Parity Requirements

The rebuild must provide equivalents for the current major endpoints, even if the exact paths evolve.

Required API domains:

- auth status and login
- current user identity
- activity catalog and session schemas
- avatars
- resources and resource indices
- audiobook catalog and chapter detail
- session creation
- session runtime bootstrap
- session listing and session detail
- session completion and completion-code lookup

The rebuild should add:

- versioned API routes
- OpenAPI-backed contracts
- integration tests for every public endpoint

## 11. Frontend Requirements

### 11.1 Required routes

- login
- home/activity catalog
- avatar selection
- avatar creation
- activity settings
- avatar interaction runtime
- audiobook browser
- audiobook player
- session list
- session detail
- error fallback

### 11.2 Required client capabilities

- auth bootstrap based on server mode
- schema-driven forms
- session sharing by URL and QR
- resilient runtime page that can reload from stored session config
- transcript display toggles
- media playback for session review and audiobook mode
- mobile-compatible session join experience

## 12. Test Strategy

The rebuild should be test-first.

### 12.1 Python

Use:

- `uv` for environment and dependency management
- `pytest` for unit and integration tests
- Docker for reproducible local and CI runs when native dependencies are involved

Required test layers:

- unit tests for activity schema loading and validation
- unit tests for flow handlers and transition logic
- unit tests for session storage adapters
- unit tests for memory loading behavior
- integration tests for auth, session, activity, and audiobook endpoints
- integration tests for session artifact generation using mocked providers

### 12.2 Frontend

Use:

- `vitest` for unit tests
- `@testing-library/react` for component and page behavior
- Playwright for end-to-end flows

Required test flows:

- auth bootstrap with Google auth disabled
- activity settings load and session creation
- direct join to avatar interaction page
- audiobook link generation and playback options
- session list and detail rendering

### 12.3 Contract tests

Required:

- activity schema compatibility tests
- flow JSON validation tests
- avatar metadata schema tests
- sample resource validation tests

## 13. Delivery Plan

### Phase 0: Foundation

- [ ] Create monorepo package layout
- [ ] Standardize Python on `uv`
- [ ] Add Docker Compose for local full-stack development
- [ ] Add CI for lint, type-check, and tests
- [ ] Define shared JSON schemas and typed models

### Phase 1: Core API and storage

- [ ] Implement auth mode detection and JWT auth
- [ ] Implement session creation and retrieval
- [ ] Implement avatar, activity, and resource catalog endpoints
- [ ] Implement local filesystem storage adapter
- [ ] Add integration tests for all core endpoints

### Phase 2: Frontend parity

- [ ] Rebuild homepage and activity navigation
- [ ] Rebuild avatar selection and avatar creation flows
- [ ] Rebuild schema-driven settings form
- [ ] Rebuild session sharing flow
- [ ] Rebuild audiobook browser and player
- [ ] Rebuild session list and session detail views

### Phase 3: Realtime runtime parity

- [ ] Implement WebRTC offer bootstrap
- [ ] Implement runtime pipeline assembly
- [ ] Implement transcript, metrics, and artifact capture
- [ ] Implement animation and end-conversation tools
- [ ] Add provider adapters and mocked integration tests

### Phase 4: Advanced flows

- [ ] Implement validated flow loading
- [ ] Implement staged flow progression and variable retrieval
- [ ] Port existing tutoring activities
- [ ] Add flow execution tests with sample content

### Phase 5: Analysis and operator polish

- [ ] Implement metrics summary generation
- [ ] Implement optional audio analysis worker
- [ ] Improve session review UX
- [ ] Add export or archive support for session artifacts

### Phase 6: Flow authoring

- [ ] Rebuild or refactor the flow-builder
- [ ] Add validation and preview of generated flow files
- [ ] Align generated artifacts with runtime schemas

## 14. Acceptance Criteria

The rebuild is acceptable when:

- an operator can sign in or use bypass auth in development
- an operator can choose an activity, configure it, and create a shareable session
- a participant can join a live avatar session from a direct link
- the session records transcript, audio, and metrics artifacts
- an operator can review the session afterward
- audiobook workflows function with audio/text/subtitle combinations
- at least one advanced tutoring flow runs correctly against validated content
- the full stack runs locally through a documented `uv` and Docker workflow
- automated tests cover the critical product paths

## 15. Open Questions

- Should the rebuilt system continue to use local files as the canonical session store in phase 1, or should a database be introduced immediately for metadata while artifacts remain on disk?
- Should the flow-builder remain a standalone tool or move into an authenticated admin surface?
- Which provider matrix is required for phase 1 parity: OpenAI only, or OpenAI plus local Ollama and Kokoro?
- Does the rebuilt system need backwards compatibility for existing session directories and activity JSON files, or is a migration step acceptable?
- Should audiobook assets remain static files in the repo, or move to external object storage?

## 16. Recommended Next Steps

1. Approve this spec as the phase-0 design baseline.
2. Split phase 0 and phase 1 into tracked issues.
3. Create an implementation board with epics for client, API, runtime, flows, and analysis.
4. Start with schema contracts and session storage tests before rebuilding UI surfaces.
