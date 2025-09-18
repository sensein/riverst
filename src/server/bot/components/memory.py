import json
import os
import shutil
from pathlib import Path
from typing import List, Dict, Any
from loguru import logger


class MemoryHandler:
    """Handles memory management for bot conversations including session persistence."""

    def __init__(self, session_dir: str, user_id: str):
        self.session_dir = session_dir
        self.user_id = user_id

    def build_memory_context(
        self, instruction: str, long_term_memory: bool, short_term_memory: bool
    ) -> List[Dict[str, str]]:
        """Build message context with memory configuration."""
        messages = [{"role": "system", "content": instruction}]

        if long_term_memory:
            long_term_messages = self._load_long_term_memory()
            if long_term_messages:
                messages.extend(long_term_messages)

        logger.debug("Messages before this session: {}", len(messages))

        if short_term_memory:
            short_term_messages = self._load_short_term_memory()
            if short_term_messages:
                messages.extend(short_term_messages)
        else:
            self._cleanup_session_directory()
            if long_term_memory and len(messages) > 1:
                messages.append(
                    {
                        "role": "system",
                        "content": (
                            "Please make a summary of the previous conversations so far "
                            "(stressing goals and achievements), "
                            "and then continue the conversation from where you left."
                            "Use expressions like 'I remember' or 'I recall' or 'Last time' "
                            "or 'Another time' to reference previous conversations."
                            "You can also specify the date of the previous conversation if necessary."
                        ),
                    }
                )

        return messages

    def _read_transcript_file(self, transcript_path: Path) -> List[Dict[str, Any]]:
        """Read and parse a transcript file into JSON, or return [] if missing/invalid."""
        if not transcript_path.exists():
            logger.debug("Transcript file not found: {}", transcript_path)
            return []

        try:
            with transcript_path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error("Failed to read transcript {}: {}", transcript_path, e)
            return []

    def _parse_messages(
        self, raw_messages: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """Normalize raw transcript messages into role/content format."""
        return [
            {
                "role": "user" if m.get("role") == "user" else "assistant",
                "content": m.get("content", ""),
            }
            for m in raw_messages
            if "content" in m
        ]

    def _wrap_with_system(
        self, messages: List[Dict[str, str]], start: str, end: str
    ) -> List[Dict[str, str]]:
        """Wrap messages with system start/end markers."""
        return (
            [{"role": "system", "content": start}]
            + messages
            + [{"role": "system", "content": end}]
        )

    def _load_session_transcript(
        self, parent_dir: Path, session_id: str
    ) -> List[Dict[str, str]]:
        """Load transcript from a specific session."""
        raw = self._read_transcript_file(parent_dir / session_id / "transcript.json")
        if not raw:
            return []
        messages = self._parse_messages(raw)
        return self._wrap_with_system(
            messages,
            f"--- Start of previous session `{session_id}` ---",
            f"--- End of previous session `{session_id}` ---",
        )

    def _load_short_term_memory(self) -> List[Dict[str, str]]:
        """Load messages from current session transcript for short-term memory."""
        raw = self._read_transcript_file(Path(self.session_dir) / "transcript.json")
        if not raw:
            logger.info("Transcript.json not found. Starting a new conversation.")
            return []

        messages = self._parse_messages(raw)
        return self._wrap_with_system(
            messages,
            "--- Start of the current session ---",
            (
                "Please continue the current conversation from where you left. "
                "There has been an interruption. "
                "Make a summary of the current conversation so far before continuing."
            ),
        )

    def _load_long_term_memory(self) -> List[Dict[str, str]]:
        """Load messages from previous sessions for long-term memory."""
        logger.debug("Building long-term memory...")

        parent_dir = Path(self.session_dir).parent
        current_session_name = Path(self.session_dir).name

        if not parent_dir.exists():
            logger.warning("Parent directory {} does not exist", parent_dir)
            return []

        user_sessions = sorted(
            [
                d.name
                for d in parent_dir.iterdir()
                if d.is_dir()
                and d.name.startswith(self.user_id)
                and d.name != current_session_name
            ]
        )

        logger.debug("Previous sessions for user {}: {}", self.user_id, user_sessions)

        all_past_messages: List[Dict[str, str]] = []
        for session_id in user_sessions:
            all_past_messages.extend(
                self._load_session_transcript(parent_dir, session_id)
            )

        return all_past_messages

    def _cleanup_session_directory(self) -> None:
        """Clean up session directory when short-term memory is disabled."""
        logger.info("Short term memory disabled. Starting a new conversation.")

        for item in os.listdir(self.session_dir):
            item_path = os.path.join(self.session_dir, item)

            if os.path.isdir(item_path) and item in ("audios", "json"):
                try:
                    shutil.rmtree(item_path)
                    logger.debug("Deleted folder: {}", item_path)
                except Exception as e:
                    logger.error("Failed to delete folder {}: {}", item_path, e)
            elif os.path.isfile(item_path):
                if self._should_delete_file(item):
                    try:
                        os.remove(item_path)
                        logger.debug("Deleted file: {}", item_path)
                    except Exception as e:
                        logger.error("Failed to delete file {}: {}", item_path, e)

    def _should_delete_file(self, filename: str) -> bool:
        """Determine if a file should be deleted during session cleanup."""
        cleanup_files = ("metrics_log.json", "metrics_summary.json", "transcript.json")
        return filename in cleanup_files or (
            filename.startswith("session_")
            and (filename.endswith(".wav") or filename.endswith(".mp4"))
        )
