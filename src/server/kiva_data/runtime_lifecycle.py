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
