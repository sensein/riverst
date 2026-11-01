/**
 * types.ts
 * Shapes returned by the teacher dashboard API (/api/teacher/*).
 */

export interface ReadingLevel {
  value: number | null;
  source: "estimate" | "teacher";
  label: string;
}

export interface StudentBase {
  id: string;
  display_name: string;
  code: string;
  link: string;
  status: string;
}

export interface ClassStudent extends StudentBase {
  last_session_at: string | null;
  sessions_completed: number;
  words_mastered: number;
  reading_level: ReadingLevel;
}

export interface SessionListItem {
  id: string;
  started_at: string;
  book_title: string | null;
  chapter: number | null;
  completion: "completed" | "ended_early" | null;
  detail: "ready" | "pending" | "unavailable" | "not_applicable";
  words_taught: number;
  words_mastered: number;
}

export interface StudentWord {
  word: string;
  status: "mastered" | "still_learning" | "already_knew";
  grade_band: number | null;
  last_seen_session_id: string;
  last_seen_at: string;
  history: { session_id: string; result: string }[];
}

export interface StudentDetailData {
  student: StudentBase & {
    class_status: string;
    reading_level_override: number | null;
    reading_level: ReadingLevel;
    reading_level_estimate: ReadingLevel;
  };
  counts: {
    already_knew: number;
    taught: number;
    mastered: number;
    still_learning: number;
  };
  reading_level_trend: { session_id: string; date: string; level: number }[];
  summary: {
    status: "ready" | "failed" | "none";
    text: string | null;
    generated_at: string | null;
  };
  words: StudentWord[];
  sessions: SessionListItem[];
}

export type StepResult =
  | "completed"
  | "attempted_not_completed"
  | "not_reached"
  | null;

export interface SessionSummary {
  status: "ready" | "pending" | "failed";
  text?: string;
  engagement?: "high" | "mixed" | "low";
  words_went_well?: string[];
  words_hard?: string[];
  notable_moments?: string[];
  suggestions?: string[];
}

export interface SessionDetailData {
  session: {
    id: string;
    student_id: string;
    student_name: string;
    started_at: string;
    duration_seconds: number | null;
    activity_label: string;
    book_title: string | null;
    chapter: number | null;
    completion: "completed" | "ended_early" | null;
    teacher_selected_words: boolean;
  };
  detail: "ready" | "pending" | "unavailable" | "not_applicable";
  already_knew: { word: string; grade_band: number | null }[];
  taught: {
    word: string;
    grade_band: number | null;
    teacher_selected: boolean;
    steps: Record<string, StepResult>;
    review: "mastered" | "not_mastered" | "not_reached" | null;
  }[];
  summary: SessionSummary;
}

export interface Note {
  id: string;
  body: string;
  created_at: string;
  updated_at: string;
}

export interface WordInsight {
  word: string;
  grade_band: number | null;
  already_knew: number;
  taught: number;
  mastered: number;
  still_learning: number;
  mastery_rate: number | null;
  hardest_step: string | null;
  still_learning_students: { id: string; display_name: string }[];
}
