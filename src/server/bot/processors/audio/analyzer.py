"""This module provides the AudioAnalyzer class for analyzing audio files."""

import os
import json
import asyncio
import traceback
from typing import Any, Dict

from senselab.audio.data_structures import Audio
from senselab.audio.tasks.preprocessing import downmix_audios_to_mono, resample_audios
from senselab.audio.tasks.features_extraction.api import extract_features_from_audios
from senselab.audio.tasks.speech_to_text import transcribe_audios
from senselab.audio.tasks.speaker_embeddings import (
    extract_speaker_embeddings_from_audios,
)
from senselab.utils.data_structures import HFModel, SpeechBrainModel

from .serialization import tensor_to_serializable


class AudioAnalyzer:
    """Performs full audio analysis including preprocessing, feature extraction,
    transcription, and speaker embedding extraction. Saves results to JSON."""

    @staticmethod
    async def analyze_audio(audiofile: str) -> None:
        """Analyze a .wav file and save features, transcript, and embeddings to a JSON file.

        Args:
            audiofile: Path to the .wav file to analyze.
        """
        print(f"[AudioAnalyzer] Analyzing audio file: {audiofile}")
        abs_audiofile = os.path.abspath(audiofile)
        if not os.path.exists(abs_audiofile):
            print(f"[AudioAnalyzer] File does not exist: {abs_audiofile}")
            return

        abs_json_file = abs_audiofile.replace(".wav", ".json").replace(
            "/audios/", "/json/"
        )

        if os.path.exists(abs_json_file):
            print(f"[AudioAnalyzer] Output already exists: {abs_json_file}")
            return

        def _trace(e: BaseException) -> str:
            return "".join(traceback.format_exception(type(e), e, e.__traceback__))

        def analyze_blocking():
            errors: Dict[str, str] = {}
            result: Dict[str, Any] = {
                "audio_file": audiofile,
                "features": None,
                "transcript": None,
                "speaker_embeddings": None,
                "errors": {},  # filled only for failing stages
            }

            # -------- Load audio container --------
            try:
                audio = Audio(filepath=abs_audiofile)
                audios = [audio]
            except Exception as e:
                errors["load_audio"] = _trace(e)
                result["errors"] = errors
                print(
                    "[AudioAnalyzer] Failed to load audio; nothing to do. Not saving JSON."
                )
                return  # cannot proceed if we can't load

            # -------- Preprocessing (best-effort; fall back to raw) --------
            resampled = audios
            try:
                downmixed = downmix_audios_to_mono(audios)
                resampled = resample_audios(downmixed, resample_rate=16000)
            except Exception as e:
                errors["preprocessing"] = _trace(e)
                print(
                    "[AudioAnalyzer] Preprocessing failed, falling back to raw audio for downstream steps."
                )

            # -------- Feature extraction (best-effort) --------
            try:
                feats = extract_features_from_audios(
                    audios=resampled,
                    opensmile=True,
                    parselmouth=True,
                    torchaudio=False,
                    torchaudio_squim=True,
                )[0]
                result["features"] = tensor_to_serializable(feats)
            except Exception as e:
                errors["feature_extraction"] = _trace(e)
                print("[AudioAnalyzer] Feature extraction failed.")

            # -------- Transcription (best-effort) --------
            try:
                asr_model = HFModel(
                    path_or_uri=os.getenv(
                        "ASR_POST_SESSION_ANALYSIS_MODEL", "openai/whisper-tiny"
                    ),
                    revision="main",
                )
                try:
                    transcript = transcribe_audios(resampled, model=asr_model)[0]
                    result["transcript"] = tensor_to_serializable(transcript)
                except Exception as e_tr:
                    errors["transcription"] = _trace(e_tr)
                    print("[AudioAnalyzer] Transcription failed.")
            except Exception as e_model:
                errors["transcription_model_init"] = _trace(e_model)
                print("[AudioAnalyzer] ASR model init failed.")

            # -------- Speaker embeddings (best-effort) --------
            try:
                speaker_model = SpeechBrainModel(
                    path_or_uri="speechbrain/spkrec-ecapa-voxceleb", revision="main"
                )
                try:
                    emb = extract_speaker_embeddings_from_audios(
                        resampled, speaker_model
                    )[0]
                    result["speaker_embeddings"] = tensor_to_serializable(emb)
                except Exception as e_emb:
                    errors["speaker_embedding_extraction"] = _trace(e_emb)
                    print("[AudioAnalyzer] Speaker embedding extraction failed.")
            except Exception as e_spk_model:
                errors["speaker_model_init"] = _trace(e_spk_model)
                print("[AudioAnalyzer] Speaker model init failed.")

            # -------- Save JSON if any stage succeeded --------
            succeeded = any(
                result[key] is not None
                for key in ("features", "transcript", "speaker_embeddings")
            )

            # Only include errors key if there are errors
            if errors:
                result["errors"] = errors
            else:
                # keep schema tidy if no errors happened
                result.pop("errors", None)

            if succeeded:
                os.makedirs(os.path.dirname(abs_json_file), exist_ok=True)
                with open(abs_json_file, "w", encoding="utf-8") as f:
                    json.dump(result, f, indent=2)
                print(f"[AudioAnalyzer] Saved analysis to: {abs_json_file}")
            else:
                print("[AudioAnalyzer] All analysis steps failed. Not saving JSON.")

        await asyncio.to_thread(analyze_blocking)
