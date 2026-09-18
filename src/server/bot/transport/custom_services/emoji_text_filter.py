import re
from typing import Any, Mapping

from pipecat.utils.text.base_text_filter import BaseTextFilter

_EMOJI_RE = re.compile(
    "["
    "\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F6FF"
    "\U0001F1E0-\U0001F1FF"
    "\U00002600-\U000026FF"
    "\U00002700-\U000027BF"
    "\U0000FE00-\U0000FE0F"
    "\U0001F900-\U0001F9FF"
    "\U0001FA70-\U0001FAFF"
    "\U00002300-\U000023FF"
    "\U00002B50-\U00002B55"
    "\U0001F004"
    "\U0001F0CF"
    "]+",
    flags=re.UNICODE,
)


class EmojiTextFilter(BaseTextFilter):
    """Strips emoji characters from text before TTS synthesis."""

    async def update_settings(self, settings: Mapping[str, Any]):
        pass

    async def filter(self, text: str) -> str:
        return _EMOJI_RE.sub("", text).strip()

    async def handle_interruption(self):
        pass

    async def reset_interruption(self):
        pass
