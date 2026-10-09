"""Saves the tutor's word decisions (flow state) so they survive the end of a session."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Union

from loguru import logger

SNAPSHOT_FILE = "flow_state.json"
SESSION_DIR_KEY = "session_dir"


def _user_fields(user_state: Dict[str, Any]) -> Dict[str, Any]:
    return {
        k: v for k, v in user_state.items() if k.startswith("vocab_") or k == "index"
    }


def write_snapshot(session_dir: Optional[Union[str, Path]], flow_manager: Any) -> None:
    """Atomically write ``flow_state.json`` for a session. Never raises.

    Args:
        session_dir: The session folder. Nothing is written when it is missing.
        flow_manager: The pipecat FlowManager (or None when flows are off).
    """
    if not session_dir or flow_manager is None:
        return
    try:
        user_state = flow_manager.state.get("user", {})
        snapshot = {
            "current_node": flow_manager.current_node,
            "user": _user_fields(user_state),
            "vocab_override": user_state.get("vocab_override") or [],
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        target = Path(session_dir) / SNAPSHOT_FILE
        tmp = target.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
        os.replace(tmp, target)
    except Exception as e:
        logger.error(f"Could not write flow state snapshot: {e}")


def read_snapshot(session_dir: Union[str, Path]) -> Optional[Dict[str, Any]]:
    """Load ``flow_state.json``, or None if it is missing or unreadable."""
    path = Path(session_dir) / SNAPSHOT_FILE
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except Exception as e:
        logger.error(f"Could not read flow state snapshot {path}: {e}")
        return None
