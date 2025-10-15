#!/usr/bin/env python3
"""
Forced word alignment using torchaudio MMS_FA.

This is good for aligning text books to audio narration.

Usage:
  python forced_alignment.py --audio_path /path/to/audio.wav --json_path /path/to/transcript.json

Input JSON format:
  {"text": "your transcript text here"}

Output (printed):
  [
    {"start": 0.12, "end": 0.45, "text": "Hello"},
    {"start": None, "end": None, "text": "there!"}
  ]

Notes:
- Times are seconds (float).
- Words with no alignable characters (or not aligned) have start/end = None.
- torchaudio.functional.forced_align is deprecated (removed in 2.9). Works on 2.8.x.
"""

import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any

import torch
import torchaudio
import torchaudio.functional as F


def _safe_resample(
    waveform: torch.Tensor, orig_sr: int, target_sr: int
) -> torch.Tensor:
    """Resample waveform to target_sr if needed."""
    if orig_sr == target_sr:
        return waveform
    return torchaudio.functional.resample(waveform, orig_sr, target_sr)


def _frame_duration_seconds(num_samples: int, sr: int, num_frames: int) -> float:
    """Duration (sec) of a single emission frame."""
    total_secs = num_samples / float(sr)
    return total_secs / float(num_frames)


def _detect_blank_id(labels: List[str]) -> int:
    """Determine the CTC blank index from pipeline labels."""
    if "<blk>" in labels:
        return labels.index("<blk>")
    if "<blank>" in labels:
        return labels.index("<blank>")
    return 0  # fallback


def _build_dictionary_wo_blank(
    raw_dict: Dict[str, int], blank_id: int
) -> Dict[str, int]:
    """Copy dictionary excluding any entries that map to the blank symbol."""
    return {k: v for k, v in raw_dict.items() if v != blank_id}


def _tokenize_words(
    text: str, dictionary: Dict[str, int]
) -> Tuple[List[str], List[List[int]]]:
    """
    Tokenize into words; for each word, keep only characters present in dictionary.
    - Lowercases text (MMS is case-insensitive).
    - Punctuation not in dictionary is ignored for alignment (but preserved in output).
    """
    words = text.strip().split()
    word_token_ids: List[List[int]] = []
    for w in words:
        ids = [dictionary[ch] for ch in w.lower() if ch in dictionary]
        word_token_ids.append(ids)
    return words, word_token_ids


def _flatten_token_ids(word_token_ids: List[List[int]]) -> List[int]:
    flat: List[int] = []
    for ids in word_token_ids:
        flat.extend(ids)
    return flat


def _group_char_spans_to_words(
    char_spans: List[Optional[Any]],
    word_token_ids: List[List[int]],
) -> List[List[Optional[Any]]]:
    """
    Regroup flat char-level spans into word-level lists (same lengths as token ids).
    Missing entries are treated as None (robustness).
    """
    grouped: List[List[Optional[Any]]] = []
    i = 0
    for ids in word_token_ids:
        n = len(ids)
        chunk: List[Optional[Any]] = []
        for _ in range(n):
            chunk.append(char_spans[i] if i < len(char_spans) else None)
            i += 1
        grouped.append(chunk)
    return grouped


def _extract_span_indices(span_obj: Any) -> Optional[Tuple[int, int]]:
    """
    Return (start_frame, end_frame) from either:
      - dict-like: {"start": int, "end": int, ...}
      - object-like: attributes .start, .end (e.g., torchaudio TokenSpan)
    Returns None if invalid.
    """
    if span_obj is None:
        return None
    # dict-like
    if isinstance(span_obj, dict):
        s = span_obj.get("start", None)
        e = span_obj.get("end", None)
    else:
        # object-like
        s = getattr(span_obj, "start", None)
        e = getattr(span_obj, "end", None)
    if isinstance(s, int) and isinstance(e, int) and e >= s and s >= 0:
        return s, e
    return None


def _span_to_seconds(
    span_group: List[Optional[Any]], frame_dt: float
) -> Tuple[Optional[float], Optional[float]]:
    """
    Convert a list of character-level spans for a word to (start_sec, end_sec).
    If no valid char spans exist, return (None, None).
    """
    starts: List[int] = []
    ends: List[int] = []
    for sp in span_group:
        se = _extract_span_indices(sp)
        if se is not None:
            s, e = se
            starts.append(s)
            ends.append(e)
    if not starts or not ends:
        return None, None
    return min(starts) * frame_dt, max(ends) * frame_dt


def align_words(audio_path: str, json_path: str) -> List[Dict[str, Optional[float]]]:
    """
    Perform forced alignment and return per-word spans:
      [{"start": float|None, "end": float|None, "text": str}, ...]
    """
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # ---- Load transcription ----
    text_raw = json.loads(Path(json_path).read_text(encoding="utf-8")).get("text", "")
    if not isinstance(text_raw, str) or not text_raw.strip():
        return []

    # ---- Load model & resources ----
    bundle = torchaudio.pipelines.MMS_FA
    model = bundle.get_model(with_star=False).to(device)

    LABELS = bundle.get_labels(star=None)
    blank_id = _detect_blank_id(LABELS)

    RAW_DICT = bundle.get_dict(star=None)
    DICTIONARY = _build_dictionary_wo_blank(RAW_DICT, blank_id)

    # ---- Load & prepare audio ----
    waveform, sr = torchaudio.load(audio_path)
    # Mono
    if waveform.dim() == 2 and waveform.size(0) > 1:
        waveform = waveform.mean(dim=0, keepdim=True)
    # Resample
    waveform = _safe_resample(waveform, sr, bundle.sample_rate)
    sr = bundle.sample_rate

    waveform = waveform.to(device)
    with torch.inference_mode():
        emission, _ = model(waveform)
    # emission: (1, frames, num_labels)
    num_frames = emission.shape[1]
    num_samples = waveform.shape[-1]
    frame_dt = _frame_duration_seconds(num_samples, sr, num_frames)

    # ---- Tokenize text into words/chars ----
    words, word_token_ids = _tokenize_words(text_raw, DICTIONARY)
    flat_tokens = _flatten_token_ids(word_token_ids)
    # Safety filter (should be no-ops if DICTIONARY was cleaned)
    flat_tokens = [t for t in flat_tokens if t != blank_id]

    # If nothing alignable, return all None spans
    if len(flat_tokens) == 0:
        return [{"start": None, "end": None, "text": w} for w in words]

    # ---- Forced alignment (CTC) ----
    targets = torch.tensor([flat_tokens], dtype=torch.int32, device=device)

    # IMPORTANT: pass the SAME blank id we detected
    alignments, scores = F.forced_align(emission, targets, blank=blank_id)
    alignments, scores = alignments[0], scores[0]  # remove batch dim
    scores = scores.exp()  # convert log-prob to prob

    # ---- Merge token spans (character-level) ----
    # Returns a sequence of TokenSpan-like entries (object with .start/.end/.score) in flat token order.
    char_spans = F.merge_tokens(alignments, scores)

    # Robust length match
    if len(char_spans) < len(flat_tokens):
        char_spans = list(char_spans) + [None] * (len(flat_tokens) - len(char_spans))
    elif len(char_spans) > len(flat_tokens):
        char_spans = list(char_spans)[: len(flat_tokens)]

    # ---- Group char spans back into words & compute word-level spans ----
    grouped = _group_char_spans_to_words(char_spans, word_token_ids)
    results: List[Dict[str, Optional[float]]] = []
    for w, char_group in zip(words, grouped):
        start_sec, end_sec = _span_to_seconds(char_group, frame_dt)
        results.append({"start": start_sec, "end": end_sec, "text": w})

    return results


# ---------- CLI ----------
if __name__ == "__main__":
    import argparse
    import pprint

    parser = argparse.ArgumentParser(
        description="Forced align words with torchaudio MMS_FA."
    )
    parser.add_argument(
        "--audio_path", required=True, type=str, help="Path to audio file"
    )
    parser.add_argument(
        "--json_path",
        required=True,
        type=str,
        help='Path to JSON file with {"text": "..."}',
    )
    args = parser.parse_args()

    spans = align_words(args.audio_path, args.json_path)
    pprint.pp(spans)

    with open("output_path.json", "w", encoding="utf-8") as f:
        json.dump(spans, f, indent=2)
