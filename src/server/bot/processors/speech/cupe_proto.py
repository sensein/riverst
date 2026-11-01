"""UDP wire protocol for the CUPE lip-sync link (pipecat LipsyncProcessor <-> cupe_service).

Each datagram is a 1-byte type tag followed by a type-specific payload. The link is
loss/reorder tolerant on purpose — a dropped audio datagram costs at most one small viseme
gap, and sending never blocks the real-time audio path."""
import os
import struct

HOST = os.getenv("CUPE_UDP_HOST", "127.0.0.1")
PORT = int(os.getenv("CUPE_UDP_PORT", "7861"))

# processor -> service
AUDIO = b"A"   # <seq u32><sample_rate u32><int16 pcm bytes>
START = b"S"   # TTS turn started (reset buffer)
STOP = b"E"    # TTS turn stopped (flush remaining)
QUIT = b"Q"    # session ended (drop per-sender state)
# service -> processor
VISEME = b"V"  # <utf-8 json viseme-event>

_AUDIO_HDR = struct.Struct(">II")  # seq, sample_rate


def pack_audio(seq, sample_rate, pcm_bytes):
    return AUDIO + _AUDIO_HDR.pack(seq, sample_rate) + pcm_bytes


def unpack_audio(payload):
    seq, sample_rate = _AUDIO_HDR.unpack_from(payload, 0)
    return seq, sample_rate, payload[_AUDIO_HDR.size:]
