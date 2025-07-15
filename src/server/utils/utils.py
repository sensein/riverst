"""
Utility functions for audio processing and device selection.
"""

import os
import io
import wave
import math
import struct
import asyncio
import aiofiles

from typing import Any
import torch
from torch import device as TorchDevice

from senselab.utils.data_structures import ScriptLine


def tensor_to_serializable(obj: Any) -> Any:
    """Recursively convert objects to a JSON-serializable format."""
    if isinstance(obj, torch.Tensor):
        return obj.detach().cpu().tolist()
    if isinstance(obj, ScriptLine):
        return obj.model_dump()
    if isinstance(obj, dict):
        return {k: tensor_to_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [tensor_to_serializable(v) for v in obj]
    return obj


async def save_audio_file(
    audio: bytes,
    filename: str,
    sample_rate: int,
    num_channels: int,
    silence_threshold: float = 100.0,
) -> bool:
    """Save raw audio bytes to a WAV file, filtering out silent recordings.

    Args:
        audio: Raw PCM audio data as bytes.
        filename: Output WAV file path.
        sample_rate: Audio sample rate.
        num_channels: Number of channels in audio.
        silence_threshold: RMS amplitude threshold to detect silence.

    Returns:
        True if file was saved, False if silent or empty.
    """

    def _is_silent(audio_bytes: bytes, threshold: float) -> bool:
        """Return True if audio is silent based on RMS amplitude."""
        samples = struct.unpack(f"<{len(audio_bytes) // 2}h", audio_bytes)
        rms = math.sqrt(sum(s**2 for s in samples) / len(samples)) if samples else 0.0
        return rms < threshold

    def _encode_wav(audio_bytes: bytes) -> bytes:
        """Encode raw PCM bytes as WAV and return as byte buffer."""
        with io.BytesIO() as buffer:
            with wave.open(buffer, "wb") as wf:
                wf.setsampwidth(2)
                wf.setnchannels(num_channels)
                wf.setframerate(sample_rate)
                wf.writeframes(audio_bytes)
            return buffer.getvalue()

    if not audio:
        print("Cannot save empty audio.")
        return False

    loop = asyncio.get_event_loop()
    is_silent = await loop.run_in_executor(None, _is_silent, audio, silence_threshold)
    if is_silent:
        print(f"Audio is silent (RMS < {silence_threshold})")
        return False

    os.makedirs(os.path.dirname(filename), exist_ok=True)
    wav_bytes = await loop.run_in_executor(None, _encode_wav, audio)

    async with aiofiles.open(filename, "wb") as f:
        await f.write(wav_bytes)

    return True


def get_best_device() -> TorchDevice:
    """Select the best available torch device (CUDA > MPS > CPU).

    Returns:
        torch.device: Best available device.
    """
    if torch.cuda.is_available():
        return torch.device("cuda")
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")
