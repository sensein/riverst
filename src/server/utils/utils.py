"""This module contains various utility functions."""
import os
import io
import wave
import asyncio
import aiofiles
from typing import Any
import torch
from torch import device as TorchDevice
import struct
import math


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
    num_channels: int,
    silence_threshold: float = 100.0  # RMS threshold for silence detection
) -> None:
    """Asynchronously save raw audio bytes to a WAV file, checking for silence.

    This function:
      1. Checks for empty audio data
      2. Checks for silent audio (below RMS threshold)
      3. Ensures target directory exists
      4. Encodes bytes to WAV format in background thread
      5. Writes to disk asynchronously

    Args:
        audio: Raw PCM audio data as bytes
        filename: Full path for output WAV file
        sample_rate: Sampling rate in Hz
        num_channels: Number of audio channels
        silence_threshold: Maximum RMS value considered silent

    Raises:
        ValueError: If audio is empty or silent
        OSError: If directory creation or file writing fails
    """
    def _is_silent(audio_bytes: bytes, threshold: float) -> bool:
        """Check if audio is silent by calculating RMS amplitude."""
        # Convert bytes to 16-bit samples
        samples = struct.unpack(f'<{len(audio_bytes)//2}h', audio_bytes)
        
        # Calculate RMS (root mean square) amplitude
        sum_squares = sum(s**2 for s in samples)
        rms = math.sqrt(sum_squares / len(samples)) if samples else 0        
        return rms < threshold

    def _encode_wav(audio: bytes, num_channels: int, sample_rate: int) -> bytes:
        """Encode raw PCM bytes to WAV format."""
        with io.BytesIO() as buffer:
            with wave.open(buffer, "wb") as wf:
                wf.setsampwidth(2)
                wf.setnchannels(num_channels)
                wf.setframerate(sample_rate)
                wf.writeframes(audio)
            return buffer.getvalue()

    # Check for empty audio
    if not audio:
        print("Cannot save empty audio.")
        return False

    # Check for silence in background thread
    loop = asyncio.get_event_loop()
    is_silent = await loop.run_in_executor(None, _is_silent, audio, silence_threshold)
    
    if is_silent:
        print(f"Audio is silent (RMS < {silence_threshold})")
        return False

    # Ensure output directory exists
    os.makedirs(os.path.dirname(filename), exist_ok=True)

    # Encode and save
    wav_bytes = await loop.run_in_executor(None, _encode_wav, audio, num_channels, sample_rate)
    async with aiofiles.open(filename, "wb") as f:
        await f.write(wav_bytes)
    return True
    

def get_best_device() -> TorchDevice:
    """Returns the "best" available torch device according to the following strategy:
    
    1. Use CUDA if available.
    2. If not, use MPS (Metal Performance Shaders) if available.
    3. Otherwise, fall back to CPU.
    
    Returns:
        torch.device: The best available torch device ('cuda', 'mps', or 'cpu').
    """
    if torch.cuda.is_available():
        return torch.device("cuda")
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")
    else:
        return torch.device("cpu")
