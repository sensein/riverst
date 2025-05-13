"""This module contains various utility functions."""
import os
import io
import wave
import asyncio
import torch
import aiofiles
from typing import Any


def tensor_to_serializable(obj: Any) -> Any:
    """Recursively convert torch.Tensors in a structure to Python lists for serialization.

    Args:
        obj: The object to convert. Can be a torch.Tensor, dict, list, or other serializable type.

    Returns:
        A copy of `obj` where any torch.Tensor has been converted to a nested list.
    """
    if isinstance(obj, torch.Tensor):
        return obj.detach().cpu().tolist()
    elif isinstance(obj, dict):
        return {k: tensor_to_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [tensor_to_serializable(v) for v in obj]
    else:
        return obj


async def save_audio_file(
    audio: bytes,
    filename: str,
    sample_rate: int,
    num_channels: int
) -> None:
    """Asynchronously save raw audio bytes to a WAV file without blocking the event loop.

    This function:
      1. Ensures the target directory exists.
      2. Encodes the raw PCM bytes into WAV format in a background thread.
      3. Writes the resulting WAV data to disk asynchronously.

    Args:
        audio: Raw PCM audio data as bytes.
        filename: Full path (including filename) where the WAV file will be saved.
        sample_rate: Sampling rate of the audio (in Hz).
        num_channels: Number of audio channels (e.g., 1 for mono, 2 for stereo).

    Raises:
        OSError: If directory creation or file writing fails.
    """
    # Ensure the output directory exists
    os.makedirs(os.path.dirname(filename), exist_ok=True)

    def _encode_wav() -> bytes:
        """Blocking helper to encode raw bytes into WAV format."""
        with io.BytesIO() as buffer:
            with wave.open(buffer, "wb") as wf:
                wf.setsampwidth(2)
                wf.setnchannels(num_channels)
                wf.setframerate(sample_rate)
                wf.writeframes(audio)
            return buffer.getvalue()

    # Encode WAV in a thread to avoid blocking the event loop
    loop = asyncio.get_event_loop()
    wav_bytes = await loop.run_in_executor(None, _encode_wav)

    # Write to disk asynchronously
    async with aiofiles.open(filename, "wb") as f:
        await f.write(wav_bytes)
