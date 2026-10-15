"""Custom activity handlers for the vocab-tutoring activity."""

from pipecat_flows import FlowManager


async def lookup_word_in_chapter(args: dict, flow_manager: FlowManager) -> dict:
    """Look up the sentence containing a word in the current chapter's full text.

    Args:
        args: Must contain 'word' (str) — the vocabulary word to search for.
        flow_manager: Provides access to activity state and user session index.

    Returns:
        dict with keys:
            - 'status': 'success' or 'not_found'
            - 'word': the queried word (echoed back)
            - 'sentence': first sentence containing the word, or None
    """
    word = (args.get("word") or "").strip()
    if not word:
        return {"status": "not_found", "word": word, "sentence": None}

    chapter_text = flow_manager.state.get("activity", {}).get("chapter_text", {})
    chapters = chapter_text.get("chapters", [])

    index = flow_manager.state.get("user", {}).get("index")
    if index is None or not (1 <= index <= len(chapters)):
        return {"status": "not_found", "word": word, "sentence": None}

    sentences = chapters[index - 1].get("sentences", [])
    word_lower = word.lower()
    for sentence in sentences:
        if word_lower in sentence.lower():
            return {"status": "success", "word": word, "sentence": sentence}

    return {"status": "not_found", "word": word, "sentence": None}
