"""Trusted runtime hooks for KIVA session lifecycle events."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .backend import KivaBackend
from .database import KivaDatabase
from .errors import NotFoundError


def mark_disconnected_kiva_session(session_id: str) -> dict[str, Any] | None:
    """Mark an unfinished session abandoned when its WebRTC client disconnects.

    Terminal session states are preserved by ``SessionService.mark_disconnected``.
    This function is intended only for trusted server runtime callbacks.
    """
    default_path = Path.home() / "riverst-data" / "kiva.sqlite3"
    database_path = Path(os.getenv("KIVA_DB_PATH", str(default_path)))
    if not database_path.is_file():
        return None
    try:
        return KivaBackend(KivaDatabase(database_path)).mark_disconnected_session(session_id)
    except NotFoundError:
        # The EventHandlerManager also serves ordinary, non-KIVA Riverst sessions.
        return None


def _kiva_backend() -> KivaBackend | None:
    default_path = Path.home() / "riverst-data" / "kiva.sqlite3"
    database_path = Path(os.getenv("KIVA_DB_PATH", str(default_path)))
    return KivaBackend(KivaDatabase(database_path)) if database_path.is_file() else None


def mark_running_kiva_session(session_id: str) -> dict[str, Any] | None:
    """Mark a KIVA session running when its WebRTC client connects (trusted runtime callback).
    No-ops for ordinary non-KIVA Riverst sessions (their id isn't in kiva_session)."""
    backend = _kiva_backend()
    if backend is None:
        return None
    try:
        return backend.mark_running_session(session_id)
    except NotFoundError:
        return None


def finalize_kiva_session(session_id: str, completed: bool) -> dict[str, Any] | None:
    """Finalize a KIVA session (completed if the flow reached a terminal node, else abandoned) when
    its client disconnects. No-ops for non-KIVA sessions."""
    backend = _kiva_backend()
    if backend is None:
        return None
    try:
        return backend.finalize_session(session_id, completed)
    except NotFoundError:
        return None
