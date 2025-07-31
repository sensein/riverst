"""This module provides the AudioAnalyzer class for analyzing audio files."""

import os
import json
import asyncio

from senselab.audio.data_structures import Audio
from senselab.audio.tasks.preprocessing import downmix_audios_to_mono, resample_audios
from senselab.audio.tasks.features_extraction.api import extract_features_from_audios
from senselab.audio.tasks.speech_to_text import transcribe_audios
from senselab.audio.tasks.speaker_embeddings import (
    extract_speaker_embeddings_from_audios,
)
from senselab.utils.data_structures import HFModel, SpeechBrainModel

from .utils import tensor_to_serializable


class AudioAnalyzer:
    """Performs full audio analysis including preprocessing, feature extraction,
    transcription, and speaker embedding extraction. Saves results to JSON."""

    @staticmethod
    async def analyze_audio(audiofile: str) -> None:
        """Analyze a .wav file and save features, transcript, and embeddings to a JSON file.

        Args:
            audiofile: Path to the .wav file to analyze.
        """
        print(f"Analyzing audio file: {audiofile}")
        abs_audiofile = os.path.abspath(audiofile)
        if not os.path.exists(abs_audiofile):
            print(f"File does not exist: {abs_audiofile}")
            return

        abs_json_file = abs_audiofile.replace(".wav", ".json").replace(
            "/audios/", "/json/"
        )

        if os.path.exists(abs_json_file):
            print(f"File already exists: {abs_json_file}")
            return

        def analyze_blocking():
            audio = Audio(filepath=abs_audiofile)
            audios = [audio]

            # Preprocess
            downmixed = downmix_audios_to_mono(audios)
            resampled = resample_audios(downmixed, resample_rate=16000)

            # Feature extraction
            features = extract_features_from_audios(
                audios=resampled,
                opensmile=True,
                parselmouth=True,
                torchaudio=False,
                torchaudio_squim=True,
            )[0]

            # Transcription
            asr_model = HFModel(path_or_uri="openai/whisper-large-v3-turbo", revision="main")
            transcript = transcribe_audios(resampled, model=asr_model)[0]

            # Speaker embedding
            speaker_model = SpeechBrainModel(
                path_or_uri="speechbrain/spkrec-ecapa-voxceleb", revision="main"
            )
            embeddings = extract_speaker_embeddings_from_audios(
                resampled, speaker_model
            )[0]

            # Save to JSON
            result = {
                "audio_file": audiofile,
                "features": tensor_to_serializable(features),
                "transcript": tensor_to_serializable(transcript),
                "speaker_embeddings": tensor_to_serializable(embeddings),
            }

            os.makedirs(os.path.dirname(abs_json_file), exist_ok=True)
            with open(abs_json_file, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2)

            print(f"Saved features to: {abs_json_file}")

        await asyncio.to_thread(analyze_blocking)
