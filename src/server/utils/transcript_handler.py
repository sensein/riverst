from loguru import logger
from typing import List, Optional
import os
import json
import aiofiles
import asyncio
from pipecat.processors.transcript_processor import TranscriptProcessor
from pipecat.frames.frames import TranscriptionUpdateFrame
from senselab.audio.data_structures import Audio
from senselab.audio.tasks.features_extraction.api import extract_features_from_audios
from senselab.audio.tasks.preprocessing import downmix_audios_to_mono, resample_audios
from .utils import tensor_to_serializable

class TranscriptHandler:
    """Handles real-time transcript processing and output.

    Maintains a list of conversation messages and outputs them either to a log
    or to a file as they are received. Each message includes its timestamp and role.

    Attributes:
        messages: List of all processed transcript messages
        output_file: Optional path to file where transcript is saved. If None, outputs to log only.
    
    # TODO: doesn't seem to work well with openai_realtime_beta!!!
    """

    def __init__(self, output_file: Optional[str] = None):
        """Initialize handler with optional file output.

        Args:
            output_file: Path to output file. If None, outputs to log only.
        """
        self.messages: List[dict] = []
        self.output_file: Optional[str] = output_file

        logger.debug(
            f"TranscriptHandler initialized {'with output_file=' + output_file if output_file else 'with log output only'}"
        )

    async def save_messages(self):
        """Save messages"""
        if self.output_file:
            try:
                os.makedirs(os.path.dirname(self.output_file), exist_ok=True)
                async with aiofiles.open(self.output_file, "w", encoding="utf-8") as f:
                    await f.write(json.dumps(self.messages, indent=2))
            except Exception as e:
                logger.error(f"Error saving transcript message to file: {e}")

    async def on_transcript_update(
        self, processor: TranscriptProcessor, frame: TranscriptionUpdateFrame
    ):
        """Handle new transcript messages.

        Args:
            processor: The TranscriptProcessor that emitted the update
            frame: TranscriptionUpdateFrame containing new messages
        """
        logger.debug(f"Received transcript update with {len(frame.messages)} new messages")

        for msg in frame.messages:
            updated = False
            for existing_msg in reversed(self.messages):
                if (
                    existing_msg["role"] == msg.role
                    and "audio_file" in existing_msg
                    and not existing_msg.get("content")
                ):
                    existing_msg["content"] = msg.content
                    existing_msg["timestamp"] = msg.timestamp
                    logger.info(f"Updated message with transcript: {existing_msg}")
                    updated = True
                    break

            if not updated:
                data = {
                    "index": len(self.messages),
                    "timestamp": msg.timestamp if msg.timestamp else None,
                    "role": msg.role,
                    "content": msg.content,
                }
                self.messages.append(data)
                logger.info(f"Transcript: {data}")

        await self.save_messages()

    '''
    # TODO: future work is to integrate senselab analysis of the audio and transcript
    # (once the session is over)
    async def process_audio_background(self, filepath: str):
        try:
            print("Processing audio in background: ", filepath)

            loop = asyncio.get_running_loop()

            def run_all_blocking_operations():
                audio = Audio(filepath=filepath)
                audio = downmix_audios_to_mono([audio])[0]
                audios = resample_audios([audio], 16000)

                acoustic_feats = extract_features_from_audios(
                    audios=audios,
                    opensmile=True,
                    parselmouth=True,
                    torchaudio=False,
                    torchaudio_squim=False
                )

                return {
                    "features": acoustic_feats[0],
                }

            result = await loop.run_in_executor(None, run_all_blocking_operations)

            for msg in reversed(self.messages):
                if msg.get("audio_file") == filepath:
                    msg["features"] = tensor_to_serializable(result["features"])
                    logger.debug(f"Attached audio processing results to message: {msg}")
                    await self.save_messages()
                    break

        except Exception as e:
            logger.error(f"Error in background audio processing for {filepath}: {e}")
    '''
