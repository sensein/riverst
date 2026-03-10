"""Device detection utilities for PyTorch."""

import os

import torch
from torch import device as TorchDevice

COMPUTE_DEVICE_ENV_VAR = "RIVERST_COMPUTE_DEVICE"
DEPLOYMENT_TARGET_ENV_VAR = "RIVERST_DEPLOYMENT_TARGET"
DEFAULT_DEVICE_ORDER = ("cuda", "mps", "cpu")
VALID_COMPUTE_DEVICE_POLICIES = {"auto", "cpu"}


def get_compute_device_policy() -> str:
    """Return the configured runtime compute device policy.

    `auto` prefers accelerated backends when available.
    `cpu` forces all local model execution onto CPU.
    """
    policy = os.getenv(COMPUTE_DEVICE_ENV_VAR, "auto").strip().lower()
    if policy not in VALID_COMPUTE_DEVICE_POLICIES:
        raise ValueError(
            f"Invalid {COMPUTE_DEVICE_ENV_VAR}={policy!r}. "
            f"Expected one of {sorted(VALID_COMPUTE_DEVICE_POLICIES)}."
        )
    return policy


def get_deployment_target() -> str:
    """Return the configured deployment target used by packaging/docs."""
    return os.getenv(DEPLOYMENT_TARGET_ENV_VAR, "cpu").strip().lower()


def get_best_device(options=None) -> TorchDevice:
    """Return the best available torch device for the current runtime policy."""
    requested_options = list(options or DEFAULT_DEVICE_ORDER)
    policy = get_compute_device_policy()

    if policy == "cpu":
        if "cpu" not in requested_options:
            raise ValueError(
                "CPU-only runtime policy requested, but 'cpu' is not in the "
                f"allowed device options: {requested_options}."
            )
        return torch.device("cpu")

    if torch.cuda.is_available() and "cuda" in requested_options:
        return torch.device("cuda")

    if (
        hasattr(torch.backends, "mps")
        and torch.backends.mps.is_available()
        and "mps" in requested_options
    ):
        return torch.device("mps")

    if "cpu" in requested_options:
        return torch.device("cpu")

    raise ValueError(f"No supported device found for options: {requested_options}.")
