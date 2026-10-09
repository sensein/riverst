import os
import json
from datetime import datetime, timedelta
from typing import List, Optional, Set
from pathlib import Path

from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from google.auth.transport import requests
from google.oauth2 import id_token
from jose import JWTError, jwt
from loguru import logger

# Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
SECRET_KEY = os.getenv("SECRET_KEY")
ENABLE_GOOGLE_AUTH = os.getenv("ENABLE_GOOGLE_AUTH", "true").lower() == "true"
if not SECRET_KEY:
    raise ValueError(
        "SECRET_KEY environment variable is not set. Please configure it before starting the application."
    )
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Security scheme
security = HTTPBearer()

# Path to user whitelist and rejection logs
BASE_DIR = Path(__file__).parent
USERS_FILE = BASE_DIR / "authorized_users.json"
REJECTION_LOG_FILE = BASE_DIR / "logs" / "rejected_logins.json"

# Ensure directories exist
USERS_FILE.parent.mkdir(exist_ok=True)
REJECTION_LOG_FILE.parent.mkdir(exist_ok=True)


ROLE_RESEARCHER = "researcher"
ROLE_TEACHER = "teacher"


def _load_users_file() -> dict:
    """Read the allowlist file, creating the default one if missing."""
    if not USERS_FILE.exists():
        # Create default authorized users file
        default_users = {
            "authorized_emails": [
                # Add your authorized email addresses here
                "example@gmail.com"
            ]
        }
        with USERS_FILE.open("w") as f:
            json.dump(default_users, f, indent=2)
        return default_users

    try:
        with USERS_FILE.open("r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading authorized users: {e}")
        return {}


def load_authorized_users() -> Set[str]:
    """Load every email allowed to sign in: researchers (``authorized_emails``) and teachers (``teacher_emails``)."""
    data = _load_users_file()
    return set(data.get("authorized_emails", [])) | set(data.get("teacher_emails", []))


def get_roles(email: str) -> List[str]:
    """Return the roles for an email from the allowlist file.

    Args:
        email: The signed-in user's email.

    Returns:
        List[str]: ``researcher`` if listed in ``authorized_emails`` (full access, as before),
        ``teacher`` if listed in ``teacher_emails``. Empty if the email is in neither list.
    """
    data = _load_users_file()
    roles = []
    if email in set(data.get("authorized_emails", [])):
        roles.append(ROLE_RESEARCHER)
    if email in set(data.get("teacher_emails", [])):
        roles.append(ROLE_TEACHER)
    return roles


def log_rejected_login(email: str, name: str, reason: str):
    """Log rejected login attempts."""
    rejection_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "email": email,
        "name": name,
        "reason": reason,
    }

    # Load existing logs or create new list
    logs = []
    if REJECTION_LOG_FILE.exists():
        try:
            with REJECTION_LOG_FILE.open("r") as f:
                logs = json.load(f)
        except Exception as e:
            logger.error(f"Error loading rejection logs: {e}")

    # Add new entry and save
    logs.append(rejection_entry)
    try:
        with REJECTION_LOG_FILE.open("w") as f:
            json.dump(logs, f, indent=2)
        logger.warning(f"Rejected login attempt from {email}: {reason}")
    except Exception as e:
        logger.error(f"Error saving rejection log: {e}")


def is_google_auth_enabled() -> bool:
    """Check if Google authentication is enabled."""
    return ENABLE_GOOGLE_AUTH


def verify_google_token(token: str) -> dict:
    """Verify Google OAuth token and return user info."""
    if not ENABLE_GOOGLE_AUTH:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google authentication is currently disabled",
        )

    try:
        # Verify the token with Google
        idinfo = id_token.verify_oauth2_token(
            token, requests.Request(), GOOGLE_CLIENT_ID
        )

        # Verify the issuer
        if idinfo["iss"] not in ["accounts.google.com", "https://accounts.google.com"]:
            raise ValueError("Wrong issuer.")

        return idinfo
    except ValueError as e:
        logger.error(f"Token verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Verify JWT token and return user data."""
    try:
        payload = jwt.decode(
            credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM]
        )
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
            )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )


def create_bypass_token() -> tuple[str, dict]:
    """Create a bypass token when Google auth is disabled."""
    roles = [ROLE_RESEARCHER, ROLE_TEACHER]
    bypass_data = {
        "sub": "dev@localhost",
        "name": "Development User",
        "bypass": True,
        "roles": roles,
    }
    user_data = {"email": "dev@localhost", "name": "Development User", "roles": roles}
    access_token = create_access_token(
        bypass_data, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return access_token, user_data


def get_current_user(token_data: dict = Depends(verify_token)) -> dict:
    """Get current authenticated user."""
    return token_data


def token_roles(token_data: dict) -> List[str]:
    """Roles carried by a token. Tokens issued before roles existed count as researcher, as they did then."""
    return token_data.get("roles", [ROLE_RESEARCHER])


def _require_role(role: str):
    def dependency(current_user: dict = Depends(get_current_user)) -> dict:
        if role not in token_roles(current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This page isn't available for your account.",
            )
        return current_user

    return dependency


require_teacher = _require_role(ROLE_TEACHER)
require_researcher = _require_role(ROLE_RESEARCHER)
