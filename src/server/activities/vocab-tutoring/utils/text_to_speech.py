# git clone https://github.com/boson-ai/higgs-audio.git
# conda create -n bosonai python=3.11
# conda activate bosonai
# pip install -r requirements.txt
# pip install -e .


import json
import torch
import torchaudio
from pathlib import Path
from boson_multimodal.serve.serve_engine import (
    HiggsAudioServeEngine,
    HiggsAudioResponse,
)
from boson_multimodal.data_types import ChatMLSample, Message

# --- model setup ---
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

# --- loop over all books and chapters ---
chapters_root = Path("../chapters")

for book_dir in sorted(chapters_root.iterdir()):
    if not book_dir.is_dir():
        continue

    out_dir = Path("../audios") / book_dir.name
    out_dir.mkdir(parents=True, exist_ok=True)

    for chapter_file in sorted(book_dir.glob("*.json")):
        with chapter_file.open("r", encoding="utf-8") as f:
            data = json.load(f)

        title = (data.get("title") or chapter_file.stem).strip()
        text = (data.get("text") or "").strip()
        if not text:
            print(f"[skip] {chapter_file}: empty text")
            continue

        content = f"{title}\n\n{text}"
        print("content: ", content[:100])

        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=content),
        ]

        out_path = out_dir / f"{chapter_file.stem}.wav"
        output: HiggsAudioResponse = serve_engine.generate(
            chat_ml_sample=ChatMLSample(messages=messages),
            max_new_tokens=1024,
            temperature=0.2,
            top_p=0.95,
            top_k=50,
            stop_strings=["<|end_of_text|>", "<|eot_id|>"],
        )

        torchaudio.save(
            str(out_path), torch.from_numpy(output.audio)[None, :], output.sampling_rate
        )
        print(f"[ok] {book_dir.name}/{chapter_file.name} → {out_path}")
