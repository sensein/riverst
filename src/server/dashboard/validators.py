"""Deterministic checks on generated session summaries.

They keep summaries consistent with the recorded word outcomes (FR-019) and stop them quoting the
student (FR-021). Each check returns a list of plain-language violations; an empty list means it passed.
"""

import re
from typing import Any, Dict, Iterable, List

MAX_SUMMARY_WORDS = 140
QUOTE_RUN = 6

_TOKEN = re.compile(r"[a-z0-9']+")


def _tokens(text: str) -> List[str]:
    return _TOKEN.findall((text or "").lower().replace("’", "'"))


def check_length(text: str, max_words: int = MAX_SUMMARY_WORDS) -> List[str]:
    """The summary text must stay within the word limit."""
    count = len((text or "").split())
    return (
        [f"The summary is {count} words; keep it under {max_words}."]
        if count > max_words
        else []
    )


def check_word_consistency(
    summary: Dict[str, Any], outcomes: Iterable[Dict[str, Any]]
) -> List[str]:
    """Words the summary calls easy or hard must agree with the recorded outcomes.

    Args:
        summary: The structured summary with ``words_went_well`` and ``words_hard``.
        outcomes: The session's word outcomes.

    Returns:
        List[str]: Violations, for example a word listed as going well that wasn't mastered.
    """
    taught = {o["word"].lower(): o for o in outcomes if o["disposition"] == "taught"}
    problems = []
    for word in summary.get("words_went_well", []):
        outcome = taught.get(word.lower())
        if outcome is None:
            problems.append(
                f'"{word}" is listed as going well but was not one of the taught words.'
            )
        elif outcome.get("review_result") == "not_mastered":
            problems.append(
                f'"{word}" is listed as going well but was not mastered in the review.'
            )
    for word in summary.get("words_hard", []):
        outcome = taught.get(word.lower())
        if outcome is None:
            problems.append(
                f'"{word}" is listed as hard but was not one of the taught words.'
            )
            continue
        steps = (outcome.get("steps") or {}).values()
        if (
            outcome.get("review_result") == "mastered"
            and steps
            and all(s == "completed" for s in steps)
        ):
            problems.append(
                f'"{word}" is listed as hard but every step was completed and it was mastered.'
            )
    return problems


def check_no_quotes(
    fields: Iterable[str], user_turns: Iterable[str], run: int = QUOTE_RUN
) -> List[str]:
    """No run of ``run`` or more consecutive words from the student may appear in the summary.

    Matching ignores case and punctuation.

    Args:
        fields: Summary text fields to check.
        user_turns: The student's transcript turns.
        run: Length of word run that counts as a quote.

    Returns:
        List[str]: One violation per quoted run found.
    """
    student_runs = set()
    for turn in user_turns:
        tokens = _tokens(turn)
        for i in range(len(tokens) - run + 1):
            end = i + run
            student_runs.add(tuple(tokens[i:end]))
    if not student_runs:
        return []
    problems = []
    for field in fields:
        tokens = _tokens(field)
        for i in range(len(tokens) - run + 1):
            end = i + run
            if tuple(tokens[i:end]) in student_runs:
                quoted = " ".join(tokens[i:end])
                problems.append(
                    f'The summary quotes the student ("{quoted}…"). Describe instead.'
                )
                break
    return problems
