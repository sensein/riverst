"""Audio processors.

Submodules are imported LAZILY (PEP 562). Importing this package must NOT pull in
torch/senselab/SQUIM — `analyzer` alone loads ~1 GB of speech models (SQUIM, speechbrain
ECAPA, feature extractors) at import time, even though audio analysis only runs when
ANALYZE_AUDIO=true (off for the language tutor). Eager imports here loaded that whole stack
at process startup and thrashed swap on the shared box. Now each name resolves on first
access, so the analysis stack is loaded only by the code path that actually uses it
(bot/core/event_manager.py, inside its `if ANALYZE_AUDIO:` branch).
"""

__all__ = ["AudioAnalyzer", "AudioResamplingHelper", "tensor_to_serializable"]

_LAZY = {
    "AudioAnalyzer": ".analyzer",
    "AudioResamplingHelper": ".resampling_helper",
    "tensor_to_serializable": ".serialization",
}


def __getattr__(name):
    """PEP 562 lazy attribute loader — import the owning submodule on first access only."""
    module = _LAZY.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    return getattr(importlib.import_module(module, __name__), name)
