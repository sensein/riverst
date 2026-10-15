# Feature Specification: Story Context Lookup for Vocab Tutoring

**Feature Branch**: `008-story-context-lookup`
**Created**: 2026-08-21
**Status**: Draft
**Input**: User description: "implement story context lookup tool for vocab-tutoring activity so the avatar retrieves targeted story context on demand instead of injecting full content"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Avatar fetches only what it needs during a lesson (Priority: P1)

A child is in the middle of a vocab tutoring session. When the child asks about a word from the story, the avatar retrieves only that word's sentence and context from the book — not the entire chapter — and uses it to answer naturally. The avatar does not repeat content already covered in the conversation.

**Why this priority**: This is the core behavior change: moving from bulk content injection to targeted retrieval. Every other story improves upon this baseline.

**Independent Test**: Can be fully tested by running a vocab tutoring session and observing that the avatar's responses reference specific word-level content it retrieved on demand, while the conversation transcript does not contain the full chapter text.

**Acceptance Scenarios**:

1. **Given** a vocab tutoring session is active and the current chapter is set, **When** the child asks what a word means, **Then** the avatar calls the lookup tool with the word and chapter and uses the returned definition context in its response.
2. **Given** the avatar is introducing a new vocabulary word, **When** it needs the word's in-story sentence, **Then** it retrieves only that word's data rather than the whole chapter's vocab list.
3. **Given** the lookup tool is called for a word not in the current chapter, **When** the result is an error, **Then** the avatar gracefully acknowledges it does not have that information rather than failing silently.

---

### User Story 2 - Avatar recalls the chapter plot to answer a comprehension question (Priority: P2)

The child asks "what happened to Peter in this part?" during the session. The avatar looks up the chapter summary for the current chapter and uses it to give a brief, story-accurate answer without guessing or making up plot details.

**Why this priority**: Chapter summaries are the next most common retrieval need after individual words; this validates that the tool supports multiple context types.

**Independent Test**: Can be fully tested by asking a comprehension question mid-session and confirming the avatar's answer matches the chapter summary text, not a hallucinated plot description.

**Acceptance Scenarios**:

1. **Given** a chapter index is known for the session, **When** the avatar needs chapter context to answer a plot question, **Then** it retrieves the chapter summary and bases its response on that text.
2. **Given** the child asks something that requires broader story context, **When** no specific chapter is more relevant, **Then** the avatar can retrieve the book-level summary and use it to frame its answer.

---

### User Story 3 - Avatar discovers available words when starting a new vocab teaching phase (Priority: P3)

When the avatar begins the vocabulary teaching phase for a chapter, it looks up the list of available words for that chapter so it can select an appropriate one to teach, rather than having the full word list pre-loaded into its context at session start.

**Why this priority**: This completes the shift from bulk pre-loading to on-demand retrieval for the session opening flow.

**Independent Test**: Can be tested by starting a session at the vocab stage and confirming the avatar's first word selection follows a tool call for the word list, not a pre-injected content block.

**Acceptance Scenarios**:

1. **Given** the session is entering the vocab teaching stage, **When** the avatar needs to select a word to teach, **Then** it calls the lookup tool without a specific word to get the list of available words for the chapter.
2. **Given** a grade level is configured for the session, **When** the word list is returned, **Then** the avatar selects a word appropriate to the configured grade level.

---

### Edge Cases

- What happens when no chapter index is set and the avatar calls for a chapter summary? The tool returns an error message prompting the avatar to ask the child which chapter they are on before proceeding.
- What happens when the lookup tool is called for a chapter index out of range? The tool returns a clear error with the valid range so the avatar can self-correct.
- What happens when a word is requested but does not exist in the chapter's vocab list? The tool returns an error listing the available words so the avatar can choose a valid one.
- What happens if the story resource file was not loaded at session start? The tool returns an error and the avatar falls back to asking the child directly about the story.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a story context lookup capability that the avatar can call during a conversation turn to retrieve a specific piece of story information.
- **FR-002**: The lookup capability MUST support at least three retrieval types: book-level summary, chapter summary by chapter number, and vocabulary word details by chapter number and word.
- **FR-003**: When called with a retrieval type of "book summary", the system MUST return the overall plot summary of the book loaded for the session.
- **FR-004**: When called with a retrieval type of "chapter summary" and a chapter number, the system MUST return the narrative summary for that chapter.
- **FR-005**: When called with a retrieval type of "vocabulary word", a chapter number, and a word, the system MUST return the in-story sentence and contextual description for that word.
- **FR-006**: When called with a retrieval type of "vocabulary word" and a chapter number but no specific word, the system MUST return the list of available vocabulary words for that chapter.
- **FR-007**: The system MUST return a structured error response (not a runtime failure) when a request cannot be fulfilled — for example, when the chapter index is missing, out of range, or the word is not found.
- **FR-008**: The lookup capability MUST be available to the avatar throughout all stages of the vocab tutoring flow (warm-up, vocab, review, closing).
- **FR-009**: The existing bulk content injection into the conversation context at node entry MUST be removed from the vocab tutoring flow so that story content is only surfaced through explicit lookup calls.
- **FR-010**: The story content data (loaded from the book resource file) MUST remain accessible in session state so the lookup capability can query it without re-reading files during the conversation.

### Key Entities

- **Book Resource**: The JSON file for a selected book containing the reading context (book summary, chapter summaries) and vocabulary data (per-chapter word lists with sentences and context descriptions). Loaded once at session start.
- **Lookup Request**: A request specifying a retrieval type, an optional chapter index, and an optional word. Issued by the avatar during conversation.
- **Lookup Response**: A structured result containing either the requested data or a descriptive error message the avatar can interpret and act on.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The full story content (chapter text, complete vocab lists) is absent from the conversation context window during normal session turns — verified by inspecting what is sent to the language model per turn.
- **SC-002**: The avatar successfully retrieves and uses targeted story content in at least 95% of turns where story context is needed, with no increase in incorrect or hallucinated story details compared to the prior bulk-injection approach.
- **SC-003**: The average amount of story content sent to the language model per conversation turn decreases by at least 70% compared to the bulk-injection baseline.
- **SC-004**: A complete vocab tutoring session (warm-up → vocab → review → closing) runs without errors attributable to missing story context under the new retrieval approach.
- **SC-005**: When a lookup request cannot be fulfilled (e.g., missing chapter index, unknown word), the avatar recovers gracefully within the same conversation turn without ending the session or producing a visible error to the child.

## Assumptions

- The story book resource file is fully loaded into session state before the first conversation turn begins; the lookup tool does not need to perform any file I/O during the session.
- The chapter index for the session is either provided by the user at session configuration time or asked of the child early in the session (the existing index-resolution flow handles this).
- Grade level filtering for vocabulary words is determined by a session-level setting already present in the user state; the lookup tool returns all words for the chapter and the avatar applies grade-level selection.
- The vocab tutoring flow is the only activity being changed in this feature; other activities (audiobook, basic interaction, etc.) are out of scope.
- The lookup tool is available as a callable function within the flow's node function list — it follows the same registration pattern as existing flow functions (`get_activity_handler`, `general_handler`).
- No external search index or embedding model is required; retrieval is key-based over the structured JSON already in session state.
