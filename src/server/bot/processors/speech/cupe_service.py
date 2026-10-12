"""Dedicated CUPE lip-sync service — a separate process (own core/GIL) that the KIVA app
launches at startup and terminates at shutdown (only in KIVA_LIPSYNC_MODE=cupe).

It owns ALL the heavy lip-sync work: it receives raw TTS audio from the pipecat
LipsyncProcessor over UDP, buffers + chunks it (0.5s), runs CUPE phoneme inference, maps
phonemes -> Oculus visemes, and sends viseme events back over UDP. Running here means none of
that ever touches the pipecat event loop, so it can't delay real-time audio.

UDP wire protocol: see cupe_proto.py. One sender (source address) == one session; state is
kept per source address and dropped on QUIT (or TTL eviction).

Run: python -m bot.processors.speech.cupe_service
Env: CUPE_UDP_HOST/CUPE_UDP_PORT (see cupe_proto), CUPE_MODEL (default multilingual-mls).
"""
import asyncio
import json
import os
import time

import numpy as np
import torch
import torchaudio
from loguru import logger

from bot.processors.speech import cupe_proto as P
from bot.processors.speech.lipsync_processor import (
    get_cupe_model,
    predict_phonemes_from_waveform,
)

MODEL = os.environ.get("CUPE_MODEL", "multilingual-mls")
SAMPLE_RATE = 16000
MIN_DURATION = 0.5  # seconds
MIN_SAMPLES = int(SAMPLE_RATE * MIN_DURATION)
VISEME_MAP_PATH = os.path.abspath("assets/phoneme_oculusviseme_map.json")
SESSION_TTL = 300.0  # drop per-sender state after this many seconds idle

_MODEL = None       # (extractor, windowing, token_to_phoneme, token_to_group)
_VISEME_MAP = None

# Keep the service from eating the whole machine and starving the main app's event loop:
#  - run at most ONE CUPE inference at a time (torch already uses several threads per call),
#  - and drop chunks when we're more than a couple behind, so a faster-than-real-time TTS burst
#    can't pile up unbounded inferences (that was causing audio to break).
_INFER_SEM = asyncio.Semaphore(1)
_MAX_INFLIGHT = int(os.getenv("CUPE_MAX_INFLIGHT", "3"))
_inflight = 0


class _Session:
    __slots__ = ("buf", "resamplers", "last_seen")

    def __init__(self):
        self.buf = []          # list of 1-D 16kHz float tensors
        self.resamplers = {}   # orig_sample_rate -> torchaudio Resample
        self.last_seen = time.monotonic()


def _preprocess(session, pcm_bytes, sample_rate):
    wf = torch.from_numpy(np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0)
    if sample_rate != SAMPLE_RATE:
        r = session.resamplers.get(sample_rate)
        if r is None:
            r = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=SAMPLE_RATE)
            session.resamplers[sample_rate] = r
        wf = r(wf.unsqueeze(0)).squeeze(0)
    return wf


def _take_chunks(session, wf):
    """Append a waveform and pop every full MIN_SAMPLES chunk (mirrors the old in-processor
    buffering in LipsyncProcessor._handle_audio_frame)."""
    session.buf.append(wf)
    chunks = []
    total = sum(w.shape[-1] for w in session.buf)
    while total >= MIN_SAMPLES:
        full = torch.cat(session.buf, dim=-1)
        chunks.append(full[:MIN_SAMPLES])
        remaining = full[MIN_SAMPLES:]
        session.buf = [remaining] if remaining.numel() > 0 else []
        total = remaining.shape[-1]
    return chunks


def _flush(session):
    if not session.buf:
        return []
    full = torch.cat(session.buf, dim=-1)
    session.buf = []
    return [full]


def _segments_to_viseme_events(phoneme_segments):
    """Map phonemes to visemes with durations (verbatim from the old
    LipsyncProcessor._phoneme_segments_to_viseme_events)."""
    visemes, vtimes, vdurations = [], [], []
    for segment in phoneme_segments:
        phoneme = segment["phoneme"].lower()
        viseme_id = _VISEME_MAP.get(phoneme, [None])[-1]
        start = segment["start"] * 1000
        end = segment["end"] * 1000
        duration = end - start
        if viseme_id is None or duration <= 0:
            continue
        visemes.append(viseme_id)
        vtimes.append(start)
        vdurations.append(duration)
    return {"visemes": visemes, "vtimes": vtimes, "vdurations": vdurations}


def _infer_chunk(chunk):
    """Run CUPE on one chunk (1-D 16kHz tensor) and return a viseme event dict, or None.
    Mirrors the old LipsyncProcessor._run_lipsync: pre-pad, predict, offset-correct, map."""
    pad = torch.zeros(int(MIN_DURATION * SAMPLE_RATE))
    padded = torch.cat([pad, chunk], dim=-1)
    ex, win, t2p, t2g = _MODEL
    result = predict_phonemes_from_waveform(
        padded, ex, win, t2p, t2g, sample_rate=SAMPLE_RATE, device="cpu"
    )

    offset = MIN_DURATION
    adjusted = []
    for seg in result["phoneme_segments"]:
        s, e = seg["start"], seg["end"]
        if e <= offset:
            continue
        if s < offset < e:
            continue
        seg_new = seg.copy()
        seg_new["start"] = round(s - offset, 2)
        seg_new["end"] = round(e - offset, 2)
        adjusted.append(seg_new)

    ev = _segments_to_viseme_events(adjusted)
    if ev["visemes"]:
        ev["vdurations"][-1] = chunk.shape[-1] / SAMPLE_RATE - ev["vtimes"][-1]
        ev["duration"] = chunk.shape[-1] / SAMPLE_RATE
        return ev
    return None


class CupeServerProtocol(asyncio.DatagramProtocol):
    def __init__(self):
        self.transport = None
        self.sessions = {}  # addr -> _Session

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        if not data:
            return
        try:
            self._dispatch(data[:1], data[1:], addr)
        except Exception:  # noqa: BLE001
            logger.exception("[cupe-service] bad datagram")

    def _dispatch(self, kind, payload, addr):
        if kind == P.QUIT:
            self.sessions.pop(addr, None)
            return
        session = self.sessions.get(addr)
        if session is None:
            session = _Session()
            self.sessions[addr] = session
            self._evict_idle()
        session.last_seen = time.monotonic()

        if kind == P.START:
            session.buf = []
        elif kind == P.AUDIO:
            _seq, sr, pcm = P.unpack_audio(payload)
            wf = _preprocess(session, pcm, sr)
            for chunk in _take_chunks(session, wf):
                asyncio.create_task(self._infer_and_reply(chunk, addr))
        elif kind == P.STOP:
            for chunk in _flush(session):
                asyncio.create_task(self._infer_and_reply(chunk, addr))

    def _evict_idle(self):
        now = time.monotonic()
        for a in [a for a, s in self.sessions.items() if now - s.last_seen > SESSION_TTL]:
            self.sessions.pop(a, None)

    async def _infer_and_reply(self, chunk, addr):
        global _inflight
        if _inflight >= _MAX_INFLIGHT:
            return  # too far behind — drop this chunk's visemes rather than grow lag/CPU
        _inflight += 1
        try:
            async with _INFER_SEM:  # serialize: one CUPE inference at a time
                ev = await asyncio.to_thread(_infer_chunk, chunk)
        except Exception:  # noqa: BLE001
            logger.exception("[cupe-service] inference failed")
            return
        finally:
            _inflight -= 1
        if ev and self.transport is not None:
            try:
                self.transport.sendto(P.VISEME + json.dumps(ev).encode(), addr)
            except Exception:  # noqa: BLE001
                pass


async def main():
    global _MODEL, _VISEME_MAP
    # Cap torch intra-op threads so one inference doesn't grab all cores (default = nproc).
    torch.set_num_threads(int(os.getenv("CUPE_TORCH_THREADS", "2")))
    with open(VISEME_MAP_PATH, "r", encoding="utf-8") as f:
        _VISEME_MAP = json.load(f)
    logger.info(f"[cupe-service] loading CUPE model '{MODEL}' …")
    _MODEL = await asyncio.to_thread(get_cupe_model, MODEL, "cpu")
    loop = asyncio.get_running_loop()
    transport, _ = await loop.create_datagram_endpoint(
        CupeServerProtocol, local_addr=(P.HOST, P.PORT)
    )
    logger.info(f"[cupe-service] ready (UDP {P.HOST}:{P.PORT})")
    try:
        await asyncio.Future()
    finally:
        transport.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
