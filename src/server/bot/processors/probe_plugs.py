"""Gated UDP measurement plugs for the LIVE bot pipeline.

Inert unless KIVA_PIPE_DEBUG=1. When on:
  - Tap(name): pass-through processor; fires per-audio-frame timing to the UDP collector.
  - start_loop_lag(): background task firing event-loop lag every 10ms.
  - start_text_injector(task): UDP plug (port 7870) that speaks whatever text it receives, so
    we can drive Kiva to talk continuously without a human.

All measurements are sent as UDP datagrams to the collector (tools/scratch/udp_logd.py) so the
pipeline never does blocking file I/O that would itself jitter the loop we're measuring.
Datagram formats: 'tap,<name>,<wall>,<samples>,<sr>,<gap_ms>' and 'lag,<wall>,<lag_ms>'.
"""
import asyncio
import os
import socket
import time

from pipecat.frames.frames import Frame, TTSAudioRawFrame, TTSSpeakFrame
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection

ENABLED = os.getenv("KIVA_PIPE_DEBUG", "").strip().lower() in ("1", "true", "yes", "on")
_LOG_PORT = int(os.getenv("KIVA_PROBE_LOG_PORT", "7871"))
_INJECT_PORT = int(os.getenv("KIVA_PROBE_INJECT_PORT", "7870"))

_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
_sock.setblocking(False)
_addr = ("127.0.0.1", _LOG_PORT)


def emit(line: str) -> None:
    try:
        _sock.sendto(line.encode(), _addr)
    except OSError:
        pass


class Tap(FrameProcessor):
    """Pass-through plug: fires timing/count for each audio frame it sees."""

    def __init__(self, name: str):
        super().__init__()
        self._name = name
        self._last = None

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, TTSAudioRawFrame):
            now = time.monotonic()
            gap = (now - self._last) * 1000 if self._last is not None else 0.0
            self._last = now
            emit(f"tap,{self._name},{now:.4f},{len(frame.audio)//2},{frame.sample_rate or 24000},{gap:.1f}")
        await self.push_frame(frame, direction)


async def _loop_lag(stop: asyncio.Event, target: float = 0.01):
    last = time.monotonic()
    while not stop.is_set():
        await asyncio.sleep(target)
        now = time.monotonic()
        emit(f"lag,{now:.4f},{((now - last) - target) * 1000:.1f}")
        last = now


def start_loop_lag() -> asyncio.Event:
    stop = asyncio.Event()
    asyncio.create_task(_loop_lag(stop))
    return stop


async def start_text_injector(task):
    """Bind the UDP text plug; each datagram's text is queued as speech into the pipeline."""
    loop = asyncio.get_running_loop()

    class _Proto(asyncio.DatagramProtocol):
        def datagram_received(self, data, addr):
            text = data.decode("utf-8", "ignore").strip()
            if text:
                asyncio.get_running_loop().create_task(task.queue_frame(TTSSpeakFrame(text)))

    transport, _ = await loop.create_datagram_endpoint(
        lambda: _Proto(), local_addr=("127.0.0.1", _INJECT_PORT), reuse_port=True
    )
    return transport
