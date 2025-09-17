import types
import torch
import torchaudio
import numpy as np
from functools import lru_cache
from loguru import logger
from pipecat.processors.audio.audio_buffer_processor import AudioBufferProcessor
from bot.utils.device_utils import get_best_device

SAMPLING_RATE = 16000
NUM_CHANNELS = 1


class AudioResamplingHelper:
    """Helper class for audio resampling operations using torchaudio."""

    _device_cache = None

    @staticmethod
    @lru_cache(maxsize=32)
    def _get_cached_resampler(orig_sr: int, target_sr: int, device: str = "cpu"):
        """Get a cached resampler for the given sample rate conversion.

        Args:
            orig_sr: Original sample rate
            target_sr: Target sample rate
            device: Target device for the resampler ('cpu', 'cuda', 'mps')

        Returns:
            torchaudio.transforms.Resample: Cached resampler instance on target device
        """
        resampler = torchaudio.transforms.Resample(orig_sr, target_sr)
        return resampler.to(device)

    @staticmethod
    async def _torchaudio_resample(processor, frame):
        """Helper function to resample audio using torchaudio with GPU acceleration.

        It takes an audio frame and resamples it to the desired sample rate.
        This is needed because the original function in AudioBufferProcessor
        (based on SOXRAudioResampler) doesn't seem to work as expected.

        Args:
            processor: The AudioBufferProcessor instance
            frame: Audio frame to resample

        Returns:
            bytes: Resampled audio data as bytes
        """
        orig_sr = frame.sample_rate
        target_sr = processor._sample_rate

        if orig_sr == target_sr:
            return frame.audio

        # Get the best available device for processing (cached)
        if AudioResamplingHelper._device_cache is None:
            AudioResamplingHelper._device_cache = str(
                get_best_device(options=["mps", "cuda", "cpu"])
            )
        device = AudioResamplingHelper._device_cache

        # Convert audio to tensor on the target device
        try:
            audio_array = np.frombuffer(frame.audio, dtype=np.int16)
            audio_tensor = torch.tensor(audio_array, device=device).float() / 32768.0
        except Exception as e:
            logger.critical(f"Failed to create audio tensor on device {device}: {e}")
            # Fallback to CPU processing on device error
            device = "cpu"
            audio_array = np.frombuffer(frame.audio, dtype=np.int16)
            audio_tensor = torch.tensor(audio_array, device=device).float() / 32768.0
        audio_tensor = audio_tensor.unsqueeze(0)  # shape: (1, N)

        # Use cached device-aware resampler
        try:
            resampler = AudioResamplingHelper._get_cached_resampler(
                orig_sr, target_sr, device
            )
            resampled = resampler(audio_tensor)

            # Convert back to bytes (optimize for device type)
            if device == "cpu":
                # Already on CPU, no need for .cpu() call
                resampled_bytes = (
                    (resampled.squeeze(0) * 32768.0)
                    .clamp(-32768, 32767)
                    .short()
                    .numpy()
                    .tobytes()
                )
            else:
                # Move to CPU for numpy operations
                resampled_bytes = (
                    (resampled.squeeze(0) * 32768.0)
                    .clamp(-32768, 32767)
                    .short()
                    .cpu()
                    .numpy()
                    .tobytes()
                )
        except Exception as e:
            logger.critical(e)
            return frame.audio
        return resampled_bytes

    @staticmethod
    async def _resample_audio(processor, frame):
        """Wrapper for input audio resampling."""
        return await AudioResamplingHelper._torchaudio_resample(processor, frame)

    @staticmethod
    def configure_audio_buffer_processor(
        sample_rate=SAMPLING_RATE, num_channels=NUM_CHANNELS, enable_turn_audio=True
    ):
        """Create and configure an AudioBufferProcessor with custom resampling methods.

        Args:
            sample_rate: Target sample rate for audio processing
            num_channels: Number of audio channels
            enable_turn_audio: Whether to enable turn-based audio processing

        Returns:
            AudioBufferProcessor: Configured processor instance
        """
        audiobuffer = AudioBufferProcessor(
            sample_rate=sample_rate,
            num_channels=num_channels,
            enable_turn_audio=enable_turn_audio,
        )

        audiobuffer._resample_audio = types.MethodType(
            AudioResamplingHelper._resample_audio, audiobuffer
        )

        return audiobuffer

    @staticmethod
    def clear_resampler_cache():
        """Clear the resampler cache. Useful for memory management."""
        AudioResamplingHelper._get_cached_resampler.cache_clear()
        AudioResamplingHelper._device_cache = None

    @staticmethod
    def get_cache_info():
        """Get cache statistics for debugging/monitoring."""
        return AudioResamplingHelper._get_cached_resampler.cache_info()
