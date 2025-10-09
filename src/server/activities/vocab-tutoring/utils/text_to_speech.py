# git clone https://github.com/boson-ai/higgs-audio.git
# conda create -n bosonai python=3.11
# conda activate bosonai
# pip install -r requirements.txt
# pip install -e .

# git clone https://github.com/boson-ai/higgs-audio.git
# conda create -n bosonai python=3.11
# conda activate bosonai
# pip install -r requirements.txt
# pip install -e .

import json
import re
import sys
import traceback
from pathlib import Path

import numpy as np
import torch
import torchaudio

from boson_multimodal.serve.serve_engine import (
    HiggsAudioServeEngine,
    HiggsAudioResponse,
)
from boson_multimodal.data_types import ChatMLSample, Message


# ---------- helpers ----------
def split_into_chunks(text: str, max_len: int = 1000):
    """
    Split text into sentence-based chunks, each <= max_len characters.
    Uses a lightweight regex splitter to avoid external deps.
    """
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []

    # Split into sentences (keep delimiters via lookbehind)
    sentences = re.split(r"(?<=[\.\!\?])\s+", text)

    chunks, current = [], ""
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        # If a single sentence is longer than max_len, hard-wrap it.
        if len(s) > max_len:
            # Break long sentence into pieces on word boundaries
            words = s.split(" ")
            piece = ""
            for w in words:
                if len(piece) + 1 + len(w) <= max_len:
                    piece = (piece + " " + w).strip()
                else:
                    if piece:
                        chunks.append(piece)
                    piece = w
            if piece:
                chunks.append(piece)
            continue

        if not current:
            current = s
        elif len(current) + 1 + len(s) <= max_len:
            current = f"{current} {s}"
        else:
            chunks.append(current)
            current = s

    if current:
        chunks.append(current)

    return chunks


def log_exception(prefix: str, err: BaseException):
    print(f"[error] {prefix}: {err.__class__.__name__}: {err}", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)


# ---------- model setup ----------
MODEL_PATH = "bosonai/higgs-audio-v2-generation-3B-base"
AUDIO_TOKENIZER_PATH = "bosonai/higgs-audio-v2-tokenizer"
device = "cuda" if torch.cuda.is_available() else "cpu"

serve_engine = HiggsAudioServeEngine(MODEL_PATH, AUDIO_TOKENIZER_PATH, device=device)

system_prompt = (
    "Generate audio following instruction.\n\n"
    "<|scene_desc_start|>\n"
    "Audio is recorded from a quiet room. A female voice reads aloud the given book content.\n"
    "<|scene_desc_end|>"
)

# ---------- I/O setup ----------
chapters_root = Path("../chapters")
audios_root = Path("../audios")
audios_root.mkdir(parents=True, exist_ok=True)

# ---------- main loop ----------
for book_dir in sorted(chapters_root.iterdir()):
    if not book_dir.is_dir():
        continue

    out_dir = audios_root / book_dir.name
    out_dir.mkdir(parents=True, exist_ok=True)

    for chapter_file in sorted(book_dir.glob("*.json")):
        try:
            out_path = out_dir / f"{chapter_file.stem}.wav"
            if out_path.exists():
                print(f"[skip exists] {out_path}")
                continue

            # --- read chapter JSON ---
            with chapter_file.open("r", encoding="utf-8") as f:
                data = json.load(f)

            title = (data.get("title") or chapter_file.stem).strip()
            text = (data.get("text") or "").strip()
            if not text:
                print(f"[skip empty] {chapter_file}")
                continue

            # --- chunking (≤1000 chars per piece, sentence-aware) ---
            # Preface first chunk with the title (kept short)
            chunks = split_into_chunks(text, max_len=1000)
            if not chunks:
                print(f"[skip chunkless] {chapter_file}")
                continue
            if chunks:
                # Optionally prepend title to the first chunk if it fits; otherwise keep title separate.
                title_line = title.strip()
                if len(title_line) + 2 + len(chunks[0]) <= 1000:
                    chunks[0] = f"{title_line}\n\n{chunks[0]}"
                else:
                    chunks.insert(0, title_line[:1000])  # very long titles trimmed

            # --- TTS per chunk and concatenate ---
            audio_segments = []
            sampling_rate = None

            for i, chunk in enumerate(chunks, start=1):
                try:
                    messages = [
                        Message(role="system", content=system_prompt),
                        Message(role="user", content=chunk),
                    ]

                    print(f"processing {out_path} [chunk {i}/{len(chunks)}]...")
                    output: HiggsAudioResponse = serve_engine.generate(
                        chat_ml_sample=ChatMLSample(messages=messages),
                        max_new_tokens=1024,
                        temperature=0.2,
                        top_p=0.95,
                        top_k=50,
                        stop_strings=["<|end_of_text|>", "<|eot_id|>"],
                    )

                    if sampling_rate is None:
                        sampling_rate = output.sampling_rate
                    elif sampling_rate != output.sampling_rate:
                        raise RuntimeError(
                            f"Mismatched sampling rate: {sampling_rate} vs {output.sampling_rate}"
                        )

                    seg = output.audio
                    if seg is None or (isinstance(seg, np.ndarray) and seg.size == 0):
                        print(f"[warn] empty audio for chunk {i}; skipping")
                        continue

                    # Ensure 1-D numpy float array
                    seg = np.asarray(seg).astype(np.float32).ravel()
                    audio_segments.append(seg)

                except Exception as e_chunk:
                    log_exception(
                        f"generate chunk {i} for {chapter_file.name}", e_chunk
                    )
                    # Continue with remaining chunks

            # --- save concatenated chapter ---
            if not audio_segments:
                print(
                    f"[warn] no audio produced for {chapter_file.name}; skipping save"
                )
                continue

            full_audio = np.concatenate(audio_segments, axis=0)
            wav_tensor = torch.from_numpy(full_audio)[None, :]  # shape: [1, T]
            torchaudio.save(str(out_path), wav_tensor, sampling_rate)
            print(f"[ok] {book_dir.name}/{chapter_file.name} → {out_path}")

        except Exception as e_chapter:
            log_exception(f"chapter {chapter_file}", e_chapter)
            # Move on to next chapter
