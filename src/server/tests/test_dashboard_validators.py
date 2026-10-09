import unittest

from dashboard import validators

ALL_DONE = {
    "definition": "completed",
    "story_context": "completed",
    "personal_connection": "completed",
    "own_sentence": "completed",
}
OUTCOMES = [
    {
        "word": "reluctant",
        "disposition": "taught",
        "review_result": "mastered",
        "steps": ALL_DONE,
    },
    {
        "word": "gleam",
        "disposition": "taught",
        "review_result": "not_mastered",
        "steps": {**ALL_DONE, "own_sentence": "attempted_not_completed"},
    },
    {"word": "brave", "disposition": "known", "review_result": None, "steps": {}},
]


class LengthTest(unittest.TestCase):
    def test_limit(self):
        self.assertEqual(validators.check_length("word " * 140), [])
        self.assertEqual(len(validators.check_length("word " * 141)), 1)


class ConsistencyTest(unittest.TestCase):
    def test_consistent_summary_passes(self):
        summary = {"words_went_well": ["Reluctant"], "words_hard": ["gleam"]}
        self.assertEqual(validators.check_word_consistency(summary, OUTCOMES), [])

    def test_not_mastered_word_cannot_go_well(self):
        self.assertEqual(
            len(
                validators.check_word_consistency(
                    {"words_went_well": ["gleam"]}, OUTCOMES
                )
            ),
            1,
        )

    def test_unknown_or_known_word_rejected(self):
        problems = validators.check_word_consistency(
            {"words_went_well": ["brave"], "words_hard": ["moon"]}, OUTCOMES
        )
        self.assertEqual(len(problems), 2)

    def test_fully_completed_mastered_word_cannot_be_hard(self):
        self.assertEqual(
            len(
                validators.check_word_consistency(
                    {"words_hard": ["reluctant"]}, OUTCOMES
                )
            ),
            1,
        )


class QuoteTest(unittest.TestCase):
    TURNS = ["I was reluctant to go to my grandma's house last summer!"]

    def test_six_word_quote_in_other_casing_and_punctuation(self):
        text = "Maya said: I WAS reluctant, to go to my... grandma's house."
        self.assertEqual(len(validators.check_no_quotes([text], self.TURNS)), 1)

    def test_five_word_overlap_passes(self):
        text = "She used reluctant to go to describe a family trip."
        self.assertEqual(validators.check_no_quotes([text], self.TURNS), [])

    def test_no_user_turns(self):
        self.assertEqual(
            validators.check_no_quotes(["anything at all here today ok"], []), []
        )


if __name__ == "__main__":
    unittest.main()
