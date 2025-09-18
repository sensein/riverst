"""Audio-specific serialization utilities."""

from typing import Any
import torch
from senselab.utils.data_structures import ScriptLine


def tensor_to_serializable(obj: Any) -> Any:
    """Convert various objects into a JSON-serializable format."""
    if isinstance(obj, torch.Tensor):
        return obj.detach().cpu().tolist()
    elif isinstance(obj, ScriptLine):
        return obj.model_dump()  # Properly handles nested ScriptLine chunks too
    elif isinstance(obj, dict):
        return {k: tensor_to_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [tensor_to_serializable(v) for v in obj]
    else:
        return obj
