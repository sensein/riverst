import numpy as np
import torch
from transformers import pipeline as transformers_pipeline
import json
import asyncio
from .utils import get_best_device

class VisemeProcessor:
    PHONEME_VISEME_MAP_PATH = "assets/phoneme_viseme_map.json"

    def __init__(self, model_name: str = "bookbot/wav2vec2-ljspeech-gruut"):
        """
        Initializes the VisemeProcessor.

        Args:
            model_name (str): Hugging Face model identifier for phonetic ASR.

        # TODO: find a faster way to obtain the phonemes
        """
        self.model_name = model_name
        self.phoneme_viseme_map = self._load_viseme_map()
        self.device = get_best_device()
        self._warm_up()

    def _load_viseme_map(self):
        """Load the phoneme-viseme mapping from a JSON file."""
        with open(self.PHONEME_VISEME_MAP_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    def _warm_up(self):
        """Load and warm up the ASR pipeline."""
        self.asr_pipeline = transformers_pipeline(
            "automatic-speech-recognition",
            model=self.model_name,
            device=self.device,
            torch_dtype=torch.float16
        )
        dummy_audio = np.random.rand(16000).astype(np.int16) * 2 - 1
        _ = self.asr_pipeline(dummy_audio)

    def _clean_visemes(self, viseme_durations, silence_viseme=0, silence_threshold=0.2, non_silence_threshold=0.05):
        cleaned = []
        for current in viseme_durations:
            viseme = current["visemes"][0]
            duration = current["duration"]

            if viseme == silence_viseme and duration <= silence_threshold and cleaned:
                cleaned[-1]["duration"] += duration
            else:
                cleaned.append(current)

        final = []
        i = 0
        while i < len(cleaned):
            current = cleaned[i]
            viseme = current["visemes"][0]
            duration = current["duration"]

            if viseme != silence_viseme and duration <= non_silence_threshold:
                if final:
                    final[-1]["duration"] += duration
                elif i + 1 < len(cleaned):
                    cleaned[i + 1]["duration"] += duration
                else:
                    final.append(current)
            else:
                final.append(current)
            i += 1

        return final

    def process(self, audio_bytes: bytes, sample_rate: int, num_channels: int):
        """
        Process audio bytes into viseme durations.

        Args:
            audio_bytes (bytes): Raw audio data.
            sample_rate (int): Sample rate of the audio.
            num_channels (int): Number of audio channels.

        Returns:
            list: Cleaned viseme duration data.
        """
        try:
            waveform = np.frombuffer(audio_bytes, dtype=np.int16)

            with torch.inference_mode():
                phonemes = self.asr_pipeline(waveform.squeeze(), return_timestamps="char")

            viseme_durations = [
                {
                    "visemes": self.phoneme_viseme_map.get(chunk["text"], []),
                    "duration": round(chunk["timestamp"][1] - chunk["timestamp"][0], 2)
                }
                for chunk in phonemes["chunks"]
            ]

            return self._clean_visemes(viseme_durations)
        except Exception as e:
            print(f"Error processing audio: {e}")
            return None

    async def process_async(self, audio_bytes, sample_rate, num_channels):
        """Asynchronously process audio bytes into viseme durations."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.process(audio_bytes, sample_rate, num_channels)
        )
