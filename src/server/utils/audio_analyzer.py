from senselab.audio.data_structures import Audio
from senselab.audio.tasks.features_extraction.api import extract_features_from_audios
from senselab.audio.tasks.preprocessing import downmix_audios_to_mono, resample_audios
from senselab.utils.data_structures import HFModel, SpeechBrainModel
from senselab.audio.tasks.speech_to_text import transcribe_audios
from senselab.audio.tasks.speaker_embeddings import extract_speaker_embeddings_from_audios

import os
import json
import asyncio
from .utils import tensor_to_serializable


class AudioAnalyzer:

    @staticmethod
    async def analyze_audio(audiofile: str) -> None:
        print(f"Analyzing audio file: {audiofile}")
        abs_audiofile = os.path.abspath(audiofile)
        abs_json_file = abs_audiofile.replace(".wav", ".json").replace("/audios/", "/json/")
        # print("Saving features to:", abs_json_file)
        os.makedirs(os.path.dirname(abs_json_file), exist_ok=True)
        if os.path.exists(abs_json_file):
            print(f"File already exists: {abs_json_file}")
            return

        def blocking():
            audio = Audio(filepath=abs_audiofile)
            audios = [audio]
            downmixed = downmix_audios_to_mono(audios)
            resampled = resample_audios(downmixed, 16000)
            features = extract_features_from_audios(
                audios=resampled,
                opensmile=True,
                parselmouth=True,
                torchaudio=False,
                torchaudio_squim=True
            )[0]
            # print(f"Extracted features from {abs_audiofile}:", features)
            model = HFModel(path_or_uri="openai/whisper-tiny", revision="main")
            transcript = transcribe_audios(audios=resampled, model=model)[0]

            model = SpeechBrainModel(path_or_uri="speechbrain/spkrec-ecapa-voxceleb", revision="main")
            embeddings = extract_speaker_embeddings_from_audios(resampled, model)[0]
            data = {
                "audio_file": audiofile,
                "features": tensor_to_serializable(features),
                "transcript": tensor_to_serializable(transcript),
                "speaker_embeddings": tensor_to_serializable(embeddings),
            }
            with open(abs_json_file, "w") as f:
                json.dump(data, f, indent=2)
            print("Saved features to:", abs_json_file)

        await asyncio.to_thread(blocking)
