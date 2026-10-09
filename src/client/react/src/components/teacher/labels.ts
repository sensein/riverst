/**
 * labels.ts
 * Plain classroom language for every teacher-facing value (FR-026).
 */

export const STATUS_LABELS: Record<string, string> = {
  on_track: "On track",
  needs_attention: "Needs attention",
  inactive: "Inactive",
  no_sessions: "No sessions yet",
  archived: "Archived",
};

export const WORD_STATUS_LABELS: Record<string, string> = {
  mastered: "Mastered",
  still_learning: "Still learning",
  already_knew: "Already knew it",
};

export const STEP_LABELS: Record<string, string> = {
  definition: "Heard a simple definition",
  story_context: "Explained it in the story",
  personal_connection: "Connected it to their life",
  own_sentence: "Used it in their own sentence",
};

export const STEP_ORDER = [
  "definition",
  "story_context",
  "personal_connection",
  "own_sentence",
] as const;

export const STEP_RESULT_LABELS: Record<string, string> = {
  completed: "Done",
  attempted_not_completed: "Tried, not yet",
  not_reached: "Not reached",
};

export const REVIEW_LABELS: Record<string, string> = {
  mastered: "Mastered",
  not_mastered: "Still learning",
  not_reached: "Not reviewed",
};

export const COMPLETION_LABELS: Record<string, string> = {
  completed: "Completed",
  ended_early: "Ended early",
};

export const ENGAGEMENT_LABELS: Record<string, string> = {
  high: "Engaged",
  mixed: "Mixed",
  low: "Low engagement",
};

/** Shown when a request fails; never shows server internals. */
export const LOAD_ERROR =
  "We couldn't load this page. Check your connection and try again.";

/** Formats an ISO date as e.g. "Oct 7, 2026". */
export const formatDate = (iso?: string | null): string =>
  iso
    ? new Date(iso).toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
        year: "numeric",
      })
    : "";

/** Formats an ISO date relative to now, e.g. "Today", "3 days ago". */
export const formatRelative = (iso?: string | null): string => {
  if (!iso) return "";
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
  if (days <= 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 14) return `${days} days ago`;
  return formatDate(iso);
};

/** Formats seconds as "12 min". */
export const formatDuration = (seconds?: number | null): string =>
  seconds == null ? "" : `${Math.max(1, Math.round(seconds / 60))} min`;

/** Readable grade band, e.g. "Grade 5". */
export const gradeBandLabel = (band?: number | null): string =>
  band ? `Grade ${band}` : "Teacher word";
