"""Device detection utilities for PyTorch."""

import torch
from torch import device as TorchDevice


def get_best_device(options=["cuda", "mps", "cpu"]) -> TorchDevice:
    """Returns the "best" available torch device according to the following strategy:

    1. Use CUDA if available.
    2. If not, use MPS (Metal Performance Shaders) if available.
    3. Otherwise, fall back to CPU.

    Returns:
        torch.device: The best available torch device ('cuda', 'mps', or 'cpu').
    """
    if torch.cuda.is_available() and "cuda" in options:
        return torch.device("cuda")
    elif (
        hasattr(torch.backends, "mps")
        and torch.backends.mps.is_available()
        and "mps" in options
    ):
        return torch.device("mps")
    else:
        # Fallback to CPU
        return torch.device("cpu")
