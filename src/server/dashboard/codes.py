"""Student codes, stable student keys and opaque record IDs."""

import secrets
from typing import Optional

# No 0/O or 1/I/L, so codes are easy to read aloud and type.
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 6


def generate_code() -> str:
    """Generate a random student code.

    Returns:
        str: Six characters from ``ALPHABET``.
    """
    return "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))


def normalize_code(raw: Optional[str]) -> Optional[str]:
    """Normalize user-typed input into a student code.

    Args:
        raw: What the student typed or what the link carried.

    Returns:
        Optional[str]: The uppercased code without whitespace, or None if it can't be a valid code.
    """
    if not raw or not isinstance(raw, str):
        return None
    code = "".join(raw.split()).upper()
    if len(code) != CODE_LENGTH or any(ch not in ALPHABET for ch in code):
        return None
    return code


def generate_user_key() -> str:
    """Generate the stable, opaque ``user_id`` used for a student's sessions.

    Returns:
        str: ``stu_`` followed by 16 hex characters. It never contains the name or the code.
    """
    return "stu_" + secrets.token_hex(8)


def new_id(prefix: str) -> str:
    """Generate an opaque record ID.

    Args:
        prefix: Short type marker, for example ``s`` for students.

    Returns:
        str: ``<prefix>_<random url-safe text>``.
    """
    return f"{prefix}_{secrets.token_urlsafe(9)}"
