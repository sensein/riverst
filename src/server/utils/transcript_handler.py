"""This module provides the TranscriptHandler class for managing real-time transcript updates."""

import os
import json
from typing import List, Optional

import aiofiles
from loguru import logger

from pipecat.processors.transcript_processor import TranscriptProcessor
from pipecat.frames.frames import TranscriptionUpdateFrame


class TranscriptHandler:
    """Handles real-time transcript updates and optionally logs them to file.

    Tracks incoming messages with timestamp and role, either printing them to log
    or persisting to a file. Useful for monitoring and debugging conversation flows.
    """

    def __init__(self, output_file: Optional[str] = None):
        """
        Args:
            output_file: Path to the file where messages should be saved.
                         If None, messages are only logged to the console.
        """
        self.output_file = output_file
        self.messages: List[dict] = []

        if output_file:
            try:
                if os.path.exists(output_file):
                    with open(output_file, "r", encoding="utf-8") as f:
                        self.messages = json.load(f)
            except Exception as e:
                logger.error(f"Error reading transcript file: {e}")
                raise ValueError(
                    f"Error reading transcript file: {e}. Please check the file format."
                )

        logger.debug(
            f"TranscriptHandler initialized "
            f"{f'with output_file={output_file}' if output_file else 'with log output only'}"
        )

    async def save_messages(self):
        """Persist current transcript messages to file, if configured."""
        if not self.output_file:
            return

        try:
            os.makedirs(os.path.dirname(self.output_file), exist_ok=True)
            async with aiofiles.open(self.output_file, "w", encoding="utf-8") as f:
                await f.write(json.dumps(self.messages, indent=2))
        except Exception as e:
            logger.error(f"Error saving transcript to file: {e}")

    async def on_transcript_update(
        self,
        processor: TranscriptProcessor,
        frame: TranscriptionUpdateFrame,
    ):
        """Process new transcript messages from a frame.

        Args:
            processor: The TranscriptProcessor generating the update.
            frame: A TranscriptionUpdateFrame with one or more messages.
        """
        logger.debug(f"Received transcript update with {len(frame.messages)} messages")

        for msg in frame.messages:
            updated = False

            for existing_msg in reversed(self.messages):
                if (
                    existing_msg.get("role") == msg.role
                    and "audio_file" in existing_msg
                    and not existing_msg.get("content")
                ):
                    existing_msg["content"] = msg.content
                    existing_msg["timestamp"] = msg.timestamp
                    logger.info(f"Updated existing transcript: {existing_msg}")
                    updated = True
                    break

            if not updated:
                new_entry = {
                    "index": len(self.messages),
                    "timestamp": msg.timestamp or None,
                    "role": msg.role,
                    "content": msg.content,
                }
                self.messages.append(new_entry)
                logger.info(f"New transcript: {new_entry}")

        await self.save_messages()
