#!/usr/bin/env python3
"""
Forced word alignment with torchaudio MMS_FA.

Inputs:
  - audio_path: path to an audio file (any format torchaudio can read)
  - json_path:  path to a JSON file containing {"text": "..."} transcription

Output:
  A list of dicts: [{"start": float|None, "end": float|None, "text": str}, ...]
  Times are in seconds. Words not detected have start/end = None.
"""

import json
from pathlib import Path
from typing import List, Dict, Optional

import torch
import torchaudio
import torchaudio.functional as F


def _safe_resample(
    waveform: torch.Tensor, orig_sr: int, target_sr: int
) -> torch.Tensor:
    if orig_sr == target_sr:
        return waveform
    return torchaudio.functional.resample(waveform, orig_sr, target_sr)


def _frame_duration_seconds(num_samples: int, sr: int, num_frames: int) -> float:
    # duration per frame in seconds
    total_secs = num_samples / float(sr)
    return total_secs / float(num_frames)


def _tokenize_words(text: str, dictionary: dict) -> (List[str], List[List[int]]):
    """
    Tokenize into words; for each word, keep only characters present in the DICTIONARY.
    Returns:
      words_original: list[str] (as they appear in the text, split on whitespace)
      word_token_ids: list[list[int]] (token ids per word, possibly empty if no char matches)
    """
    words = text.strip().split()
    word_token_ids: List[List[int]] = []
    for w in words:
        ids = []
        for ch in w:
            if ch in dictionary:
                ids.append(dictionary[ch])
            # else: skip unknown chars (e.g., punctuation not in the dict)
        word_token_ids.append(ids)
    return words, word_token_ids


def _flatten_token_ids(word_token_ids: List[List[int]]) -> List[int]:
    flat = []
    for ids in word_token_ids:
        flat.extend(ids)
    return flat


def _group_char_spans_to_words(
    char_spans: List[Optional[dict]],
    word_token_ids: List[List[int]],
) -> List[List[Optional[dict]]]:
    """
    Given a flat list of per-character spans (possibly None) and the tokenization per word,
    regroup spans per word (same lengths as token lists). If the flat list is shorter than
    expected (shouldn't happen in normal cases), missing entries are treated as None.
    """
    grouped: List[List[Optional[dict]]] = []
    i = 0
    for ids in word_token_ids:
        n = len(ids)
        chunk = []
        for _ in range(n):
            chunk.append(char_spans[i] if i < len(char_spans) else None)
            i += 1
        grouped.append(chunk)
    return grouped


def _span_to_seconds(
    span_group: List[Optional[dict]], frame_dt: float
) -> (Optional[float], Optional[float]):
    """
    Convert a list of character-level spans for a word to (start_sec, end_sec).
    Each span dict is expected to have 'start' and 'end' fields expressed in frame indices.
    If no valid char spans exist, return (None, None).
    """
    starts = []
    ends = []
    for sp in span_group:
        if sp is None:
            continue
        # Expecting sp like {"start": int, "end": int, "score": float, ...}
        s = sp.get("start", None)
        e = sp.get("end", None)
        if isinstance(s, int) and isinstance(e, int) and e >= s and s >= 0:
            starts.append(s)
            ends.append(e)
    if not starts or not ends:
        return None, None
    return min(starts) * frame_dt, max(ends) * frame_dt


def align_words(audio_path: str, json_path: str) -> List[Dict[str, Optional[float]]]:
    """
    Perform forced alignment and return per-word spans.
    """
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # ---- Load transcription ----
    text = json.loads(Path(json_path).read_text(encoding="utf-8")).get("text", "")
    if not isinstance(text, str) or not text.strip():
        return []

    # ---- Load model & resources ----
    bundle = torchaudio.pipelines.MMS_FA
    model = bundle.get_model(with_star=False).to(device)
    DICTIONARY = bundle.get_dict(star=None)

    # ---- Load & prepare audio ----
    waveform, sr = torchaudio.load(audio_path)
    # Convert to mono if needed
    if waveform.dim() == 2 and waveform.size(0) > 1:
        waveform = waveform.mean(dim=0, keepdim=True)
    # Resample to model sample rate if needed
    waveform = _safe_resample(waveform, sr, bundle.sample_rate)
    sr = bundle.sample_rate

    waveform = waveform.to(device)
    with torch.inference_mode():
        emission, _ = model(waveform)

    # emission shape: (batch=1, frames, num_labels)
    # We'll need frames for time conversion
    num_frames = emission.shape[1]
    num_samples = waveform.shape[-1]
    frame_dt = _frame_duration_seconds(num_samples, sr, num_frames)

    # ---- Tokenize text into words/chars compatible with dictionary ----
    words, word_token_ids = _tokenize_words(text, DICTIONARY)
    flat_tokens = _flatten_token_ids(word_token_ids)

    # If there are no recognizable tokens at all, return all None spans
    if len(flat_tokens) == 0:
        return [{"start": None, "end": None, "text": w} for w in words]

    # ---- Forced alignment ----
    targets = torch.tensor([flat_tokens], dtype=torch.int32, device=device)
    # Use blank=0 consistent with MMS
    alignments, scores = F.forced_align(emission, targets, blank=0)
    alignments, scores = alignments[0], scores[0]  # remove batch dimension
    scores = scores.exp()  # convert log-probs to probabilities

    # ---- Merge token spans (character-level) ----
    # F.merge_tokens returns a list of dicts with 'start'/'end' frame indices and 'score' per token,
    # preserving the flat token order (one entry per character token).
    char_spans = F.merge_tokens(alignments, scores)

    # Make it robust: ensure length matches # of flat tokens by padding/truncating with None
    if len(char_spans) < len(flat_tokens):
        char_spans = list(char_spans) + [None] * (len(flat_tokens) - len(char_spans))
    elif len(char_spans) > len(flat_tokens):
        char_spans = list(char_spans)[: len(flat_tokens)]

    # ---- Group char spans back into words and compute word-level spans ----
    grouped = _group_char_spans_to_words(char_spans, word_token_ids)

    results: List[Dict[str, Optional[float]]] = []
    for w, char_group in zip(words, grouped):
        start_sec, end_sec = _span_to_seconds(char_group, frame_dt)
        results.append({"start": start_sec, "end": end_sec, "text": w})

    return results


# ---------- CLI example ----------
if __name__ == "__main__":
    import argparse
    import pprint

    parser = argparse.ArgumentParser(
        description="Forced align words with torchaudio MMS_FA."
    )
    parser.add_argument("audio_path", type=str, help="Path to audio file")
    parser.add_argument(
        "json_path", type=str, help='Path to JSON file with {"text": "..."}'
    )
    args = parser.parse_args()

    spans = align_words(args.audio_path, args.json_path)
    pprint.pp(spans)
