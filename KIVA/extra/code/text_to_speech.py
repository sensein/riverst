"""This module is an experiment for generating audiobooks from text using the Higgs-Audio model.


Setup instructions (run once):
> git clone https://github.com/boson-ai/higgs-audio.git
> conda create -n bosonai python=3.11
> conda activate bosonai
> pip install -r requirements.txt
> pip install -e .


Usage:
> python text_to_speech.py

Notes:
- The Higgs-Audio model is quite large (3B parameters)
and requires a GPU with at least 16GB of VRAM to run effectively.
- Unfortunately, I have experienced some instability with the model,
leading to occasional hallucinations and artifacts.
- Hallucinatory outputs led me to opt for using naturalistic audio
from https://archive.org/ instead of generating all audio via the model.
Hopefully future model updates will improve this.
"""

import json
import re
import sys
import traceback
from pathlib import Path
from typing import List, Optional
import numpy as np

import torch
import torchaudio

# chunking deps
import langid
import jieba
import tqdm
import os
from dataclasses import asdict

from loguru import logger
from transformers import AutoConfig, AutoTokenizer
from transformers.cache_utils import StaticCache

from boson_multimodal.data_types import (
    ChatMLSample,
    Message,
    AudioContent,
    TextContent,
)
from boson_multimodal.model.higgs_audio import HiggsAudioModel
from boson_multimodal.data_collator.higgs_audio_collator import HiggsAudioSampleCollator
from boson_multimodal.audio_processing.higgs_audio_tokenizer import (
    load_higgs_audio_tokenizer,
)
from boson_multimodal.dataset.chatml_dataset import (
    ChatMLDatasetSample,
    prepare_chatml_sample,
)
from boson_multimodal.model.higgs_audio.utils import revert_delay_pattern


# ---------- helpers ----------
def log_exception(prefix: str, err: BaseException):
    print(f"[error] {prefix}: {err.__class__.__name__}: {err}", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)


# ---------- prepare_chunk_text (from example) ----------
def prepare_chunk_text(
    text: str,
    chunk_method: Optional[str] = None,
    chunk_max_word_num: int = 200,
    chunk_max_num_turns: int = 1,
) -> List[str]:
    """
    Example method for chunking:
      - None: whole text
      - 'speaker': split on [SPEAKER*] lines; optionally merge N turns
      - 'word': per-paragraph, then word-count chunks (Chinese via jieba)
    """
    if chunk_method is None:
        return [text]

    text = text.strip()
    if not text:
        return []

    if chunk_method == "speaker":
        lines = text.split("\n")
        speaker_chunks = []
        speaker_utterance = ""
        for line in lines:
            line = line.strip()
            if line.startswith("[SPEAKER") or line.startswith("<|speaker_id_start|>"):
                if speaker_utterance:
                    speaker_chunks.append(speaker_utterance.strip())
                speaker_utterance = line
            else:
                if speaker_utterance:
                    speaker_utterance += "\n" + line
                else:
                    speaker_utterance = line
        if speaker_utterance:
            speaker_chunks.append(speaker_utterance.strip())
        if chunk_max_num_turns > 1:
            merged = []
            for i in range(0, len(speaker_chunks), chunk_max_num_turns):
                merged.append(
                    "\n".join(speaker_chunks[i : i + chunk_max_num_turns])  # noqa: E203
                )  # noqa: E203
            return merged
        return speaker_chunks

    if chunk_method == "word":
        language = langid.classify(text)[0]
        paragraphs = text.split("\n\n")
        chunks = []
        for p in paragraphs:
            p = p.strip()
            if not p:
                continue
            if language == "zh":
                words = list(jieba.cut(p, cut_all=False))
                for i in range(0, len(words), chunk_max_word_num):  # noqa: E203
                    chunks.append(
                        "".join(words[i : i + chunk_max_word_num])  # noqa: E203
                    )  # noqa: E203
            else:
                words = p.split()
                for i in range(0, len(words), chunk_max_word_num):
                    chunks.append(
                        " ".join(words[i : i + chunk_max_word_num])  # noqa: E203
                    )  # noqa: E203
            if chunks:
                chunks[-1] = chunks[-1] + "\n\n"
        return chunks

    raise ValueError(f"Unknown chunk method: {chunk_method}")


# ---------- minimal normalization ----------
def normalize_chinese_punctuation(text: str) -> str:
    mapping = {
        "，": ", ",
        "。": ".",
        "：": ":",
        "；": ";",
        "？": "?",
        "！": "!",
        "（": "(",
        "）": ")",
        "【": "[",
        "】": "]",
        "《": "<",
        "》": ">",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "、": ",",
        "—": "-",
        "…": "...",
        "·": ".",
        "「": '"',
        "」": '"',
        "『": '"',
        "』": '"',
    }
    for zh, en in mapping.items():
        text = text.replace(zh, en)
    return text


# ---------- prepare_generation_context (example, extended to accept direct file paths) ----------
AUDIO_PLACEHOLDER_TOKEN = "<|__AUDIO_PLACEHOLDER__|>"


def _build_system_message_with_audio_prompt(system_message_text: str) -> Message:
    contents = []
    while AUDIO_PLACEHOLDER_TOKEN in system_message_text:
        loc = system_message_text.find(AUDIO_PLACEHOLDER_TOKEN)
        contents.append(TextContent(system_message_text[:loc]))
        contents.append(AudioContent(audio_url=""))
        value = loc + len(AUDIO_PLACEHOLDER_TOKEN)
        system_message_text = system_message_text[value:]  # noqa: E203
    if len(system_message_text) > 0:
        contents.append(TextContent(system_message_text))
    return Message(role="system", content=contents)


def prepare_generation_context(
    scene_prompt, ref_audio, ref_audio_in_system_message, audio_tokenizer, speaker_tags
):
    """
    Original example function with a tiny extension:
    - If ref_audio looks like a path (contains / or \\ or endswith .wav), use it directly.
    """
    system_message = None
    messages: List[Message] = []
    audio_ids = []

    if ref_audio is not None:
        speaker_info_l = ref_audio.split(",")
        use_direct_paths = any(
            ("/" in s or "\\" in s or s.lower().endswith(".wav"))
            for s in speaker_info_l
        )

        if ref_audio_in_system_message:
            speaker_desc = []
            for spk_id, _character_name in enumerate(speaker_info_l):
                speaker_desc.append(f"SPEAKER{spk_id}: {AUDIO_PLACEHOLDER_TOKEN}")
            if scene_prompt:
                system_message = (
                    "Generate audio following instruction.\n\n"
                    f"<|scene_desc_start|>\n{scene_prompt}\n\n"
                    + "\n".join(speaker_desc)
                    + "\n<|scene_desc_end|>"
                )
            else:
                system_message = (
                    "Generate audio following instruction.\n\n"
                    + "<|scene_desc_start|>\n"
                    + "\n".join(speaker_desc)
                    + "\n<|scene_desc_end|>"
                )
            system_message = _build_system_message_with_audio_prompt(system_message)
        else:
            if scene_prompt:
                system_message = Message(
                    role="system",
                    content="Generate audio following instruction.\n\n"
                    f"<|scene_desc_start|>\n{scene_prompt}\n<|scene_desc_end|>",
                )

        for spk_id, character_name in enumerate(speaker_info_l):
            if use_direct_paths:
                prompt_audio_path = character_name.strip()
            else:
                # fall back to examples/voice_prompts/<name>.wav
                prompt_audio_path = os.path.join(
                    "higgs-audio/examples/voice_prompts",
                    f"{character_name.strip()}.wav",
                )

            prompt_text_path = os.path.splitext(prompt_audio_path)[0] + ".txt"
            prompt_text = ""
            if os.path.exists(prompt_text_path):
                with open(prompt_text_path, "r", encoding="utf-8") as f:
                    prompt_text = f.read().strip()

            if os.path.exists(prompt_audio_path):
                # encode to audio_ids (for model_client.generate)
                try:
                    audio_tokens = audio_tokenizer.encode(prompt_audio_path)
                    audio_ids.append(audio_tokens)
                except Exception:
                    pass

                if not ref_audio_in_system_message:
                    messages.append(
                        Message(
                            role="user",
                            content=(
                                f"[SPEAKER{spk_id}] {prompt_text}"
                                if len(speaker_info_l) > 1
                                else (prompt_text or "[REF]")
                            ),
                        )
                    )
                    messages.append(
                        Message(
                            role="assistant",
                            content=AudioContent(audio_url=prompt_audio_path),
                        )
                    )
            else:
                raise FileNotFoundError(
                    f"Voice prompt audio file not found: {prompt_audio_path}"
                )
    else:
        if len(speaker_tags) > 1:
            speaker_desc_l = []
            for idx, tag in enumerate(speaker_tags):
                speaker_desc_l.append(
                    f"{tag}: {'feminine' if idx % 2 == 0 else 'masculine'}"
                )
            scene_desc_l = []
            if scene_prompt:
                scene_desc_l.append(scene_prompt)
            scene_desc_l.append("\n".join(speaker_desc_l))
            system_message = Message(
                role="system",
                content="You are an AI assistant designed to convert text into speech.\n\n<|scene_desc_start|>\n"
                + "\n\n".join(scene_desc_l)
                + "\n<|scene_desc_end|>",
            )
        else:
            system_message_l = ["Generate audio following instruction."]
            if scene_prompt:
                system_message_l.append(
                    f"<|scene_desc_start|>\n{scene_prompt}\n<|scene_desc_end|>"
                )
            system_message = Message(
                role="system", content="\n\n".join(system_message_l)
            )

    if system_message:
        messages.insert(0, system_message)
    return messages, audio_ids


# ---------- HiggsAudioModelClient (from example) ----------
class HiggsAudioModelClient:
    def __init__(
        self,
        model_path,
        audio_tokenizer,
        device=None,
        device_id=None,
        max_new_tokens=2048,
        kv_cache_lengths: List[int] = [1024, 4096, 8192],
        use_static_kv_cache=False,
    ):
        if device_id is not None:
            device = f"cuda:{device_id}"
            self._device = device
        else:
            if device is not None:
                self._device = device
            else:
                if torch.cuda.is_available():
                    self._device = "cuda:0"
                elif torch.backends.mps.is_available():
                    self._device = "mps"
                else:
                    self._device = "cpu"

        logger.info(f"Using device: {self._device}")
        if isinstance(audio_tokenizer, str):
            audio_tokenizer_device = "cpu" if self._device == "mps" else self._device
            self._audio_tokenizer = load_higgs_audio_tokenizer(
                audio_tokenizer, device=audio_tokenizer_device
            )
        else:
            self._audio_tokenizer = audio_tokenizer

        self._model = HiggsAudioModel.from_pretrained(
            model_path,
            device_map=self._device,
            torch_dtype=torch.bfloat16,
        )
        self._model.eval()
        self._kv_cache_lengths = kv_cache_lengths
        self._use_static_kv_cache = use_static_kv_cache

        self._tokenizer = AutoTokenizer.from_pretrained(model_path)
        self._config = AutoConfig.from_pretrained(model_path)
        self._max_new_tokens = max_new_tokens
        self._collator = HiggsAudioSampleCollator(
            whisper_processor=None,
            audio_in_token_id=self._config.audio_in_token_idx,
            audio_out_token_id=self._config.audio_out_token_idx,
            audio_stream_bos_id=self._config.audio_stream_bos_id,
            audio_stream_eos_id=self._config.audio_stream_eos_id,
            encode_whisper_embed=self._config.encode_whisper_embed,
            pad_token_id=self._config.pad_token_id,
            return_audio_in_tokens=self._config.encode_audio_in_tokens,
            use_delay_pattern=self._config.use_delay_pattern,
            round_to=1,
            audio_num_codebooks=self._config.audio_num_codebooks,
        )
        self.kv_caches = None
        if use_static_kv_cache:
            self._init_static_kv_cache()

    def _init_static_kv_cache(self):
        cache_config = (
            AutoConfig.from_pretrained(self._model.name_or_path)
            if hasattr(self._model, "name_or_path")
            else self._model.config.text_config
        )
        cache_config = self._model.config.text_config
        cache_config.num_hidden_layers = (
            self._model.config.text_config.num_hidden_layers
        )
        if self._model.config.audio_dual_ffn_layers:
            cache_config.num_hidden_layers += len(
                self._model.config.audio_dual_ffn_layers
            )
        self.kv_caches = {
            length: StaticCache(
                config=cache_config,
                max_batch_size=1,
                max_cache_len=length,
                device=self._model.device,
                dtype=self._model.dtype,
            )
            for length in sorted(self._kv_cache_lengths)
        }
        if "cuda" in self._device:
            logger.info("Capturing CUDA graphs for KV caches")
            self._model.capture_model(self.kv_caches.values())

    def _prepare_kv_caches(self):
        for kv_cache in self.kv_caches.values():
            kv_cache.reset()

    @torch.inference_mode()
    def generate(
        self,
        messages,
        audio_ids,
        chunked_text,
        generation_chunk_buffer_size=None,
        temperature=1.0,
        top_k=50,
        top_p=0.95,
        ras_win_len=7,
        ras_win_max_num_repeat=2,
        seed=123,
        *args,
        **kwargs,
    ):
        if ras_win_len is not None and ras_win_len <= 0:
            ras_win_len = None
        sr = 24000
        audio_out_ids_l = []
        generated_audio_ids = []
        generation_messages = []
        for idx, chunk_text in tqdm.tqdm(
            enumerate(chunked_text),
            desc="Generating audio chunks",
            total=len(chunked_text),
        ):
            generation_messages.append(
                Message(
                    role="user",
                    content=chunk_text,
                )
            )
            chatml_sample = ChatMLSample(messages=messages + generation_messages)
            input_tokens, _, _, _ = prepare_chatml_sample(
                chatml_sample, self._tokenizer
            )
            postfix = self._tokenizer.encode(
                "<|start_header_id|>assistant<|end_header_id|>\n\n",
                add_special_tokens=False,
            )
            input_tokens.extend(postfix)

            logger.info(f"========= Chunk {idx} Input =========")
            logger.info(self._tokenizer.decode(input_tokens))
            context_audio_ids = audio_ids + generated_audio_ids

            curr_sample = ChatMLDatasetSample(
                input_ids=torch.LongTensor(input_tokens),
                label_ids=None,
                audio_ids_concat=(
                    torch.concat([ele.cpu() for ele in context_audio_ids], dim=1)
                    if context_audio_ids
                    else None
                ),
                audio_ids_start=(
                    torch.cumsum(
                        torch.tensor(
                            [0] + [ele.shape[1] for ele in context_audio_ids],
                            dtype=torch.long,
                        ),
                        dim=0,
                    )
                    if context_audio_ids
                    else None
                ),
                audio_waveforms_concat=None,
                audio_waveforms_start=None,
                audio_sample_rate=None,
                audio_speaker_indices=None,
            )

            batch_data = self._collator([curr_sample])
            batch = asdict(batch_data)
            for k, v in batch.items():
                if isinstance(v, torch.Tensor):
                    batch[k] = v.contiguous().to(self._device)

            if self._use_static_kv_cache and self.kv_caches is not None:
                self._prepare_kv_caches()

            outputs = self._model.generate(
                **batch,
                max_new_tokens=self._max_new_tokens,
                use_cache=True,
                do_sample=True,
                temperature=temperature,
                top_k=top_k,
                top_p=top_p,
                past_key_values_buckets=self.kv_caches,
                ras_win_len=ras_win_len,
                ras_win_max_num_repeat=ras_win_max_num_repeat,
                stop_strings=["<|end_of_text|>", "<|eot_id|>"],
                tokenizer=self._tokenizer,
                seed=seed,
            )

            step_audio_out_ids_l = []
            for ele in outputs[1]:
                audio_out_ids = ele
                if self._config.use_delay_pattern:
                    audio_out_ids = revert_delay_pattern(audio_out_ids)
                step_audio_out_ids_l.append(
                    audio_out_ids.clip(0, self._audio_tokenizer.codebook_size - 1)[
                        :, 1:-1
                    ]
                )
            audio_out_ids = torch.concat(step_audio_out_ids_l, dim=1)
            audio_out_ids_l.append(audio_out_ids)
            generated_audio_ids.append(audio_out_ids)

            generation_messages.append(
                Message(
                    role="assistant",
                    content=AudioContent(audio_url=""),
                )
            )
            if (
                generation_chunk_buffer_size is not None
                and len(generated_audio_ids) > generation_chunk_buffer_size
            ):
                generated_audio_ids = generated_audio_ids[
                    -generation_chunk_buffer_size:
                ]
                generation_messages = generation_messages[
                    (-2 * generation_chunk_buffer_size) :  # noqa: E203
                ]

        logger.info("========= Final Text output =========")
        logger.info(self._tokenizer.decode(outputs[0][0]))
        concat_audio_out_ids = torch.concat(audio_out_ids_l, dim=1)

        if concat_audio_out_ids.device.type == "mps":
            concat_audio_out_ids_cpu = concat_audio_out_ids.detach().cpu()
        else:
            concat_audio_out_ids_cpu = concat_audio_out_ids

        concat_wv = self._audio_tokenizer.decode(concat_audio_out_ids_cpu.unsqueeze(0))[
            0, 0
        ]
        text_result = self._tokenizer.decode(outputs[0][0])
        return concat_wv, sr, text_result


# ---------- model setup ----------
MODEL_PATH = "bosonai/higgs-audio-v2-generation-3B-base"
AUDIO_TOKENIZER_PATH = "bosonai/higgs-audio-v2-tokenizer"

# device choice similar to your original
device = (
    "cuda"
    if torch.cuda.is_available()
    else ("mps" if torch.backends.mps.is_available() else "cpu")
)
logger.info(f"Device: {device}")

# tokenizer for prepare_generation_context
audio_tokenizer = load_higgs_audio_tokenizer(
    AUDIO_TOKENIZER_PATH, device="cpu" if device == "mps" else device
)

# Model client (replaces serve_engine usage)
model_client = HiggsAudioModelClient(
    model_path=MODEL_PATH,
    audio_tokenizer=audio_tokenizer,
    device=device,
    device_id=None,
    max_new_tokens=1024,
    use_static_kv_cache=(device.startswith("cuda")),
)

# Scene prompt that matches your previous system prompt description
SCENE_PROMPT = "Audio is recorded from a quiet room. A female voice reads aloud the given book content."

# ---------- I/O setup ----------
chapters_root = Path("../chapters")
audios_root = Path("../audios")
audios_root.mkdir(parents=True, exist_ok=True)

# ---------- voice-clone target (DIRECT FILE PATH) ----------
REF_AUDIO = (
    "higgs-audio/examples/voice_prompts/belinda.wav"  # <- your target voice file
)

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

            # --- normalization (light) ---
            text = normalize_chinese_punctuation(text)
            text = text.replace("(", " ").replace(")", " ")
            text = text.replace("°F", " degrees Fahrenheit").replace(
                "°C", " degrees Celsius"
            )
            lines = text.split("\n")
            text = "\n".join(
                [" ".join(line.split()) for line in lines if line.strip()]
            ).strip()
            if not any(
                text.endswith(c)
                for c in [".", "!", "?", ",", ";", '"', "'", "</SE_e>", "</SE>"]
            ):
                text += "."

            # --- chunking via prepare_chunk_text ---
            chunks = prepare_chunk_text(
                text,
                chunk_method="word",  # change to None/"speaker" if desired
                chunk_max_word_num=200,
                chunk_max_num_turns=1,
            )
            if not chunks:
                print(f"[skip chunkless] {chapter_file}")
                continue

            # --- ALWAYS prepend title (no length checks) ---
            chunks.insert(0, f"{title}\n")

            # --- Build base messages via prepare_generation_context (with voice cloning) ---
            pattern = re.compile(r"\[(SPEAKER\d+)\]")
            speaker_tags = sorted(set(pattern.findall(text)))

            messages_base, audio_ids = prepare_generation_context(
                scene_prompt=SCENE_PROMPT,
                ref_audio=REF_AUDIO,  # supports direct path ./belinda.wav
                ref_audio_in_system_message=False,
                audio_tokenizer=audio_tokenizer,
                speaker_tags=speaker_tags,
            )

            # print(messages_base)
            # print(audio_ids)
            # print(chunks)

            # --- Call model_client.generate once per chapter (it loops over chunks) ---
            try:
                concat_wv, sr, text_output = model_client.generate(
                    messages=messages_base,
                    audio_ids=audio_ids,
                    chunked_text=chunks,
                    generation_chunk_buffer_size=None,  # keep all prior generated audio in context
                    temperature=0.2,
                    top_k=50,
                    top_p=0.95,
                    ras_win_len=7,
                    ras_win_max_num_repeat=2,
                    seed=123,
                )
            except Exception as e_gen:
                log_exception(f"model_client.generate for {chapter_file.name}", e_gen)
                continue

            # --- save concatenated chapter ---
            # concat_wv may be torch.Tensor; convert to numpy float32
            wav_np = np.asarray(concat_wv).astype(np.float32).ravel()
            wav_tensor = torch.from_numpy(wav_np)[None, :]  # (1, T)
            torchaudio.save(str(out_path), wav_tensor, int(sr))
            print(f"[ok] {book_dir.name}/{chapter_file.name} → {out_path}")

        except Exception as e_chapter:
            log_exception(f"chapter {chapter_file}", e_chapter)
            # Move on to next chapter
