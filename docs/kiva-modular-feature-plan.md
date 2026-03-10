# KIVA Modular Feature Implementation Plan

Status: Draft

Date: 2026-03-07

Branch: `codex/rebuild-spec`

## 1. Goal

This document analyzes the requested KIVA features and turns them into a modular implementation plan that can be reused across flows.

Constraint:

- audiobook training is only one KIVA flow
- shared capabilities must live in reusable platform modules
- flow-specific behavior should be configured through activity schemas, resources, and flow definitions rather than embedded in one-off runtime code

## 2. Requested Feature Themes

The requested items cluster into six workstreams:

1. Reading-state grounding
2. Pedagogical control and response policy
3. Engagement detection and motivational support
4. Runtime latency and synchronization
5. Analytics, mastery, and cross-session measurement
6. Privacy, validation, and reporting

## 3. Existing System Baseline

Relevant capabilities already present:

- KIVA uses advanced flows with `reading_context` and user state in [`src/server/activities/vocab-tutoring/flow_config.json`](/Users/satra/software/sensein/riverst/src/server/activities/vocab-tutoring/flow_config.json)
- indexable reading content already exists in activity resources and `get_reading_context` flow handling in [`src/server/bot/flows/handlers.py`](/Users/satra/software/sensein/riverst/src/server/bot/flows/handlers.py)
- audiobook playback already exposes word-level timing in [`src/client/react/src/pages/AudioPlayerPage.tsx`](/Users/satra/software/sensein/riverst/src/client/react/src/pages/AudioPlayerPage.tsx)
- session artifacts already include transcripts, audio, and metrics via [`src/server/bot/core/event_manager.py`](/Users/satra/software/sensein/riverst/src/server/bot/core/event_manager.py) and [`src/server/bot/monitoring/metrics_logger.py`](/Users/satra/software/sensein/riverst/src/server/bot/monitoring/metrics_logger.py)
- subtitle rendering is already present in the runtime UI in [`src/client/react/src/components/avatarInteraction/AvatarInteractionContent.tsx`](/Users/satra/software/sensein/riverst/src/client/react/src/components/avatarInteraction/AvatarInteractionContent.tsx)

Gaps relative to the request:

- no unified reading-position state model shared across audiobook playback and dialogue flow execution
- no reusable policy engine for single-question prompts, wait time, minimum expectations, or contingent follow-ups
- no explicit disengagement detector
- current metrics are infrastructure-focused, not pedagogy-focused
- no defined cross-session mastery or retention layer
- no validation protocol against human-coded samples

## 4. Design Principles

### 4.1 Shared capability first

Every new feature should be implemented as:

- a reusable state contract
- a reusable runtime processor or service
- a reusable analytics event schema
- optional per-flow configuration

Audiobook tutoring should consume these modules, not define them.

### 4.2 Flow configuration over prompt sprawl

Behavioral rules such as:

- minimum vocabulary targets
- minimum student response length
- single-question constraints
- disengagement handling

should be encoded as structured policy in activity config and flow metadata, then enforced by shared runtime components.

### 4.3 Event-first analytics

Pedagogical and engagement metrics should be derived from normalized events instead of fragile transcript-only post-processing.

### 4.4 Testable contracts

Each subsystem should be introduced with:

- schema validation
- unit tests
- replay tests using captured sessions or synthetic traces

## 5. Proposed Modular Architecture

## 5.1 Shared modules

### Module A: Reading State Service

Purpose:

- maintain canonical reading position at word, sentence, paragraph, and section level
- expose current location to prompts, dialogue flow, analytics, and UI

Responsibilities:

- accept reading progression events from audiobook playback and dialogue flow
- persist current location in session state
- resolve current text span and neighboring context
- detect pauses, rereads, and regressions

Consumers:

- audiobook flow
- vocabulary tutoring flow
- future comprehension flows
- analytics layer

### Module B: Instruction Policy Engine

Purpose:

- enforce teaching and response expectations consistently across KIVA flows

Responsibilities:

- enforce single-question prompts
- enforce minimum instructional targets per session
- enforce minimum response expectations
- decide when modeling, sentence starters, or adaptive prompts are needed
- maintain stable instructional routines across sessions
- ensure follow-up prompts are contingent on prior student response

Consumers:

- all KIVA instructional flows

### Module C: Engagement Monitor

Purpose:

- detect disengagement and guide short motivational or pause behavior

Responsibilities:

- classify silence, refusal, minimal response, repeated non-response, and participation drop-off
- emit engagement events
- trigger affect acknowledgment and brief scaffolding
- offer pause or stop options when thresholds are met

Consumers:

- KIVA tutoring flows
- future support-oriented flows

### Module D: Runtime Synchronization and Latency Monitor

Purpose:

- reduce perceived and measured lag across ASR, subtitles, avatar response, and animation

Responsibilities:

- instrument timestamps across speech input, transcription, subtitle render, LLM response, TTS start, TTS end, and avatar animation start
- expose latency metrics per turn and per session
- align subtitles and animation with audio playback

Consumers:

- all real-time avatar flows
- performance dashboards

### Module E: Pedagogical Analytics Layer

Purpose:

- convert session events into interpretable educational and product metrics

Responsibilities:

- track pedagogical behaviors such as question type, scaffolding, wait time, motivational prompts, and contingent follow-ups
- track student engagement signals such as response length, response latency, participation trends, and silence
- compute learning metrics such as exposures per word, instructional effort, time to mastery, and retention
- support cross-session growth and mastery trajectories

Consumers:

- session review UI
- research exports
- product iteration workflows

### Module F: Privacy and Evaluation Layer

Purpose:

- govern storage, documentation, de-identification, and validation quality

Responsibilities:

- document data usage and retention
- support privacy-preserving storage decisions
- maintain validation datasets and agreement checks against human-coded samples
- track confidence and quality of automated measures

Consumers:

- engineering
- research
- compliance review

## 5.2 Flow-specific adapters

### Audiobook flow adapter

Responsibilities:

- generate word-, sentence-, and paragraph-level reading events from the audiobook player
- update shared reading state
- consume policy engine outputs for grounding prompts in current text

### Vocabulary tutoring flow adapter

Responsibilities:

- request current reading state from the shared service
- ground vocabulary and comprehension prompts in current text position
- log exposures, mastery attempts, and scaffolding events

### Future KIVA flow adapters

Examples:

- comprehension check flow
- retell flow
- second-language tutoring flow

These should reuse the same shared services and only differ in policy configuration and content schemas.

## 6. Feature Analysis and Implementation Approach

## 6.1 Reading-state grounding

Requested features covered:

- automatic reading position at sentence, paragraph, and word level
- persistent reading state shared across dialogue, prompts, and feedback
- current-text grounding for questions and follow-ups
- logging of progression, pauses, and rereads

Implementation approach:

1. Extend reading content schema to include stable IDs for:
   - word
   - sentence
   - paragraph
   - chapter or section
2. Introduce a session-scoped `reading_state` object in flow and session state.
3. Emit normalized reading events:
   - `word_entered`
   - `sentence_completed`
   - `paragraph_completed`
   - `pause_detected`
   - `reread_detected`
   - `position_set`
4. Build a `ReadingStateService` that derives current position and recent history.
5. Expose a shared handler to flows such as `get_reading_position` and `get_current_text_window`.

Key design choice:

- do not infer progress only from dialogue transcripts
- prefer direct player/runtime events when available
- fall back to transcript inference only as a secondary heuristic

## 6.2 Pedagogical control and instructional consistency

Requested features covered:

- adaptive wait time after child responses
- single-question prompts
- contingent follow-up prompts
- minimum instructional expectations per session
- minimum response expectations per student response
- adaptive support such as modeling or sentence starters
- consistent instructional routines across sessions

Implementation approach:

1. Define a reusable `instruction_policy` schema in activity configs.
2. Add policy fields such as:
   - `single_question_only`
   - `min_target_words_per_session`
   - `min_student_words_per_response`
   - `adaptive_wait_time_ms`
   - `allowed_scaffolds`
   - `routine_template`
3. Introduce a `PolicyEngine` processor between transcript interpretation and prompt generation.
4. Have the flow manager consult policy outputs before advancing nodes or issuing prompts.
5. Log policy interventions as explicit analytics events.

Key design choice:

- enforce constraints structurally where possible instead of relying on large system prompts alone

## 6.3 Engagement and motivational support

Requested features covered:

- disengagement detection
- affect acknowledgment
- motivational scaffolding
- graceful pause or stopping option

Implementation approach:

1. Define disengagement signals:
   - refusal phrases
   - silence thresholds
   - repeated minimal responses
   - declining participation trend
2. Build an `EngagementMonitor` that consumes transcript and latency events.
3. Produce engagement states such as:
   - `engaged`
   - `hesitant`
   - `disengaged`
   - `paused`
4. Map each state to configurable recovery behaviors.
5. Require flows to explicitly support `pause` and `stop` transitions.

Key design choice:

- the engagement monitor should recommend actions
- the flow adapter decides whether and how to surface those actions based on activity policy

## 6.4 Runtime synchronization and latency

Requested features covered:

- lower latency from child speech to transcription, subtitle render, and avatar response
- synchronize audio, subtitles, and avatar animation
- monitor latency as a core performance metric

Implementation approach:

1. Add per-turn timestamp instrumentation to runtime processors.
2. Define a latency event model:
   - speech end
   - ASR final
   - subtitle rendered
   - LLM first token
   - TTS start
   - audio playback start
   - avatar animation start
3. Compute turn-level latency breakdowns.
4. Refactor subtitle and avatar animation consumers to use shared timing cues where available.
5. Surface latency summary in session metrics.

Key design choice:

- latency must be tracked both as an engineering metric and as a pedagogical quality metric because long lag degrades instructional flow

## 6.5 Analytics and learning measurement

Requested features covered:

- session-level interaction data with timestamps and reading position
- pedagogical behavior tracking
- student engagement tracking
- learning and mastery metrics
- cross-session growth and retention
- interpretable session-level summaries
- analytics that inform instructional improvement

Implementation approach:

1. Define a normalized `session_event` schema covering:
   - reading events
   - dialogue events
   - policy interventions
   - engagement events
   - teaching actions
   - mastery updates
2. Store raw events and derived metrics separately.
3. Compute derived outputs:
   - exposures per word
   - number of scaffold attempts
   - question-type distribution
   - average wait time
   - response-length distribution
   - participation trend
   - time to mastery
   - retained/not retained across sessions
4. Generate session summary narratives from these structured metrics.
5. Add longitudinal summaries at the learner level.

Key design choice:

- summaries should cite structured signals rather than free-form LLM impression alone

## 6.6 Validation, privacy, and documentation

Requested features covered:

- validate automated metrics against human-coded samples
- privacy-preserving data storage
- clear documentation of data use

Implementation approach:

1. Define a human-coding rubric for:
   - question type
   - scaffolding
   - affect support
   - disengagement
   - mastery event
2. Build a gold-sample evaluation dataset.
3. Compare automated output to coded samples on a scheduled basis.
4. Document:
   - data collected
   - retention policy
   - de-identification strategy
   - intended analytic uses
5. Store PII-sensitive and research-sensitive artifacts behind clear boundaries.

## 7. Data Contract Additions

## 7.1 Session state additions

Add to shared session/flow state:

```json
{
  "reading_state": {
    "resource_id": "the_tale_of_peter_rabbit",
    "chapter_id": 3,
    "paragraph_id": "p12",
    "sentence_id": "s48",
    "word_id": "w391",
    "position_updated_at": "2026-03-07T14:00:00Z",
    "recent_positions": [],
    "pause_count": 0,
    "reread_count": 0
  },
  "instruction_state": {
    "target_words_taught": [],
    "instructional_steps_completed": [],
    "single_question_compliance": true,
    "wait_time_events": []
  },
  "engagement_state": {
    "current_status": "engaged",
    "minimal_response_streak": 0,
    "silence_events": 0,
    "refusal_events": 0
  },
  "mastery_state": {
    "word_exposures": {},
    "word_mastery_status": {},
    "retention_history": []
  }
}
```

## 7.2 Event schema additions

Add normalized events such as:

- `reading_position_updated`
- `reading_pause_detected`
- `reading_reread_detected`
- `question_prompted`
- `wait_time_applied`
- `student_response_evaluated`
- `scaffold_prompted`
- `motivation_prompted`
- `pause_offered`
- `latency_measured`
- `word_exposure_recorded`
- `mastery_status_changed`

## 8. Implementation Phases

## Phase 0: Contracts and instrumentation design

Deliverables:

- shared schemas for reading state, instruction policy, engagement events, and session events
- test fixtures and synthetic traces
- design review with KIVA stakeholders

TDD:

- schema validation tests
- event serialization tests

## Phase 1: Shared Reading State Service

Deliverables:

- reading state model and persistence
- audiobook event emitter
- flow handlers for current reading location
- pause and reread detection

TDD:

- reading position update tests
- pause/reread detection tests
- integration tests from audiobook playback events into flow-visible state

## Phase 2: Instruction Policy Engine

Deliverables:

- configurable instruction policy schema
- enforcement of single-question prompts
- adaptive wait-time controller
- minimum instructional and response expectation tracking
- contingent follow-up enforcement hooks

TDD:

- policy rule evaluation tests
- turn replay tests for contingent follow-up behavior
- flow tests for minimum target coverage

## Phase 3: Engagement Monitor

Deliverables:

- disengagement classifier
- motivational scaffold templates
- pause/stop flow hooks

TDD:

- silence and minimal-response detection tests
- refusal classification tests
- flow tests for pause/stop transitions

## Phase 4: Runtime latency and synchronization

Deliverables:

- end-to-end timestamp instrumentation
- subtitle/audio/avatar sync improvements
- latency dashboards in metrics summary

TDD:

- processor timestamp propagation tests
- subtitle timing tests
- latency budget regression tests

## Phase 5: Pedagogical analytics and mastery

Deliverables:

- normalized event log
- derived pedagogy and engagement metrics
- mastery and cross-session growth tracking
- session summary generator

TDD:

- metric derivation tests
- longitudinal aggregation tests
- summary generation tests on fixed event fixtures

## Phase 6: Validation, privacy, and reporting

Deliverables:

- human-coded validation dataset
- agreement evaluation scripts
- privacy and data-use documentation
- instructional analytics views

TDD:

- evaluation pipeline tests
- privacy redaction tests
- report-generation tests

## 9. Recommended GitHub Work Breakdown

The work should be tracked as one project with nine issues:

1. KIVA shared contracts and event schemas
2. Shared reading state service and audiobook instrumentation
3. Instruction policy engine for KIVA flows
4. Engagement monitor and pause/stop handling
5. Runtime latency instrumentation and synchronization
6. Pedagogical analytics event pipeline
7. Mastery, growth, and cross-session tracking
8. Validation against human-coded samples
9. Privacy, data documentation, and analytics surfacing

Rationale:

- this is small enough for a single board
- the issues are modular and map to reusable system capabilities
- audiobook-specific work is contained inside issue 2 and does not dominate the architecture

## 10. Risks

- prompt-only enforcement will drift; policy must be implemented structurally
- word-level reading position may vary across audiobook assets; content contracts must be normalized first
- latency fixes can regress if instrumentation is added without performance budgets
- cross-session growth tracking is only useful if learner identity and session linkage are defined cleanly
- privacy work cannot be deferred until after analytics collection is already in place

## 11. Acceptance Criteria

This initiative is complete when:

- KIVA flows can access canonical reading position without ad hoc inference
- audiobook and tutoring flows share the same reading-state service
- single-question and contingent follow-up behavior is enforced by shared policy
- disengagement detection triggers configurable motivational or pause behavior
- session logs capture reading, pedagogy, engagement, mastery, and latency events
- session summaries are derived from interpretable structured metrics
- cross-session retention metrics are available for supported learners
- automated metrics have documented validation against human-coded samples
- privacy and data-use documentation is committed in the repo

## 12. Recommended Next Step

Create the board and issues immediately from the work breakdown in section 9, then implement phase 0 first with schema and replay-test scaffolding before changing any KIVA prompt logic.
