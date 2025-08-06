"""LipsyncProcessor for handling mouth animations based on the audio input."""

from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.frames.frames import (
    Frame,
    TTSStartedFrame,
    TTSStoppedFrame,
    TTSAudioRawFrame,
)
from pipecat.processors.frameworks.rtvi import RTVIServerMessageFrame
import torch
import torchaudio
import json
from huggingface_hub import hf_hub_download
import importlib.util
import sys
import os
from .utils import get_best_device
import asyncio
import time
import re


def predict_phonemes_from_waveform(
    waveform,
    extractor,
    windowing,
    token_to_phoneme,
    token_to_group,
    sample_rate=16000,
    device="cpu",
):
    """
    Predict phonemes from a waveform tensor using CUPE model.

    Returns:
        dict with keys:
            - phoneme_probabilities
            - phoneme_predictions
            - group_probabilities
            - group_predictions
            - phonemes_sequence
            - groups_sequence
            - phoneme_segments
            - model_info
    """
    window_size_ms = 120
    stride_ms = 80

    if waveform.ndim == 1:
        waveform = waveform.unsqueeze(0)
    if waveform.shape[0] > 1:
        waveform = waveform.mean(dim=0, keepdim=True)

    waveform = waveform.to(device)
    audio_batch = waveform.unsqueeze(0)  # [1, 1, time]

    windowed_audio = windowing.slice_windows(
        audio_batch, sample_rate, window_size_ms, stride_ms
    )

    batch_size, num_windows, window_size = windowed_audio.shape

    if num_windows == 0:
        return {
            "phoneme_probabilities": [],
            "phoneme_predictions": [],
            "group_probabilities": [],
            "group_predictions": [],
            "phonemes_sequence": [],
            "groups_sequence": [],
            "phoneme_segments": [],
            "model_info": {
                "sample_rate": sample_rate,
                "frames_per_second": 1000 / 16,
                "num_phoneme_classes": 0,
                "num_group_classes": 0,
            },
        }

    windows_flat = windowed_audio.reshape(-1, window_size)

    logits_phonemes, logits_groups = extractor.predict(
        windows_flat, return_embeddings=False, groups_only=False
    )

    frames_per_window = logits_phonemes.shape[1]
    logits_phonemes = logits_phonemes.reshape(
        batch_size, num_windows, frames_per_window, -1
    )
    logits_groups = logits_groups.reshape(
        batch_size, num_windows, frames_per_window, -1
    )

    phoneme_logits = windowing.stich_window_predictions(
        logits_phonemes,
        original_audio_length=audio_batch.size(2),
        cnn_output_size=frames_per_window,
        sample_rate=sample_rate,
        window_size_ms=window_size_ms,
        stride_ms=stride_ms,
    )
    group_logits = windowing.stich_window_predictions(
        logits_groups,
        original_audio_length=audio_batch.size(2),
        cnn_output_size=frames_per_window,
        sample_rate=sample_rate,
        window_size_ms=window_size_ms,
        stride_ms=stride_ms,
    )

    phoneme_probs = torch.softmax(phoneme_logits.squeeze(0), dim=-1)
    group_probs = torch.softmax(group_logits.squeeze(0), dim=-1)

    phoneme_preds = torch.argmax(phoneme_probs, dim=-1)
    group_preds = torch.argmax(group_probs, dim=-1)

    phonemes_sequence = [token_to_phoneme[int(p)] for p in phoneme_preds.cpu().numpy()]
    groups_sequence = [token_to_group[int(g)] for g in group_preds.cpu().numpy()]

    # Remove 'noise'
    valid_indices = [i for i, p in enumerate(phonemes_sequence) if p != "noise"]
    phoneme_preds = phoneme_preds[valid_indices]
    group_preds = group_preds[valid_indices]
    phoneme_probs = phoneme_probs[valid_indices]
    group_probs = group_probs[valid_indices]
    phonemes_sequence = [phonemes_sequence[i] for i in valid_indices]
    groups_sequence = [groups_sequence[i] for i in valid_indices]

    # Recover valid_indices from full prediction
    full_phoneme_ids = (
        torch.argmax(torch.softmax(phoneme_logits.squeeze(0), dim=-1), dim=-1)
        .cpu()
        .numpy()
    )
    full_phonemes = [token_to_phoneme[int(p)] for p in full_phoneme_ids]
    valid_indices = [i for i, p in enumerate(full_phonemes) if p != "noise"]
    phonemes_sequence = [full_phonemes[i] for i in valid_indices]

    # Build timestamped phoneme sequence using valid_indices
    frame_duration = 0.016  # 16ms per frame
    phoneme_segments = []
    if phonemes_sequence:
        current_phoneme = phonemes_sequence[0]
        start_idx = valid_indices[0]

        for i in range(1, len(phonemes_sequence)):
            current_idx = valid_indices[i]
            if phonemes_sequence[i] != current_phoneme:
                phoneme_segments.append(
                    {
                        "phoneme": current_phoneme,
                        "start": round(start_idx * frame_duration, 2),
                        "end": round(current_idx * frame_duration, 2),
                    }
                )
                current_phoneme = phonemes_sequence[i]
                start_idx = current_idx

        # Final segment
        phoneme_segments.append(
            {
                "phoneme": current_phoneme,
                "start": round(start_idx * frame_duration, 2),
                "end": round((valid_indices[-1] + 1) * frame_duration, 2),
            }
        )

    return {
        "phoneme_probabilities": phoneme_probs.cpu().numpy(),
        "phoneme_predictions": phoneme_preds.cpu().numpy(),
        "group_probabilities": group_probs.cpu().numpy(),
        "group_predictions": group_preds.cpu().numpy(),
        "phonemes_sequence": phonemes_sequence,
        "groups_sequence": groups_sequence,
        "phoneme_segments": phoneme_segments,
        "model_info": {
            "sample_rate": sample_rate,
            "frames_per_second": 1000 / 16,
            "num_phoneme_classes": phoneme_probs.shape[-1],
            "num_group_classes": group_probs.shape[-1],
        },
    }


def load_cupe_model(model_name="english", device="cpu"):
    model_files = {
        "english": "en_libri1000_uj01d_e199_val_GER=0.2307.ckpt",
        "multilingual-mls": "multi_MLS8_uh02_e36_val_GER=0.2334.ckpt",
        "multilingual-mswc": "multi_mswc38_ug20_e59_val_GER=0.5611.ckpt",
    }

    if model_name not in model_files:
        raise ValueError(
            f"Model {model_name} not available. Choose from: {list(model_files.keys())}"
        )

    repo_id = "Tabahi/CUPE-2i"

    # Download files from the Hub
    model_file = hf_hub_download(repo_id=repo_id, filename="model2i.py")
    windowing_file = hf_hub_download(repo_id=repo_id, filename="windowing.py")
    mapper_file = hf_hub_download(repo_id=repo_id, filename="mapper.py")
    model_utils_file = hf_hub_download(repo_id=repo_id, filename="model_utils.py")
    checkpoint_file = hf_hub_download(
        repo_id=repo_id, filename=f"ckpt/{model_files[model_name]}"
    )

    # Fix model2i.py (they have a bug with loading weights on CPU, I opened a PR to fix it)
    def patch_model_file(path, device):
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        patched_content = re.sub(
            r"torch\.load\(([^,]+),\s*weights_only=True\)",
            rf'torch.load(\1, map_location=torch.device("{device}"), weights_only=True)',
            content,
        )
        with open(path, "w", encoding="utf-8") as f:
            f.write(patched_content)

    patch_model_file(model_file, device)

    def import_module_from_file(module_name, file_path):
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module

    # Import modules
    _ = import_module_from_file("model_utils", model_utils_file)
    model2i = import_module_from_file("model2i", model_file)
    windowing = import_module_from_file("windowing", windowing_file)
    mapper = import_module_from_file("mapper", mapper_file)

    # Build mappings
    phoneme_to_token = mapper.phoneme_mapped_index
    token_to_phoneme = {v: k for k, v in phoneme_to_token.items()}
    group_to_token = mapper.phoneme_groups_index
    token_to_group = {v: k for k, v in group_to_token.items()}

    # Init extractor
    extractor = model2i.CUPEEmbeddingsExtractor(checkpoint_file, device=device)

    return extractor, windowing, token_to_phoneme, token_to_group


class LipsyncProcessor(FrameProcessor):
    """Processor for handling lipsync animations based on audio input."""

    PHONEME_VISEME_MAP_PATH = os.path.abspath("assets/phoneme_oculusviseme_map.json")
    MIN_DURATION_TO_PROCESS = 1.0  # seconds
    SAMPLE_RATE = 16000
    MIN_SAMPLES_TO_PROCESS = int(SAMPLE_RATE * MIN_DURATION_TO_PROCESS)

    def __init__(self):
        super().__init__()
        self.device = get_best_device(options=["cuda", "cpu"])
        self.audio_waveform_buffer = []  # list of waveform tensors
        self.resampler = None
        self.viseme_map = self._load_viseme_map()

        self.extractor, self.windowing, self.token_to_phoneme, self.token_to_group = (
            load_cupe_model(model_name="multilingual-mls", device=self.device)
        )
        self._warm_up()

    def _load_viseme_map(self):
        """Load the phoneme-viseme mapping from a JSON file."""
        with open(self.PHONEME_VISEME_MAP_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    def _warm_up(self):
        """Warm-up CUPE for reduced initial latency."""
        dummy_audio = torch.randn(16000).to(self.device)
        predict_phonemes_from_waveform(
            dummy_audio,
            self.extractor,
            self.windowing,
            self.token_to_phoneme,
            self.token_to_group,
            device=self.device,
        )
        # print("[LipsyncProcessor] Warm-up done.")

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, TTSStartedFrame):
            self._reset_buffers()

        elif isinstance(frame, TTSAudioRawFrame):
            await self._handle_audio_frame(frame, direction)
            return

        elif isinstance(frame, TTSStoppedFrame):
            await self._flush_remaining(direction)

        await self.push_frame(frame, direction)

    async def _handle_audio_frame(
        self, frame: TTSAudioRawFrame, direction: FrameDirection
    ):
        waveform = self._preprocess_audio(frame)
        self.audio_waveform_buffer.append(waveform)

        total_samples = sum(w.shape[-1] for w in self.audio_waveform_buffer)
        while total_samples >= self.MIN_SAMPLES_TO_PROCESS:
            full_waveform = torch.cat(self.audio_waveform_buffer, dim=-1)
            chunk = full_waveform[:, : self.MIN_SAMPLES_TO_PROCESS]
            remaining = full_waveform[:, self.MIN_SAMPLES_TO_PROCESS :]  # noqa: E203
            self.audio_waveform_buffer = [remaining] if remaining.numel() > 0 else []
            start = time.time()
            await self._run_lipsync(chunk.squeeze(0), direction)
            end = time.time()
            total_samples = remaining.shape[-1]

    async def _flush_remaining(self, direction: FrameDirection):
        if self.audio_waveform_buffer:
            full_waveform = torch.cat(self.audio_waveform_buffer, dim=-1)
            await self._run_lipsync(full_waveform.squeeze(0), direction)
        self._reset_buffers()

    def _reset_buffers(self):
        self.audio_waveform_buffer.clear()

    def _preprocess_audio(self, frame: TTSAudioRawFrame) -> torch.Tensor:
        waveform = (
            torch.frombuffer(frame.audio, dtype=torch.int16)
            .float()
            .div_(32768.0)
            .unsqueeze(0)
        )
        if frame.sample_rate != self.SAMPLE_RATE:
            if self.resampler is None:
                self.resampler = torchaudio.transforms.Resample(
                    orig_freq=frame.sample_rate, new_freq=self.SAMPLE_RATE
                ).to(self.device)
            waveform = self.resampler(waveform)
        return waveform.to(self.device)

    async def _run_lipsync(self, waveform: torch.Tensor, direction: FrameDirection):
        result = await asyncio.to_thread(
            predict_phonemes_from_waveform,
            waveform,
            self.extractor,
            self.windowing,
            self.token_to_phoneme,
            self.token_to_group,
            device=self.device,
        )
        # print("phonemes:", result["phoneme_segments"])
        viseme_events = self._phoneme_segments_to_viseme_events(
            result["phoneme_segments"]
        )
        if (
            viseme_events
            and "visemes" in viseme_events
            and len(viseme_events["visemes"]) > 0
        ):
            viseme_events["vdurations"][-1] = (
                waveform.shape[-1] / self.SAMPLE_RATE - viseme_events["vtimes"][-1]
            )
            viseme_events["duration"] = waveform.shape[-1] / self.SAMPLE_RATE
            # print("viseme_events:", viseme_events)
            await self.push_frame(
                RTVIServerMessageFrame(
                    data={"type": "visemes-event", "payload": viseme_events}
                ),
                direction,
            )

        # Send audio
        audio_int16 = (
            waveform.clamp(-1, 1).cpu() * 32768.0
        ).short()  # Convert to int16
        audio_bytes = (
            audio_int16.squeeze(0).numpy().tobytes()
        )  # Remove channel dim and convert

        await self.push_frame(
            TTSAudioRawFrame(
                audio=audio_bytes,
                sample_rate=self.SAMPLE_RATE,
                num_channels=1,
            ),
            direction,
        )

    def _phoneme_segments_to_viseme_events(self, phoneme_segments):
        """Map phonemes to visemes with durations and return structured arrays."""
        visemes = []
        vtimes = []
        vdurations = []

        for segment in phoneme_segments:
            phoneme = segment["phoneme"].lower()
            viseme_id = self.viseme_map.get(phoneme, [None])[
                -1
            ]  # Default to neutral viseme "sil"
            start = segment["start"] * 1000
            end = segment["end"] * 1000
            duration = end - start

            if viseme_id is None or duration <= 0:
                continue

            visemes.append(viseme_id)
            vtimes.append(start)
            vdurations.append(duration)

        return {
            "visemes": visemes,
            "vtimes": vtimes,
            "vdurations": vdurations,
        }
