import types
import torch
import torchaudio
import numpy as np
from pipecat.processors.audio.audio_buffer_processor import AudioBufferProcessor


class AudioResamplingHelper:
    """Helper class for audio resampling operations using torchaudio."""

    @staticmethod
    async def _torchaudio_resample(processor, frame, kind="output"):
        """Helper function to resample audio using torchaudio.

        It takes an audio frame and resamples it to the desired sample rate.
        This is needed because the original function in AudioBufferProcessor
        (based on SOXRAudioResampler) doesn't seem to work as expected.

        Args:
            processor: The AudioBufferProcessor instance
            frame: Audio frame to resample
            kind: Type of resampling ("input" or "output")

        Returns:
            bytes: Resampled audio data as bytes
        """
        orig_sr = frame.sample_rate
        target_sr = processor._sample_rate

        if orig_sr == target_sr:
            return frame.audio

        audio_tensor = (
            torch.tensor(np.frombuffer(frame.audio, dtype=np.int16).copy()).float()
            / 32768.0
        )
        audio_tensor = audio_tensor.unsqueeze(0)  # shape: (1, N)

        resampled = torchaudio.transforms.Resample(orig_sr, target_sr)(audio_tensor)
        resampled_bytes = (
            (resampled.squeeze(0) * 32768.0)
            .clamp(-32768, 32767)
            .short()
            .numpy()
            .tobytes()
        )
        return resampled_bytes

    @staticmethod
    async def _resample_input_audio(processor, frame):
        """Wrapper for input audio resampling."""
        return await AudioResamplingHelper._torchaudio_resample(
            processor, frame, kind="input"
        )

    @staticmethod
    async def _resample_output_audio(processor, frame):
        """Wrapper for output audio resampling."""
        return await AudioResamplingHelper._torchaudio_resample(
            processor, frame, kind="output"
        )

    @staticmethod
    def configure_audio_buffer_processor(
        sample_rate=16000, num_channels=1, enable_turn_audio=True
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

        # Dynamically bind the resampling methods to the instance
        audiobuffer._resample_input_audio = types.MethodType(
            AudioResamplingHelper._resample_input_audio, audiobuffer
        )
        audiobuffer._resample_output_audio = types.MethodType(
            AudioResamplingHelper._resample_output_audio, audiobuffer
        )

        return audiobuffer
