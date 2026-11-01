# Feature Specification: Teacher Monitoring Dashboard

**Feature Branch**: `010-teacher-dashboard`
**Created**: 2026-10-08
**Status**: Draft
**Input**: User description: "I want to build a monitoring dashboard from the point of view of a teacher using kiva in the classroom. The dashboard should be able to link to several students and if you click on a student you should get a summary of their reading level and vocabulary progress based on the sessions they've completed. if you go further into details, you should be able to see for each session which words were taught, which words were skipped because the student knows them, whether the student was able to complete each task for each word (context in the story, relate to it in their life, use it in a sentence, etc). Then it should also generate a session level summary for how the session went. the dashboard should be simple and intuitive to use. add any features that you think would be useful and i missed."

## Context

Today KIVA has no idea of a teacher or a student. Each session is filed under a random identifier chosen on the device. The per-word learning outcomes (which words were known, taught, and mastered, and which teaching steps were done) are tracked while a session runs but are thrown away when it ends. The only saved records are the transcript, the audio, and technical performance metrics. This feature therefore covers three things:

1. Students linked to a teacher.
2. Durable recording of per-word learning outcomes.
3. A teacher-facing view on top of both.

The four teaching steps KIVA uses for each new word are:

1. **Simple definition**: KIVA explains the word in kid-friendly terms.
2. **Story context**: the student is asked what the word means in the sentence from the book.
3. **Personal connection**: the student relates the word to their own life.
4. **Own sentence**: the student makes up a new sentence using the word.

After the teaching steps, a **review** checks each taught word again. The student re-defines it and uses it in a sentence, and the word is marked *mastered* or *not yet mastered*. If a student says they already know a word and explains it correctly, the word is recorded as *known* and skipped.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See my class at a glance (Priority: P1)

A teacher opens the dashboard and sees all of their linked students on one screen. Each student has a row or card showing:

- name
- date of last session
- number of sessions completed
- current reading level
- words mastered so far
- a simple status indicator ("on track", "needs attention", "inactive")

From this screen the teacher can tell in seconds who is progressing and who needs help.

**Why this priority**: This is the entry point for everything else. Even on its own it answers the most common teacher question: "who is using KIVA, and is anyone struggling?"

**Independent Test**: Link three students with different session histories. Open the dashboard and confirm that each student shows correct counts, last-session dates, and status, all without any further clicks.

**Acceptance Scenarios**:

1. **Given** a teacher with 25 linked students, **When** they open the dashboard, **Then** all 25 students are listed with name, last session date, sessions completed, reading level, words mastered, and status.
2. **Given** a student who has not done a session in more than 7 days, **When** the teacher views the class overview, **Then** that student is marked "inactive".
3. **Given** a student whose last 2 completed sessions each had at least half of the taught words *not yet mastered*, **When** the teacher views the class overview, **Then** that student is marked "needs attention".
4. **Given** a class list, **When** the teacher sorts by name, last session, or words mastered, or filters by status, **Then** the list updates right away.
5. **Given** a newly linked student with no sessions, **When** the teacher views the class, **Then** the student appears with "No sessions yet" in place of the metrics.

---

### User Story 2 - Link students to my class (Priority: P1)

A teacher adds students to their class and connects each student to the KIVA sessions that student does. After that, every session the student completes appears on the teacher's dashboard automatically.

**Why this priority**: Without linking, there is nothing to show. This has to ship together with Story 1 to be a usable MVP.

**Independent Test**: A teacher adds a student. The student completes a session through the linked identity. The session then appears under that student on the teacher's dashboard.

**Acceptance Scenarios**:

1. **Given** a teacher on the dashboard, **When** they add a student by entering a display name, **Then** the student appears in their class with a unique student code and a matching link.
2. **Given** a student code, **When** the student starts KIVA using the code or link, **Then** the session is attributed to that student. The student does not need an account or a password.
3. **Given** a student who starts KIVA without a code, **When** the session completes, **Then** it does not appear on any teacher's dashboard.
4. **Given** a linked student, **When** that student completes a session, **Then** the session appears under the student on the teacher's dashboard without any manual step.
5. **Given** a teacher, **When** they rename, archive, or unlink a student, **Then** the change shows on the dashboard and archived students are hidden from the default class view.
6. **Given** a student whose code may have been shared or lost, **When** the teacher regenerates the code, **Then** the old code stops working and the student's past sessions stay linked.
7. **Given** two teachers, **When** each views their dashboard, **Then** each sees only the students linked to their own class.

---

### User Story 3 - Student progress summary (Priority: P1)

The teacher clicks a student and gets a one-page summary showing:

- the student's current reading level and how it has changed
- cumulative vocabulary progress: words known on arrival, words taught, words mastered, and words still being learned
- a timeline of the student's sessions
- a short plain-language summary of the student's strengths and areas to work on

**Why this priority**: This is the core value the teacher asked for: understanding one student's reading and vocabulary growth over time.

**Independent Test**: Give a student 5 completed sessions with known outcomes. Open the student and confirm the totals, the trend, and the session list match those sessions.

**Acceptance Scenarios**:

1. **Given** a student with 5 completed sessions, **When** the teacher opens the student, **Then** they see totals for words known, taught, mastered, and not yet mastered across all sessions.
2. **Given** a student, **When** the teacher opens the student, **Then** they see the current reading level, the level at the first session, and a simple trend over time.
3. **Given** a student, **When** the teacher opens the student, **Then** they see a list of every word the student has met, each with its latest status (known / mastered / still learning) and the session where it last came up.
4. **Given** a student's word list, **When** the teacher filters to "still learning", **Then** only words not yet mastered are shown, as a ready-made list of words to revisit.
5. **Given** a student, **When** the teacher opens the student, **Then** a 2–4 sentence plain-language progress summary is shown, covering strengths, recurring difficulties (for example, "often struggles to use new words in their own sentence"), and a suggested focus.

6. **Given** a student whose estimated reading level the teacher disagrees with, **When** the teacher sets a level manually, **Then** the teacher-set level is shown, marked "set by teacher", and the automatic estimate stays visible alongside it.
7. **Given** a teacher-set level, **When** the teacher clears it, **Then** the automatic estimate is shown again.

**Reading level** is estimated automatically from the grade band (4, 5 or 6) of the words the student masters or already knows. The estimate is the highest grade band in which the student has mastered or already knew at least two-thirds of the words they encountered, across their last 5 sessions. A band only counts if the student encountered at least 2 of its words in those sessions. If no band meets that threshold, the level is shown as "below grade 4 words". With fewer than 2 sessions, the level is shown as "not enough sessions yet". The teacher can override the estimate at any time.

---

### User Story 4 - Session detail with per-word task outcomes (Priority: P2)

From a student's session list, the teacher opens one session and sees:

- the book and chapter, the date, and the duration
- **Words skipped (already known)**: each word the student said they knew and explained correctly
- **Words taught**: for each word, whether the student completed each teaching step (simple definition heard, story context, personal connection, own sentence), plus the review result (mastered / not yet mastered)

The teacher sees outcomes and summaries only. The student's raw responses, transcript and voice recordings are never shown.

**Why this priority**: This is the drill-down the teacher explicitly asked for. It is lower than P1 because the overview and summary already deliver value without it.

**Independent Test**: Run a session where the student knows 1 word, completes all steps for a second word, and fails the "own sentence" step for a third. Open the session and confirm each outcome is shown correctly.

**Acceptance Scenarios**:

1. **Given** a completed session, **When** the teacher opens it, **Then** known/skipped words and taught words are listed in separate, clearly labeled groups.
2. **Given** a taught word, **When** the teacher views it, **Then** each of the four teaching steps shows as completed, attempted but not completed, or not reached, and the review result is shown.
3. **Given** any session view, **When** the teacher looks for the student's own words, transcript, or recordings, **Then** none are available. Only outcomes and generated summaries are shown.
4. **Given** a session that ended early (for example, the student left after 1 word), **When** the teacher opens it, **Then** the steps that were never reached are marked "not reached", and the session is labeled "ended early".

---

### User Story 5 - Auto-generated session summary (Priority: P2)

Each completed session has a short, auto-generated summary of how it went:

- engagement (for example, responsive vs. many short or off-topic answers)
- which words went well and which were hard
- notable moments (for example, a strong personal connection the student made)
- one or two suggestions for the teacher

**Why this priority**: Teachers never see raw session content, so the summary is their only narrative view of how a session went. It depends on the per-word data from Story 4.

**Independent Test**: Complete a session and open it. A summary is present at the top of the session detail, and its claims match the recorded per-word outcomes.

**Acceptance Scenarios**:

1. **Given** a completed session, **When** the teacher opens it, **Then** a summary of no more than about 120 words appears at the top of the session detail.
2. **Given** a session summary, **When** it states that a word was mastered or struggled with, **Then** that claim agrees with the recorded per-word outcome.
3. **Given** a session for which no summary could be produced, **When** the teacher opens it, **Then** the per-word detail still shows and the summary area says it is unavailable, with an option to retry.

---

### User Story 6 - Class-wide vocabulary insights (Priority: P3)

The teacher sees which words are hardest across the class. For each word, the view shows how many students were taught it, how many mastered it, and how many already knew it. Which teaching step students most often fail is also highlighted. This helps the teacher plan whole-class instruction.

**Why this priority**: This is a useful extra beyond the original request. It builds on the same data.

**Independent Test**: Given several students with sessions on the same chapter, the class word view shows the correct counts per word, and sorting by "least mastered" puts the hardest word first.

**Acceptance Scenarios**:

1. **Given** a class with sessions on shared books, **When** the teacher opens class insights, **Then** each word shows counts for known, taught, mastered, and still learning.
2. **Given** class insights, **When** the teacher sorts by mastery rate, **Then** the words with the lowest mastery appear first.
3. **Given** class insights, **When** the teacher selects a word, **Then** they see which students are still learning it.

---

### User Story 7 - Share and keep notes (Priority: P3)

The teacher can:

- add a private note to a student or a session (for example, "was tired today")
- produce a printable or downloadable progress report for a student, for parent conferences or records

**Why this priority**: A useful extra for real classroom workflows. It is not required for monitoring.

**Independent Test**: Add a note to a session, reload, and confirm the note persists. Generate a student report and confirm it contains the summary, the word lists, and the session history.

**Acceptance Scenarios**:

1. **Given** a session or student, **When** the teacher adds a note, **Then** it is saved, shown with a timestamp, and visible only to that teacher.
2. **Given** a student, **When** the teacher requests a progress report, **Then** they get a printable document with the student's progress summary, word lists by status, and session history.

---

### Edge Cases

- **Sessions recorded before this feature exists** have no student link, so they are not shown on the dashboard.
- **A session whose results could not be produced** appears in the session list labeled "detailed results not available", with a Retry option. It does not count toward word totals.
- **A session that disconnects or is abandoned mid-word** keeps the outcomes recorded up to that point. Remaining steps are "not reached". The session is labeled "ended early". Its words still count toward the student's totals, but only completed sessions are used for the "needs attention" status.
- **The same word comes up in multiple sessions** (for example, not mastered first, mastered later). The student summary shows the latest status and keeps the history.
- **A student claims to know a word but explains it incorrectly.** The word is taught, not skipped, and it appears under "taught".
- **A session runs with a teacher vocabulary override.** The session detail shows that the words were teacher-selected.
- **A session runs under a non-vocabulary activity.** The student code is only offered for the KIVA vocabulary activity, so such sessions are not linked to students and are not shown.
- **A student is unlinked or archived.** Their past data stays available to the teacher in an "archived" view and is not deleted.
- **A student enters an invalid, regenerated, or mistyped code.** KIVA tells them the code wasn't recognized and lets them retry. It does not silently attribute the session to the wrong student.
- **Two devices use the same student code at the same time.** Both sessions are attributed to that student.
- **An empty class** shows a clear first-step prompt to add students.

## Requirements *(mandatory)*

### Functional Requirements

**Teacher access & class management**

- **FR-001**: Teachers MUST be able to sign in to the dashboard. Each teacher MUST only see students and sessions linked to their own class.
- **FR-002**: Teachers MUST be able to add, rename, archive, and unlink students in their class.
- **FR-003**: The system MUST give each student a unique student code and link. Sessions started with that code or link MUST be attributed to the student and appear on the teacher's dashboard with no manual step. Students MUST NOT need an account or a password.
- **FR-003a**: Teachers MUST be able to regenerate a student's code. The old code stops working and past sessions stay linked.
- **FR-004**: Only accounts with the teacher role MUST be able to open the dashboard or any teacher data. A student who signs in with a code, or a device signed in with a non-teacher account, MUST NOT reach it.

**Learning outcome recording**

- **FR-005**: For every vocabulary session, the system MUST durably record, per word:
  - the word itself, its grade band, and the book and chapter
  - whether it was skipped as known or taught
  - for taught words, the outcome of each teaching step: simple definition, story context, personal connection, own sentence
  - the review result: mastered or not yet mastered
- **FR-006**: Each recorded step outcome MUST be one of: *completed*, *attempted – not completed*, *not reached*.
- **FR-007**: The system MAY use the session's conversation internally to produce outcomes and summaries. It MUST NOT show the student's raw responses to teachers.
- **FR-008**: The system MUST record session-level facts:
  - date and time, and duration
  - activity, book, and chapter
  - whether the session was completed or ended early
  - whether a teacher vocabulary override was used

**Class overview**

- **FR-009**: The dashboard home MUST list all active students with name, last session date, sessions completed, reading level, words mastered, and status.
- **FR-010**: The system MUST assign each student one status:
  - **inactive**: no session in more than 7 days
  - **needs attention**: in each of the last 2 completed sessions, at least half of the taught words were not yet mastered
  - **on track**: anything else
- **FR-011**: Teachers MUST be able to sort the class list by name, last session, and words mastered, and filter it by status.

**Student summary**

- **FR-012**: The student view MUST show cumulative counts of words known, taught, mastered, and still learning.
- **FR-013**: The student view MUST show the current reading level and its trend over the student's sessions. The level is estimated from word grade bands as defined in User Story 3.
- **FR-013a**: Teachers MUST be able to set or clear a manual reading level for a student. When one is set, it is the level shown everywhere, labeled "set by teacher", with the automatic estimate still visible.
- **FR-014**: The student view MUST list every word the student has encountered with its latest status, and MUST allow filtering by status.
- **FR-015**: The student view MUST show a chronological list of the student's sessions. Each entry shows the date, the book and chapter, the words taught, and the words mastered.
- **FR-016**: The system MUST generate a short plain-language progress summary for each student covering strengths, recurring difficulties, and a suggested focus. It MUST refresh when a new session is completed.

**Session detail & summary**

- **FR-017**: The session view MUST present known/skipped words and taught words as separate groups, with step-by-step outcomes and the review result for each taught word.
- **FR-018**: The system MUST generate a session summary (about 120 words or fewer) covering engagement, words that went well or were hard, notable moments, and suggestions.
- **FR-019**: Generated summaries MUST be consistent with the recorded per-word outcomes, and MUST NOT state outcomes that contradict them.
- **FR-020**: If a summary cannot be generated, the session detail MUST still display, show that the summary is unavailable, and allow a retry.
- **FR-021**: The dashboard MUST NOT expose session transcripts, the student's raw responses, or voice recordings. The session summary is the teacher's only narrative view of a session. Summaries MUST describe what happened without quoting the student word for word.

**Extras**

- **FR-022**: The system SHOULD provide a class-wide word view: per-word counts of known, taught, mastered, and still learning, plus the most commonly failed teaching step.
- **FR-023**: Teachers SHOULD be able to attach private, timestamped notes to students and sessions.
- **FR-024**: Teachers SHOULD be able to produce a printable progress report per student.

**Usability**

- **FR-025**: Any session detail MUST be reachable from the dashboard home in no more than 2 clicks: student, then session.
- **FR-026**: The dashboard MUST use plain classroom language (for example, "Mastered", "Still learning", "Already knew it") and no technical or system terms.
- **FR-027**: The dashboard MUST be usable on a laptop and on a tablet.

### Key Entities

- **Teacher**: A signed-in educator who owns one or more classes and sees only their own students.
- **Class**: A group of students belonging to a teacher.
- **Student**: A child linked to a class, identified by display name and a unique student code. Has many sessions, an automatically estimated reading level, and an optional teacher-set reading level. Can be active or archived.
- **Session**: One completed or ended-early KIVA activity by a student. Has a date, duration, activity, book and chapter, completion state, override flag, a generated summary, and many word outcomes.
- **Word Outcome**: One word within one session. Has the word, its grade band, and its disposition (known/skipped or taught). For taught words it has four step outcomes and the review result.
- **Student Progress Summary**: Generated overview for one student. Has cumulative counts, reading level history, the latest status per word, and a narrative summary.
- **Teacher Note**: Private text attached to a student or session, with a timestamp.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A teacher can identify which students need attention within 10 seconds of opening the dashboard.
- **SC-002**: A teacher can get from the dashboard home to the per-word outcomes of any session in 2 clicks or fewer.
- **SC-003**: In a check of at least 20 sessions, 100% of the recorded per-word outcomes (known vs. taught, each step's result, review result) match what happened in the session transcript.
- **SC-004**: At least 90% of generated session summaries are rated by teachers as "accurate" and "useful" in a pilot review, and none contradict the recorded outcomes.
- **SC-005**: First-time teacher users complete the core tasks unaided on their first attempt in at least 90% of cases: add a student, find a struggling student, open a session's word breakdown.
- **SC-006**: Session results and summaries appear on the dashboard within 2 minutes of the session ending.
- **SC-007**: The class overview loads in under 3 seconds for a class of 35 students with a full school year of sessions.
- **SC-008**: No teacher can view any student or session outside their own class.

## Assumptions

- The vocabulary activity flow (known-word check, the four teaching steps, review, 3 new words per session) stays as currently designed. The dashboard reports on it and does not change it.
- Teacher sign-in reuses the project's existing sign-in approach. Teachers are added through the same authorization mechanism used today: an administrator adds their email.
- Self-service teacher sign-up and in-app teacher invitations are out of scope for v1.
- Student devices are signed in with a classroom account that is not a teacher account. FR-004 depends on this: if a teacher signs a student device in with their own account, the dashboard is reachable from that device.
- v1 covers the KIVA "Child vocabulary training" activity only. The ESL and ISL vocabulary activities don't run the structured lesson flow that records known, taught and mastered words, so they are out of scope for v1.
- Teacher sign-in lasts 30 minutes, as for every account today. A teacher who stays longer is asked to sign in again.
- One teacher per class and one class per student for v1. Co-teachers and shared classes are out of scope.
- Students are children. Student records use a display name only. No student email or other contact details are collected.
- Generated summaries are produced after the session ends. A delay of up to 2 minutes is acceptable.
- Sessions completed before this feature ships will not have per-word detail. Backfilling them from old transcripts is out of scope for v1.
- "Mastered" means passing KIVA's end-of-session review for that word. Long-term retention across sessions is shown only through repeat encounters.
- Real-time monitoring of a live, in-progress session is out of scope for v1. The dashboard shows completed and ended-early sessions.
- Teachers have no access to raw session content (transcripts, the student's own words, audio). Who else, such as project researchers, can access it is unchanged by this feature.
- Parent-facing access is out of scope. The printable report (FR-024) is how teachers share progress.
