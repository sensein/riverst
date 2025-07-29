#
# Kokoro TTS service for Pipecat
#

import asyncio
import concurrent.futures
from typing import AsyncGenerator, Optional

import numpy as np
from loguru import logger

import torch
from kokoro import KPipeline

from pipecat.frames.frames import (
    ErrorFrame,
    Frame,
    TTSAudioRawFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
)
from pipecat.services.tts_service import TTSService
from pipecat.utils.tracing.service_decorators import traced_tts


class KokoroTTSService(TTSService):
    """Kokoro TTS service implementation.

    Provides text-to-speech synthesis using Kokoro models running locally.
    """

    def __init__(
        self,
        *,
        voice: str = "af_heart",
        device: Optional[str] = None,
        sample_rate: int = 24000,
        max_workers: int = 1,
        **kwargs,
    ):
        """Initialize the Kokoro TTS service.

        Args:
            voice: The voice to use for synthesis (default: "af_heart").
            device: The device to run on (None for default device).
            sample_rate: Output sample rate (default: 24000).
            max_workers: Number of threads for audio generation (default: 1).
            **kwargs: Additional arguments passed to the parent TTSService.
        """
        super().__init__(sample_rate=sample_rate, **kwargs)

        self._voice = voice
        self._device = device
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)

        # Initialize model in a separate thread to avoid blocking
        self._model = None
        self._initialize_model()

    def _initialize_model(self):
        """Initialize the Kokoro model. This runs in a separate thread."""
        try:
            logger.debug("Loading Kokoro model (prince-canuma/Kokoro-82M)")
            self._model = KPipeline(lang_code="a")
            logger.debug("Kokoro model loaded successfully")
            _ = self._model("Example text", voice=self._voice)
            logger.debug("Kokoro model initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Kokoro model: {e}")
            raise

    def can_generate_metrics(self) -> bool:
        return True

    def _generate_audio_sync(self, text: str) -> bytes:
        """Generate audio synchronously using the model."""
        try:
            if not text.strip():
                raise ValueError("Empty input text provided to TTS")

            logger.debug(f"Generating audio for: {text[:50]}...")  # Log snippet only

            audio_segments = []

            for idx, (_1, _2, audio) in enumerate(self._model(text, voice=self._voice)):
                if isinstance(audio, torch.Tensor):
                    if audio.device.type == "meta":
                        raise RuntimeError(
                            "Received audio tensor on meta device. Model likely not fully initialized."
                        )
                else:
                    try:
                        audio = torch.from_numpy(audio)
                    except Exception as e:
                        logger.warning(
                            f"Failed to convert audio segment {idx} to torch.Tensor: {e}"
                        )
                        continue

                if audio.numel() > 0:
                    audio_segments.append(audio)
                else:
                    logger.warning(f"Skipped empty audio tensor at index {idx}")

            if not audio_segments:
                raise ValueError("No valid audio segments returned by Kokoro")

            audio_array = (
                audio_segments[0]
                if len(audio_segments) == 1
                else torch.cat(audio_segments, dim=0)
            )
            audio_np = audio_array.numpy()
            audio_int16 = (audio_np * 32767).astype(np.int16)
            return audio_int16.tobytes()

        except Exception as e:
            logger.error(f"Error generating audio: {e}")
            raise

    @traced_tts
    async def run_tts(self, text: str) -> AsyncGenerator[Frame, None]:
        """Generate speech from text using Kokoro.

        Args:
            text: The text to convert to speech.

        Yields:
            Frame: Audio frames containing the synthesized speech and status frames.
        """
        logger.debug(f"{self}: Generating TTS [{text}]")

        try:
            await self.start_ttfb_metrics()
            await self.start_tts_usage_metrics(text)

            yield TTSStartedFrame()

            # Run audio generation in executor (separate thread) to avoid blocking
            loop = asyncio.get_event_loop()
            audio_bytes = await loop.run_in_executor(
                self._executor, self._generate_audio_sync, text
            )

            # Chunk the audio data for streaming
            CHUNK_SIZE = self.chunk_size

            await self.stop_ttfb_metrics()

            # Stream the audio in chunks
            for i in range(0, len(audio_bytes), CHUNK_SIZE):
                chunk = audio_bytes[i : i + CHUNK_SIZE]  # noqa: E203
                if len(chunk) > 0:
                    yield TTSAudioRawFrame(chunk, self.sample_rate, 1)
                    await asyncio.sleep(0.001)  # Prevent buffer overrun

        except Exception as e:
            logger.error(f"Error in run_tts: {e}")
            yield ErrorFrame(error=str(e))
        finally:
            logger.debug(f"{self}: Finished TTS [{text}]")
            await self.stop_ttfb_metrics()
            yield TTSStoppedFrame()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        self._executor.shutdown(wait=True)
        await super().__aexit__(exc_type, exc_val, exc_tb)
