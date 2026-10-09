import unittest
from datetime import datetime, timedelta, timezone

from dashboard import metrics

NOW = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)


def word(name, band=4, disposition="taught", review="mastered", steps=None):
    return {
        "word": name,
        "grade_band": band,
        "disposition": disposition,
        "review_result": None if disposition == "known" else review,
        "steps": steps or {},
    }


def session(sid, days_ago, words, completion="completed", ingested=True):
    return {
        "id": sid,
        "started_at": (NOW - timedelta(days=days_ago)).isoformat(),
        "completion": completion,
        "ingested": ingested,
        "words": words,
    }


class ReadingLevelTest(unittest.TestCase):
    def test_not_enough_sessions(self):
        self.assertIsNone(
            metrics.reading_level_estimate([session("a", 1, [word("x"), word("y")])])
        )

    def test_highest_qualifying_band_wins(self):
        sessions = [
            session("a", 3, [word("a1", 4), word("a2", 4), word("b1", 5)]),
            session(
                "b",
                2,
                [
                    word("b2", 5),
                    word("c1", 6, review="not_mastered"),
                    word("c2", 6, review="not_mastered"),
                ],
            ),
        ]
        self.assertEqual(metrics.reading_level_estimate(sessions), 5)

    def test_exactly_two_thirds_qualifies(self):
        sessions = [
            session("a", 3, [word("x", 6), word("y", 6, disposition="known")]),
            session("b", 2, [word("z", 6, review="not_mastered")]),
        ]
        self.assertEqual(metrics.reading_level_estimate(sessions), 6)

    def test_band_needs_two_words(self):
        sessions = [
            session("a", 3, [word("x", 6)]),
            session("b", 2, [word("y", 4, review="not_mastered")]),
        ]
        self.assertEqual(metrics.reading_level_estimate(sessions), "below_4")

    def test_only_last_five_sessions_count(self):
        old = [
            session(f"o{i}", 20 + i, [word(f"o{i}a", 6), word(f"o{i}b", 6)])
            for i in range(3)
        ]
        recent = [
            session(f"r{i}", i + 1, [word(f"r{i}", 4, review="not_mastered")])
            for i in range(5)
        ]
        self.assertEqual(metrics.reading_level_estimate(old + recent), "below_4")

    def test_uningested_sessions_are_ignored(self):
        sessions = [
            session("a", 3, [word("x"), word("y")]),
            session("b", 2, [], ingested=False),
        ]
        self.assertIsNone(metrics.reading_level_estimate(sessions))

    def test_override_takes_precedence(self):
        shown = metrics.display_reading_level(4, override=6)
        self.assertEqual(shown, {"value": 6, "source": "teacher", "label": "Grade 6"})
        self.assertEqual(
            metrics.display_reading_level(None)["label"], "Not enough sessions yet"
        )
        self.assertEqual(
            metrics.display_reading_level("below_4")["label"], "Below grade-4 words"
        )


class StatusTest(unittest.TestCase):
    def test_no_sessions(self):
        self.assertEqual(metrics.student_status([], NOW), "no_sessions")

    def test_inactive_boundary(self):
        self.assertEqual(
            metrics.student_status([session("a", 7, [word("x")])], NOW), "on_track"
        )
        self.assertEqual(
            metrics.student_status([session("a", 7.01, [word("x")])], NOW), "inactive"
        )

    def test_needs_attention_at_exactly_half(self):
        half = [word("x", review="not_mastered"), word("y")]
        sessions = [session("a", 3, half), session("b", 2, half)]
        self.assertEqual(metrics.student_status(sessions, NOW), "needs_attention")

    def test_ended_early_sessions_are_skipped(self):
        bad = [word("x", review="not_mastered")]
        sessions = [
            session("a", 4, bad),
            session("b", 3, [word("y")]),
            session("c", 2, bad, completion="ended_early"),
        ]
        self.assertEqual(metrics.student_status(sessions, NOW), "on_track")

    def test_session_without_taught_words_is_not_struggling(self):
        sessions = [
            session("a", 3, [word("x", review="not_mastered")]),
            session("b", 2, [word("y", disposition="known")]),
        ]
        self.assertEqual(metrics.student_status(sessions, NOW), "on_track")


class WordStatusTest(unittest.TestCase):
    def test_latest_status_wins_and_history_kept(self):
        sessions = [
            session("b", 1, [word("brave", review="mastered")]),
            session("a", 5, [word("brave", review="not_mastered")]),
        ]
        [entry] = metrics.word_statuses(sessions)
        self.assertEqual(entry["status"], "mastered")
        self.assertEqual([h["session_id"] for h in entry["history"]], ["a", "b"])
        counts = metrics.cumulative_counts(sessions)
        self.assertEqual(
            counts, {"already_knew": 0, "taught": 1, "mastered": 1, "still_learning": 0}
        )


class ClassInsightsTest(unittest.TestCase):
    def test_counts_and_hardest_step(self):
        miss = {"own_sentence": "attempted_not_completed"}
        students = [
            {
                "id": "s1",
                "display_name": "Maya",
                "sessions": [session("a", 1, [word("brave", steps=miss)])],
            },
            {
                "id": "s2",
                "display_name": "Leo",
                "sessions": [
                    session("b", 1, [word("brave", review="not_mastered", steps=miss)])
                ],
            },
            {
                "id": "s3",
                "display_name": "Ana",
                "sessions": [session("c", 1, [word("brave", disposition="known")])],
            },
        ]
        [entry] = metrics.class_word_insights(students)
        self.assertEqual(
            (entry["already_knew"], entry["taught"], entry["mastered"]), (1, 2, 1)
        )
        self.assertEqual(entry["mastery_rate"], 0.5)
        self.assertEqual(entry["hardest_step"], "own_sentence")
        self.assertEqual(
            entry["still_learning_students"], [{"id": "s2", "display_name": "Leo"}]
        )


if __name__ == "__main__":
    unittest.main()
