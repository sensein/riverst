# Feature Specification: Avatar Edge Case Fallback Handling

**Feature Branch**: `007-avatar-fallback-handling`
**Created**: 2026-08-09
**Status**: Clarified
**Input**: User description: "create a new branch for an edge case fallback process, which the avatar can refer to if the student goes off the pipeline. importantly, this should include ways to bring back the child to the task if they veer too far away from the conversation, methods to address a child refusing to participate in a task or answer a question, keeping responses rooted to english and not reverting to any other language even if the student is talking in another language, make this flexible so we can keep adding to it as situations arise."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Student veers off-topic and avatar redirects (Priority: P1)

A child midway through a vocabulary tutoring session starts talking about something unrelated to the lesson (e.g., a video game, a story about their pet, or a random tangent). The avatar gently acknowledges the comment, then steers the conversation back to the activity without making the child feel dismissed or punished.

**Why this priority**: Off-topic digressions are the most common disruption in child-facing sessions. Without a reliable redirect strategy, the pipeline stalls or the avatar loses its instructional thread. This is the minimum viable fallback to keep sessions functional.

**Independent Test**: In a live session, say something completely off-topic mid-lesson (e.g., "Did you know my dog ate a sock?"). Confirm the avatar acknowledges the comment briefly, then returns to the exact task step it was on before the digression, within one to two turns.

**Acceptance Scenarios**:

1. **Given** the avatar is mid-lesson on a specific task step, **When** the student says something unrelated, **Then** the avatar briefly acknowledges it and returns to the task within one turn.
2. **Given** the student has gone off-topic two or more times in a row, **When** the avatar redirects, **Then** it uses a warmer or more explicit redirect ("Let's save that for after our lesson — right now I need your help with…") rather than a minimal one.
3. **Given** the student's off-topic comment is emotionally charged (e.g., "I'm really upset about something"), **When** the avatar redirects, **Then** it shows brief empathy before returning to the lesson, rather than ignoring the emotion.

---

### User Story 2 - Student refuses to participate, doesn't know the answer, or goes silent (Priority: P2)

A child says "I don't know," "I don't want to do this," "This is boring," or simply goes silent without responding. The avatar gives the student adequate time to think before interpreting silence as non-participation, then tries one or two encouragement strategies before simplifying the question, offering a hint, or moving on — without pressuring or repeating the same prompt in a loop.

**Why this priority**: Refusal and disengagement are the second most common disruption and are the hardest to recover from if the avatar keeps repeating the same question. Failure here leads to a dead session with no educational value.

**Independent Test**: When the avatar asks a question, respond with "I don't know" or stay completely silent. Confirm the avatar gives a gentle wait-prompt before treating silence as refusal, does not repeat the exact same question verbatim more than once, offers a hint or simpler version instead, and eventually progresses the lesson if the student remains unresponsive.

**Acceptance Scenarios**:

1. **Given** the student says "I don't know" to a question, **When** the avatar responds, **Then** it provides a hint or simplifies the question rather than repeating it verbatim.
2. **Given** the student explicitly refuses ("I don't want to," "This is too hard"), **When** the avatar responds, **Then** it acknowledges the feeling, tries a different approach (e.g., making it easier, framing it as a game), and does not escalate or repeat the demand.
3. **Given** the student goes silent after being asked a question, **When** the avatar detects an elongated pause, **Then** it gives one warm, non-pressuring prompt ("Take your time — I'm here whenever you're ready") and waits again before treating the silence as a refusal.
4. **Given** the student remains silent after the wait prompt, **When** the avatar responds, **Then** it treats the silence as a soft refusal and moves to a hint or simpler version of the question rather than repeating the full question.
5. **Given** the student refuses multiple consecutive tasks, **When** the avatar responds, **Then** it acknowledges the situation empathetically and wraps up the session gracefully rather than continuing to press.

---

### User Story 3 - Student speaks in a non-English language (Priority: P3)

A child responds in Spanish, French, or another language. The avatar continues responding exclusively in English, does not mirror or adopt the other language, but may briefly acknowledge that it heard them — then continues in English.

**Why this priority**: The platform is an English-language educational tool. Slipping into another language undermines the activity's goals and can cause the LLM to respond inconsistently or lose track of the lesson. This is a hard constraint.

**Independent Test**: Respond to the avatar in Spanish or French. Confirm the avatar's reply is entirely in English, acknowledges the student without code-switching, and continues the lesson in English.

**Acceptance Scenarios**:

1. **Given** the student responds in a non-English language, **When** the avatar replies, **Then** the response is entirely in English — no words, phrases, or sentences in any other language.
2. **Given** the student continues using a non-English language across multiple turns, **When** the avatar responds, **Then** it continues in English and may gently note that it will respond in English, without scolding or making the student feel wrong.
3. **Given** the student mixes English with another language, **When** the avatar replies, **Then** it responds only to the English content and continues in English, without completing or repeating the non-English portion.

---

### User Story 4 - New fallback scenarios can be added without restructuring existing activities (Priority: P4)

A researcher or developer wants to add a new fallback scenario (e.g., "student is crying," "student asks an inappropriate question," "student says something harmful") to the system. They can add it to a shared fallback definition without needing to edit every activity's flow config individually.

**Why this priority**: The platform will encounter edge cases that can't all be anticipated now. A single shared definition that all activities pull from means new scenarios can be deployed once rather than re-applied across every activity.

**Independent Test**: Add a new fallback rule to the shared config. Run two different activities and confirm the new behavior is present in both, without having edited either activity's `flow_config.json`.

**Acceptance Scenarios**:

1. **Given** a new fallback scenario is added to the shared fallback config, **When** any activity session runs, **Then** the avatar exhibits the new behavior without any changes to individual activity files.
2. **Given** the shared fallback config is edited, **When** a session is started, **Then** the updated fallback behavior takes effect immediately without requiring a server restart or cache clear beyond the standard session initialization.

---

### Edge Cases

- What happens when the student's off-topic comment reveals a safety concern (e.g., mentions they are scared at home)? Sessions are monitored by an adult supervisor who can intervene directly; the avatar does not need to escalate programmatically, but its response should not dismiss or override a child's distress signal.
- What happens when the student's refusal is combined with an off-topic digression (e.g., "I don't want to do this, let's talk about dinosaurs instead")? Both fallbacks may fire; the redirect-to-task handler should take priority over the refusal handler.
- What happens when the session's flow node expects a specific tool call (like `check_vocab_progress`) and the student's off-topic response delays it? The fallback must not call or trigger any state-transition function until the student is back on task.
- What happens when the student speaks a mix of English and a non-English language (e.g., Spanglish)? The avatar should respond only to the English content and continue in English.
- What happens if the student's message is in a language that uses a non-Latin script (e.g., Arabic, Chinese)? The English-only rule still applies — the avatar responds in English.
- What happens when the student is a bilingual child who naturally code-switches? The avatar should remain in English but not make the child feel corrected or singled out.
- How long should the avatar wait before treating silence as a refusal? Long enough for the student to think and respond comfortably — the instruction should convey "give adequate think time" rather than specify a precise number of seconds, since the pipeline's VAD determines the actual pause detection window.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The avatar MUST detect when a student's response is significantly off-topic relative to the current task node and respond with a redirect within the same conversational turn.
- **FR-002**: The avatar MUST NOT repeat the same question or prompt verbatim after a student says "I don't know" or explicitly refuses; it MUST offer a hint, a simpler version, or move forward instead. (Covers verbal refusal and "I don't know" — for silence, see FR-002a.)
- **FR-002a**: When a student goes silent after being asked a question, the avatar MUST issue one warm, non-pressuring wait prompt ("Take your time — I'm here whenever you're ready") and wait again before treating the silence as a soft refusal. It MUST give adequate time for thinking before escalating to a hint or simpler version.
- **FR-003**: The avatar MUST acknowledge a student refusal or disengagement with empathy before attempting a different strategy; it MUST NOT simply restate the demand.
- **FR-004**: The avatar MUST produce responses exclusively in English regardless of the language the student uses, including when the student's input is entirely in a non-English language.
- **FR-005**: The avatar MUST NOT call or trigger any flow-state transition function (e.g., `check_vocab_progress`) while the student is in an off-topic or refusal state; transitions only occur once the student is back on task. **Exception**: the avatar MAY call the session-closing transition (e.g., to the `closing` or `end` node) when FR-008 applies — sustained consecutive refusals warranting a graceful session close. This is the only permitted transition from a fallback state.
- **FR-006**: The shared fallback definition MUST be structured so that a new fallback scenario can be added in one place and automatically apply to all activities that use the shared config.
- **FR-007**: Fallback behavior MUST NOT override or conflict with any activity-specific task instructions; it operates as a layer that activates when the expected task flow breaks down.
- **FR-008**: The avatar MUST handle repeated refusals or sustained unresponsiveness by gracefully moving toward session close rather than looping indefinitely on the same task step.

### Key Entities

- **Fallback Config**: A shared, structured definition of edge case scenarios and the behavioral instructions the avatar should follow for each. Applies globally across activities.
- **Off-Topic Redirect Strategy**: A reusable set of avatar behaviors (acknowledge, empathize if needed, return to task) applied when a student digresses significantly from the current task.
- **Refusal/Disengagement Handler**: A reusable set of avatar behaviors (empathize, simplify, hint, advance) applied when a student refuses to answer or goes silent.
- **Language Guard**: An always-on constraint embedded in the avatar's persona that forces English-only output regardless of student input language.
- **Activity Flow Config**: The per-activity JSON file (`flow_config.json`) that defines nodes, transitions, task instructions, and role instructions. The fallback config integrates with this structure without modifying individual activity files.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a test session where the student goes off-topic, the avatar returns to the task within 2 conversational turns in at least 9 out of 10 cases.
- **SC-002**: In a test session where the student says "I don't know," the avatar never repeats the exact same question verbatim in the next turn.
- **SC-003**: In a test session where the student responds in a non-English language, 100% of the avatar's turns are in English.
- **SC-004**: Adding a new fallback scenario to the shared config and verifying it in two different activities requires editing exactly one file and takes under 10 minutes.
- **SC-005**: No flow-state transition function is triggered during an off-topic or refusal interaction; all transitions occur only after the student returns to the task.

## Assumptions

- The fallback system targets child learners in the 8–12 age range; language and tone are calibrated for this range uniformly across all activities.
- English is the only supported response language for the avatar; this is a hard platform constraint, not a per-session setting.
- The "off-topic" detection relies on the LLM's natural language understanding of the current task context, not a separate classifier.
- The shared fallback config integrates via the `role_messages` field in `flow_config.json` nodes (the persistent persona prompt), since this field is already the mechanism for cross-node behavioral guidelines.
- Silence detection (elongated pauses) is handled here as part of the refusal fallback layer, not solely at the transport layer. The pipeline's VAD determines the actual audio silence window; the fallback instruction tells the avatar what to say when no student response has arrived.
- Sessions are monitored by an adult supervisor; safety-critical edge cases (e.g., a student disclosing harm) are handled through human oversight and are out of scope for automated avatar response.
- The Flow Builder (`src/flow-builder/`) is the canonical tool for editing `flow_config.json`; the shared fallback config is loader-level and does not require Flow Builder changes.
