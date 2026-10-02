# Feature Specification: Sandbox Session Transcript Storage in S3

**Feature Branch**: `claude/sandbox-s3-transcripts-22f273`
**Created**: 2026-09-22
**Status**: Draft
**Input**: User description: "connect the sandbox environment to an S3 bucket and save the transcripts of each session there"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Transcripts survive instance loss (Priority: P1)

Today, sandbox session transcripts live only on the sandbox instance's local
disk. The instance is stopped nightly and can be rebuilt or replaced at any
time, so a transcript can be lost with no way to recover it. After this
feature, every completed session's transcript is durably copied to an S3
bucket, so it remains available regardless of what happens to the instance
afterward.

**Why this priority**: This is the core problem statement — transcripts are
currently at risk of permanent loss. Every other story depends on the
transcript existing durably in S3 first.

**Independent Test**: Can be fully tested by running a sandbox session to
completion, then stopping (or simulating the nightly stop of) the sandbox
instance, and confirming the session's transcript is still readable from the
S3 bucket.

**Acceptance Scenarios**:

1. **Given** a sandbox session runs to completion, **When** the session ends,
   **Then** that session's transcript appears in the S3 bucket under a key
   that identifies the session.
2. **Given** a transcript has been uploaded to S3, **When** the sandbox
   instance is later stopped, terminated, or rebuilt, **Then** the transcript
   remains retrievable from the bucket unchanged.

---

### User Story 2 - Reviewer retrieves a past session without EC2 access (Priority: P2)

A team member who wants to review or analyze a sandbox session's conversation
(e.g., for behavioral analysis or debugging) can find and download that
session's transcript directly from S3 using the session ID, without needing
SSH or file access on the sandbox instance itself.

**Why this priority**: Durable storage only pays off if the transcripts are
also easy to find and retrieve; this is the primary reason anyone would look
in the bucket.

**Independent Test**: Can be fully tested by taking a known session ID from a
completed sandbox session and locating and downloading its transcript from
the S3 bucket using only bucket access (no EC2 access).

**Acceptance Scenarios**:

1. **Given** a session ID for a completed sandbox session, **When** a team
   member looks in the S3 bucket, **Then** they can identify and download the
   matching transcript without ambiguity about which session it belongs to.

---

### User Story 3 - Upload happens automatically, every session (Priority: P3)

No one has to remember to copy transcripts off the sandbox instance before it
stops for the night, or run any manual export step. Each session's transcript
is uploaded to S3 automatically as part of normal session teardown.

**Why this priority**: Removes reliance on a human remembering a manual step;
without this, the feature degrades back into an easily-forgotten chore.

**Independent Test**: Can be fully tested by running several sandbox sessions
back to back with no manual intervention and confirming all of their
transcripts show up in S3 without anyone running an upload command.

**Acceptance Scenarios**:

1. **Given** a sandbox session completes normally, **When** no manual action
   is taken, **Then** its transcript is present in S3 within seconds of the
   session ending — the upload is dispatched immediately at session
   teardown, not on a delay or batch schedule.
2. **Given** the nightly sandbox stop occurs, **When** sessions completed
   earlier that day are checked, **Then** all of their transcripts were
   already uploaded before the stop (upload happens at session end, not at
   shutdown).

### Edge Cases

- What happens when the S3 upload fails (network issue, permissions,
  throttling)? The session MUST still end normally for the user; the failure
  is logged, and the transcript remains on local disk for later retry rather
  than being lost.
- What happens if the S3 bucket or credentials are misconfigured? The system
  surfaces a clear, loggable error rather than failing silently or crashing
  the session.
- What happens if a session ends abnormally (crash, disconnect) partway
  through? Whatever transcript content exists locally at that point is still
  uploaded; the feature does not depend on a clean shutdown path.
- What happens if two sessions somehow share a session ID? Out of scope —
  session IDs are already assumed unique by the existing local storage
  scheme.
- What happens on repeated uploads of the same session (e.g., a retry)? The
  later upload MUST overwrite/replace the same key rather than creating
  duplicate or ambiguous copies.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST have a dedicated S3 bucket designated as the
  destination for sandbox session transcripts.
- **FR-002**: When a sandbox session ends, the system MUST upload that
  session's transcript to the designated S3 bucket.
- **FR-003**: Each uploaded transcript MUST be stored under a key that
  uniquely identifies the session it belongs to, so it can be located by
  session ID alone.
- **FR-004**: A failure to upload a transcript to S3 MUST NOT prevent or
  delay the session from ending normally for the user, and MUST be logged.
- **FR-005**: The system MUST retain the local copy of a transcript when its
  S3 upload fails, so the data is not lost.
- **FR-006**: Uploading a transcript MUST require no manual action by an
  operator; it happens as part of normal session completion.
- **FR-007**: Access to the S3 bucket MUST be restricted to authorized
  Riverst infrastructure and personnel — it MUST NOT be publicly readable or
  writable.
- **FR-008**: Re-uploading a transcript for the same session MUST replace the
  existing object rather than create a duplicate or conflicting one.
- **FR-009**: This feature applies to the sandbox environment only; the
  production environment is out of scope unless separately specified.

### Key Entities

- **Session Transcript**: The JSON record of a session's conversation turns,
  currently produced and saved locally by the existing transcript handler.
  This feature adds a durable, off-instance copy of the same content.
- **S3 Bucket**: Dedicated durable object storage for the sandbox
  environment's transcripts, one object per session.
- **Upload Event**: The action, triggered automatically at session end, that
  copies a session's transcript from local disk to the S3 bucket.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of sandbox sessions that complete after this feature
  ships have a matching transcript object in the S3 bucket.
- **SC-002**: A session's transcript remains retrievable from S3 after the
  sandbox instance has been stopped, restarted, or rebuilt.
- **SC-003**: An S3 upload failure never causes a user-visible session
  failure or delay — zero session-teardown errors are attributable to the
  upload step.
- **SC-004**: A team member can locate and download any given session's
  transcript from S3 using only its session ID, in under a couple of
  minutes, without EC2 access.
- **SC-005**: No sandbox session transcript is publicly accessible outside
  authorized Riverst infrastructure and personnel.

## Assumptions

- "Sandbox environment" refers to the Terraform-managed `sandbox` environment
  (`infra/envs/sandbox`); production is a separate, hand-built environment
  and is out of scope for this feature.
- "Transcripts" refers to the conversation transcript JSON already produced
  by the existing transcript handler for each session, not the full session
  directory (e.g., recorded audio files) — those remain local-disk-only
  unless a future feature extends this to other artifacts.
- The S3 bucket is new, dedicated infrastructure for this purpose, managed
  alongside the rest of the sandbox environment's Terraform configuration.
- The sandbox instance already has (or can be granted) an IAM identity
  suitable for scoping S3 permissions to only this bucket.
- Uploads happen from the sandbox instance itself at session-end time; no
  separate polling or batch-export process is introduced.
- "Authorized Riverst infrastructure and personnel" (FR-007, SC-005) means
  the existing account-level access model already used for every other
  resource in this AWS account — the same admin identity that already has
  SSM/console access to secrets and instances. This feature does not create
  a separate reviewer-specific IAM identity or bucket policy for humans; it
  only scopes the *sandbox instance's own* write access to this one bucket.
