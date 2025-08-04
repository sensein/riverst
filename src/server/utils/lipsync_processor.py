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
from transformers import pipeline as transformers_pipeline
from .utils import get_best_device
import numpy as np
import json
import os
from dataclasses import dataclass
import string
from faster_whisper import WhisperModel


class LipsyncProcessor(FrameProcessor):
    """Processor for handling lipsync animations based on audio input."""

    PHONEME_VISEME_MAP_PATH = os.path.abspath("assets/phoneme_oculusviseme_map.json")

    def __init__(self, strategy="timestamped_asr"):
        super().__init__()
        self.audio_buffer = []
        self.is_buffering = False
        self.strategy = strategy
        self.device = get_best_device()
        self.forced_alignment_flag = (
            False  # Set to True if you want to use forced alignment
        )
        if self.strategy == "timestamped_asr":
            if str(self.device) == "mps":
                self.asr_pipeline = transformers_pipeline(
                    "automatic-speech-recognition",
                    model="openai/whisper-tiny",
                    device=self.device,
                    torch_dtype=torch.float16,
                )
            else:
                self.asr_model = WhisperModel(
                    "tiny",
                    device=str(self.device),
                    compute_type="float16" if str(self.device) == "cuda" else "int8",
                )
            if self.forced_alignment_flag:
                bundle = torchaudio.pipelines.WAV2VEC2_ASR_BASE_960H
                self.labels = bundle.get_labels()
                self.model = bundle.get_model().to(self.device)
                self.dictionary = {c: i for i, c in enumerate(self.labels)}
        elif self.strategy == "timestamped_phoneme_recognition":
            self.asr_pipeline = transformers_pipeline(
                "automatic-speech-recognition",
                model="bookbot/wav2vec2-ljspeech-gruut",
                device=self.device,
                torch_dtype=torch.float16,
            )
            self.phoneme_viseme_map = self._load_viseme_map()
        else:
            raise ValueError(f"Unknown strategy: {self.strategy}")
        self._warm_up()

    def _load_viseme_map(self):
        """Load the phoneme-viseme mapping from a JSON file."""
        with open(self.PHONEME_VISEME_MAP_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    def _warm_up(self):
        """Load and warm up the ASR pipeline."""
        dummy_audio = np.random.rand(16000).astype(np.int16) * 2 - 1
        if self.strategy == "timestamped_asr":
            if str(self.device) == "mps":
                self.asr_pipeline(dummy_audio)
            else:
                self.asr_model.transcribe(
                    dummy_audio,
                    word_timestamps=True,
                    beam_size=1,
                    temperature=[0.0],
                    suppress_tokens=[],
                    condition_on_previous_text=False,
                    vad_filter=False,
                )
        else:
            self.asr_pipeline(dummy_audio)
        print("_warm_up done")

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        """Process incoming frames, handling TTS audio buffering and ASR."""
        await super().process_frame(frame, direction)

        if isinstance(frame, TTSStartedFrame):
            self.is_buffering = True
            self.audio_buffer.clear()
            return  # do not push immediately

        elif isinstance(frame, TTSAudioRawFrame) and self.is_buffering:
            self.audio_buffer.append(frame)
            return  # do not push immediately

        elif isinstance(frame, TTSStoppedFrame) and self.is_buffering:
            self.is_buffering = False

            # 1. Pre-allocate a buffer and concatenate bytes first
            raw_audio_bytes = b"".join(frame.audio for frame in self.audio_buffer)

            # 2. Convert all at once to int16 tensor
            audio_tensor = torch.frombuffer(raw_audio_bytes, dtype=torch.int16)

            # 3. Normalize to float32 in one go
            audio_tensor = audio_tensor.to(torch.float32).div_(32768.0)

            # 4. Reshape to (1, N)
            audio_tensor = audio_tensor.unsqueeze(0)

            # 5. Conditional resampling only if needed
            sample_rate = self.audio_buffer[0].sample_rate
            if sample_rate != 16000:
                resampler = torchaudio.transforms.Resample(
                    orig_freq=sample_rate, new_freq=16000
                )
                audio_tensor = resampler(audio_tensor)

            # 6. Duration in seconds
            audio_duration_sec = audio_tensor.shape[1] / 16000.0

            # 7. Only convert to numpy if absolutely needed
            audio_data = audio_tensor.squeeze(0).numpy()
            if self.strategy == "timestamped_asr":
                # Note: Unfortunately, the timestamps returned by the ASR pipeline are not always accurate.
                # For this reason, we explored forced alignment to get precise(r-ish) word timings.
                # However, this takes a lot of time and memory, so it's not ideal anyway.
                if self.forced_alignment_flag:
                    transcript = self.asr_pipeline(audio_data)
                    formatted_output = self._run_forced_alignment(
                        audio_data, transcript["text"]
                    )
                else:
                    if str(self.device) == "mps":
                        prediction = self.asr_pipeline(
                            audio_data, return_timestamps="word"
                        )
                        formatted_output = self._format_prediction(
                            prediction, audio_duration_sec
                        )
                    else:
                        segments, _ = self.asr_model.transcribe(
                            audio_data,
                            word_timestamps=True,
                            beam_size=1,
                            temperature=[0.0],
                            suppress_tokens=[],
                            condition_on_previous_text=False,
                            vad_filter=False,
                        )
                        formatted_output = self._format_faster_whisper_segments(
                            segments, audio_duration_sec
                        )

            elif self.strategy == "timestamped_phoneme_recognition":
                # Handle phoneme-based ASR output
                prediction = self.asr_pipeline(audio_data, return_timestamps="char")
                formatted_output = self._format_phoneme_chunks(
                    prediction["chunks"], audio_duration_sec
                )
            else:
                raise ValueError(f"Unknown strategy: {self.strategy}")

            output_frame = RTVIServerMessageFrame(
                data={"type": "visemes-event", "payload": formatted_output}
            )

            # Emit RTVIServerMessageFrame before the buffered audio
            await self.push_frame(output_frame, direction)
            # Emit the TTSStartedFrame, then buffered audio, then TTSStoppedFrame
            started_frame = TTSStartedFrame()
            await self.push_frame(started_frame, direction)

            for audio_frame in self.audio_buffer:
                await self.push_frame(audio_frame, direction)

            await self.push_frame(frame, direction)

            self.audio_buffer.clear()
            return  # already emitted all frames

        # Default case (non-TTS frames or TTS frames outside buffering state)
        await self.push_frame(frame, direction)

    def _format_prediction(self, prediction: dict, audio_duration_sec: float) -> dict:
        words = []
        wtimes = []
        wdurations = []

        for chunk in prediction["chunks"]:
            word = chunk["text"]
            start = chunk["timestamp"][0]
            end = chunk["timestamp"][1]

            # If the end is None, use the total duration
            if end is None:
                end = audio_duration_sec

            words.append(word)
            wtimes.append(int(start * 1000))  # convert to ms
            wdurations.append(int((end - start) * 1000))  # convert to ms

        return {
            "words": words,
            "wtimes": wtimes,
            "wdurations": wdurations,
            "duration": float(audio_duration_sec),  # total duration in s
        }

    def _format_faster_whisper_segments(
        self, segments, audio_duration_sec: float
    ) -> dict:
        words = []
        wtimes = []
        wdurations = []

        for segment in segments:
            if not segment.words:
                continue
            for word in segment.words:
                words.append(word.word)
                wtimes.append(int(word.start * 1000))
                end_time = word.end if word.end is not None else audio_duration_sec
                wdurations.append(int((end_time - word.start) * 1000))

        return {
            "words": words,
            "wtimes": wtimes,
            "wdurations": wdurations,
            "duration": float(audio_duration_sec),
        }

    def _format_phoneme_chunks(self, chunks: list, audio_duration_sec: float) -> dict:
        visemes = []
        vtimes = []
        vdurations = []

        i = 0
        while i < len(chunks):
            chunk = chunks[i]
            text = chunk["text"]
            start, end = chunk["timestamp"]

            if start is None or end is None:
                i += 1
                continue

            # Handle space
            if text == " ":
                pause_start = start
                pause_end = end
                count = 1

                # Check for multiple consecutive spaces
                while (i + 1 < len(chunks)) and (chunks[i + 1]["text"] == " "):
                    i += 1
                    next_chunk = chunks[i]
                    pause_end = next_chunk["timestamp"][1]
                    count += 1

                pause_duration = pause_end - pause_start

                if count == 1 and len(visemes) > 0:
                    # Merge single space with previous viseme
                    vdurations[-1] += int(pause_duration * 1000)
                else:
                    # Treat multiple spaces as separate viseme
                    visemes.append("sil")
                    vtimes.append(int(pause_start * 1000))
                    vdurations.append(int(pause_duration * 1000))

            else:
                # This logic handles phonemes and maps them to visemes
                # taking into account phonemes represented by multiple visemes.
                mapped_visemes = self.phoneme_viseme_map.get(text, ["sil"])
                num_visemes = len(mapped_visemes)
                duration_ms = int((end - start) * 1000)
                sub_duration = duration_ms // num_visemes
                start_ms = int(start * 1000)

                for i, viseme in enumerate(mapped_visemes):
                    visemes.append(viseme)
                    vtimes.append(start_ms + i * sub_duration)
                    # If last viseme, assign any remainder to preserve total duration
                    if i == num_visemes - 1:
                        vdurations.append(
                            duration_ms - sub_duration * (num_visemes - 1)
                        )
                    else:
                        vdurations.append(sub_duration)

            i += 1

        return {
            "visemes": visemes,
            "vtimes": vtimes,
            "vdurations": vdurations,
            "duration": float(audio_duration_sec),  # total duration in s
        }

    def _run_forced_alignment(self, waveform, transcript):
        """Run forced alignment to get precise word timings."""
        waveform_tensor = torch.from_numpy(waveform).to(self.device)
        if waveform_tensor.ndim == 1:
            waveform_tensor = waveform_tensor.unsqueeze(0)  # shape: [1, time]
        emissions, _ = self.model(waveform_tensor)
        emissions = torch.log_softmax(emissions, dim=-1)[0].cpu().detach()
        transcript = transcript.translate(str.maketrans("", "", string.punctuation))
        transcript = "|" + "|".join(transcript.strip().upper()) + "|"
        transcript = transcript.replace(" ", "")
        tokens = [self.dictionary[c] for c in transcript]

        trellis = self._get_trellis(emissions, tokens)
        path = self._backtrack(trellis, emissions, tokens)
        segments = self._merge_repeats(path, transcript)
        words = self._merge_words(segments)
        return {
            "words": [w.label for w in words],
            "wtimes": [w.start * 20 for w in words],
            "wdurations": [(w.end - w.start) * 20 for w in words],
            "duration": waveform_tensor.shape[1] // 16,
        }

    def _get_trellis(self, emission, tokens, blank_id=0):
        """Compute the trellis for the given emissions and tokens (for forced alignment)."""
        T, N = emission.size(0), len(tokens)
        trellis = torch.full((T, N), -float("inf"))
        trellis[1:, 0] = torch.cumsum(emission[1:, blank_id], 0)
        trellis[0, 1:] = -float("inf")
        for t in range(T - 1):
            trellis[t + 1, 1:] = torch.maximum(
                trellis[t, 1:] + emission[t, blank_id],
                trellis[t, :-1] + emission[t, tokens[1:]],
            )
        return trellis

    def _backtrack(self, trellis, emission, tokens, blank_id=0):
        """Backtrack the trellis to compute the best path (for forced alignment)."""

        @dataclass
        class Point:
            token_index: int
            time_index: int
            score: float

        t, j = trellis.size(0) - 1, trellis.size(1) - 1
        path = [Point(j, t, emission[t, blank_id].exp().item())]
        while j > 0 and t > 0:
            p_stay = emission[t - 1, blank_id]
            p_change = emission[t - 1, tokens[j]]
            stayed = trellis[t - 1, j] + p_stay
            changed = trellis[t - 1, j - 1] + p_change
            t -= 1
            if changed > stayed:
                j -= 1
            prob = (p_change if changed > stayed else p_stay).exp().item()
            path.append(Point(j, t, prob))
        return path[::-1]

    def _merge_repeats(self, path, transcript):
        """Merge repeated tokens in the path to create segments."""

        @dataclass
        class Segment:
            label: str
            start: int
            end: int
            score: float

        i1, i2 = 0, 0
        segments = []
        while i1 < len(path):
            while i2 < len(path) and path[i1].token_index == path[i2].token_index:
                i2 += 1
            seg_score = sum(path[k].score for k in range(i1, i2)) / (i2 - i1)
            segments.append(
                Segment(
                    label=transcript[path[i1].token_index],
                    start=path[i1].time_index,
                    end=path[i2 - 1].time_index + 1,
                    score=seg_score,
                )
            )
            i1 = i2
        return segments

    def _merge_words(self, segments, sep="|"):
        """Merge segments into words based on the separator (for forced alignment)."""

        @dataclass
        class Segment:
            label: str
            start: int
            end: int
            score: float

        words = []
        i1 = 0
        while i1 < len(segments):
            i2 = i1
            while i2 < len(segments) and segments[i2].label != sep:
                i2 += 1
            if i1 != i2:
                segs = segments[i1:i2]
                label = "".join([s.label for s in segs])
                score = sum(s.score * (s.end - s.start) for s in segs) / sum(
                    s.end - s.start for s in segs
                )
                words.append(Segment(label, segs[0].start, segs[-1].end, score))
            i1 = i2 + 1
        return words
