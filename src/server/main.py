import argparse
import asyncio
import datetime
import json
import math
import os
import re
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import timedelta

import uvicorn
import uvloop
from dotenv import load_dotenv
from fastapi import (
    BackgroundTasks,
    FastAPI,
    File as FastAPIFile,
    Form,
    Request,
    Query,
    Body,
    Depends,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger

from bot.core.bot_runner import run_bot
from pipecat.transports.smallwebrtc.connection import (
    IceServer,
    SmallWebRTCConnection,
)
from authorization.auth import (
    verify_google_token,
    load_authorized_users,
    log_rejected_login,
    create_access_token,
    create_bypass_token,
    get_current_user,
    is_google_auth_enabled,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)

# Load environment variables
load_dotenv(override=True)
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

app = FastAPI()

BASE_SESSION_DIR = Path(__file__).parent

(BASE_SESSION_DIR / "sessions").mkdir(exist_ok=True)
app.mount(
    "/api/sessions",
    StaticFiles(directory=BASE_SESSION_DIR / "sessions"),
    name="sessions",
)

AVATAR_UPLOADS_BASE = BASE_SESSION_DIR / "uploads"
AVATAR_UPLOADS_BASE.mkdir(exist_ok=True)
app.mount(
    "/uploads",
    StaticFiles(directory=AVATAR_UPLOADS_BASE),
    name="uploads",
)

# Enable CORS for all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Track active WebRTC connections
pcs_map: Dict[str, SmallWebRTCConnection] = {}

# ICE servers for WebRTC connection
ice_servers = [
    IceServer(urls="stun:stun.l.google.com:19302"),
    IceServer(urls="stun:stun.l.google.com:5349"),
    IceServer(urls="stun:stun1.l.google.com:3478"),
    IceServer(urls="stun:stun1.l.google.com:5349"),
    IceServer(urls="stun:stun2.l.google.com:19302"),
    IceServer(urls="stun:stun2.l.google.com:5349"),
    IceServer(urls="stun:stun3.l.google.com:3478"),
    IceServer(urls="stun:stun3.l.google.com:5349"),
    IceServer(urls="stun:stun4.l.google.com:19302"),
    IceServer(urls="stun:stun4.l.google.com:5349"),
]

# Optionally add TURN server if env vars are present
turn_url = os.getenv("TURN_URL")
turn_username = os.getenv("TURN_USERNAME")
turn_credential = os.getenv("TURN_CREDENTIAL")

if turn_url and turn_username and turn_credential:
    ice_servers.append(
        IceServer(urls=turn_url, username=turn_username, credential=turn_credential)
    )


# Authentication routes
@app.get("/api/auth/status")
async def auth_status() -> JSONResponse:
    """Get authentication status and configuration."""
    return JSONResponse(
        {
            "google_auth_enabled": is_google_auth_enabled(),
            "auth_methods": ["google"] if is_google_auth_enabled() else ["bypass"],
        }
    )


@app.post("/api/auth/bypass")
async def bypass_auth() -> JSONResponse:
    """Bypass authentication when Google auth is disabled."""
    if is_google_auth_enabled():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bypass authentication is not available when Google auth is enabled",
        )

    # Create bypass token
    # Create bypass token
    access_token, user_data = create_bypass_token()

    logger.info("Bypass authentication used")

    return JSONResponse(
        {
            "access_token": access_token,
            "token_type": "bearer",
            "user": user_data,
        }
    )


@app.post("/api/auth/google")
async def google_auth(request: Request) -> JSONResponse:
    """Authenticate with Google OAuth token."""
    data = await request.json()
    google_token = data.get("token")

    if not google_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Google token required"
        )

    # Verify Google token
    user_info = verify_google_token(google_token)
    email = user_info.get("email")
    name = user_info.get("name", "Unknown")

    # Check if user is authorized
    authorized_users = load_authorized_users()
    if email not in authorized_users:
        log_rejected_login(email, name, "User not in authorized list")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Your account is not authorized to access this application.",
        )

    # Create JWT token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": email, "name": name}, expires_delta=access_token_expires
    )

    logger.info(f"Successful login: {email}")

    return JSONResponse(
        {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {"email": email, "name": name},
        }
    )


@app.get("/api/auth/me")
async def get_me(current_user: dict = Depends(get_current_user)) -> JSONResponse:
    """Get current user information."""
    return JSONResponse(
        {"email": current_user.get("sub"), "name": current_user.get("name")}
    )


@app.post("/api/session")
async def create_session(
    config: dict = Body(...), current_user: dict = Depends(get_current_user)
) -> JSONResponse:
    """Creates a new session and stores its config.

    Args:
        config (dict): Configuration dictionary.

    Returns:
        JSONResponse: Contains the newly generated session ID.
    """
    if not config.get("user_id"):
        return JSONResponse(status_code=400, content={"error": "User ID is required"})
    user_id = config["user_id"]
    session_id = (
        user_id
        + "__"
        + datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        + "_"
        + str(uuid.uuid4())[:8]
    )
    session_dir = BASE_SESSION_DIR / Path("sessions") / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    config_path = session_dir / "config.json"
    with config_path.open("w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    logger.info(f"Session created: {session_id}")
    return JSONResponse({"session_id": session_id})


@app.post("/api/offer")
async def offer(
    request: Request,
    background_tasks: BackgroundTasks,
    session_id: str = Query(default=None),
) -> JSONResponse:
    """Handles WebRTC offers and initializes connections.

    Args:
        request (Request): Incoming HTTP request with SDP data.
        background_tasks (BackgroundTasks): Background task manager.
        session_id (str): ID of the associated session.

    Returns:
        JSONResponse: SDP answer from the WebRTC connection.
    """
    data = await request.json()
    pc_id: Optional[str] = data.get("pc_id")

    session_dir = (BASE_SESSION_DIR / Path("sessions") / session_id).resolve()
    config_path = Path(os.path.join(session_dir, "config.json"))

    try:
        with config_path.open("r", encoding="utf-8") as f:
            config = json.load(f)
    except FileNotFoundError:
        logger.error(f"Config file not found at {config_path}")
        return JSONResponse(status_code=404, content={"error": "Config file not found"})
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding config file: {e}")
        return JSONResponse(
            status_code=400, content={"error": "Invalid config file format"}
        )

    if pc_id and pc_id in pcs_map:
        pipecat_connection = pcs_map[pc_id]
        logger.info(f"Reusing existing connection for pc_id: {pc_id}")
        await pipecat_connection.renegotiate(
            sdp=data["sdp"],
            type=data["type"],
            restart_pc=data.get("restart_pc", False),
        )
    else:
        pipecat_connection = SmallWebRTCConnection(ice_servers)
        await pipecat_connection.initialize(sdp=data["sdp"], type=data["type"])

        @pipecat_connection.event_handler("closed")
        async def handle_disconnected(webrtc_connection: SmallWebRTCConnection):
            logger.info(f"Closing connection for pc_id: {webrtc_connection.pc_id}")
            pcs_map.pop(webrtc_connection.pc_id, None)

        background_tasks.add_task(
            run_bot, pipecat_connection, config=config, session_dir=str(session_dir)
        )

    answer = pipecat_connection.get_answer()
    pcs_map[answer["pc_id"]] = pipecat_connection
    return JSONResponse(answer)


@app.get("/api/health")
async def health_check() -> JSONResponse:
    """Health check endpoint.

    Returns:
        JSONResponse: Service status message.
    """
    return JSONResponse({"status": "ok"})


@app.get("/api/avatars")
async def get_avatars() -> JSONResponse:
    """Returns a list of available avatars."""
    file_path = BASE_SESSION_DIR / "assets" / "avatars.json"
    try:
        with file_path.open("r", encoding="utf-8") as f:
            avatars = json.load(f)
        return JSONResponse(content=avatars)
    except Exception as e:
        logger.error(f"Error loading avatars: {e}")
        return JSONResponse(
            status_code=500, content={"error": "Unable to load avatars"}
        )


MAX_AVATAR_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_AVATARS_PER_USER = 10
_UUID_GLB_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.glb$"
)


def _email_to_dirname(email: str) -> str:
    """Convert an email to a filesystem/URL-safe directory name."""
    return email.replace("@", "_at_")


def _user_upload_dir(email: str) -> Path:
    """Returns the upload directory for a given user, creating it if needed."""
    user_dir = AVATAR_UPLOADS_BASE / _email_to_dirname(email)
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def _extract_glb_external_uris(content: bytes) -> list[str]:
    """Parse the JSON chunk of a GLB file and return any external URI values found.

    GLB layout: 12-byte file header, then chunks of (4-byte length + 4-byte type + data).
    The first chunk is always the JSON chunk (type 0x4E4F534A).
    """
    if len(content) < 20:
        return []

    chunk_length = int.from_bytes(content[12:16], "little")
    chunk_type = int.from_bytes(content[16:20], "little")

    if chunk_type != 0x4E4F534A:  # "JSON"
        return []

    json_bytes = content[20 : 20 + chunk_length]
    try:
        gltf = json.loads(json_bytes)
    except Exception as e:
        logger.warning(f"Failed to parse GLB JSON chunk: {e}")
        return []

    external_uris: list[str] = []

    def _collect(obj: object) -> None:
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key == "uri" and isinstance(value, str):
                    if "://" in value and not value.startswith("data:"):
                        external_uris.append(value)
                else:
                    _collect(value)
        elif isinstance(obj, list):
            for item in obj:
                _collect(item)

    _collect(gltf)
    return external_uris


@app.post("/api/upload-avatar")
async def upload_avatar(
    file: UploadFile = FastAPIFile(...),
    gender: str = Form(default="masculine"),
    current_user: dict = Depends(get_current_user),
) -> JSONResponse:
    """Accepts a GLB file upload, validates it, and saves to the user's upload directory."""
    if gender not in ("masculine", "feminine"):
        gender = "masculine"

    if not file.filename or not file.filename.lower().endswith(".glb"):
        raise HTTPException(status_code=400, detail="Only .glb files are accepted.")

    content = await file.read()

    if len(content) > MAX_AVATAR_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {MAX_AVATAR_FILE_SIZE // (1024 * 1024)} MB.",
        )

    if len(content) < 12 or content[:4] != b"glTF":
        raise HTTPException(
            status_code=400,
            detail="Invalid GLB file. The file does not have a valid glTF binary header.",
        )

    external_uris = _extract_glb_external_uris(content)
    if external_uris:
        logger.warning(
            f"Rejected GLB upload from {current_user['sub']}: "
            f"contains {len(external_uris)} external URI(s): {external_uris[:3]}"
        )
        raise HTTPException(
            status_code=400,
            detail="GLB file contains external URI references, which are not permitted.",
        )

    user_dir = _user_upload_dir(current_user["sub"])
    existing_count = sum(1 for f in user_dir.iterdir() if f.suffix == ".glb")
    if existing_count >= MAX_AVATARS_PER_USER:
        raise HTTPException(
            status_code=400,
            detail=f"Upload limit reached. Maximum {MAX_AVATARS_PER_USER} avatars per user.",
        )

    file_id = str(uuid.uuid4())
    unique_filename = f"{file_id}.glb"

    with open(user_dir / unique_filename, "wb") as f:
        f.write(content)

    with open(user_dir / f"{file_id}.json", "w") as f:
        json.dump({"gender": gender}, f)

    encoded_email = _email_to_dirname(current_user["sub"])
    model_url = f"/uploads/{encoded_email}/{unique_filename}"
    logger.info(f"Avatar uploaded by {current_user['sub']}: {unique_filename} ({len(content)} bytes)")

    return JSONResponse(content={"modelUrl": model_url})


@app.delete("/api/upload-avatar/{filename}")
async def delete_avatar(
    filename: str,
    current_user: dict = Depends(get_current_user),
) -> JSONResponse:
    """Deletes a user-uploaded avatar. Only the owning user's UUID-named files can be deleted."""
    if not _UUID_GLB_RE.match(filename):
        raise HTTPException(
            status_code=400,
            detail="Invalid filename. Only user-uploaded avatars can be deleted.",
        )

    user_dir = _user_upload_dir(current_user["sub"])
    file_path = user_dir / filename

    try:
        file_path.resolve().relative_to(user_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filename.")

    stem = filename[:-4]
    sidecar = user_dir / f"{stem}.json"

    glb_deleted = False
    json_deleted = False

    if file_path.exists():
        file_path.unlink()
        glb_deleted = True
    if sidecar.exists():
        sidecar.unlink()
        json_deleted = True

    if not glb_deleted and not json_deleted:
        raise HTTPException(status_code=404, detail="Avatar file not found.")

    logger.info(
        f"Avatar deleted by {current_user['sub']}: {filename} "
        f"(glb={glb_deleted}, json={json_deleted})"
    )
    return JSONResponse(content={"deleted": filename})


@app.get("/api/my-avatars")
async def get_my_avatars(
    current_user: dict = Depends(get_current_user),
) -> JSONResponse:
    """Returns the list of avatars uploaded by the current user, with gender metadata."""
    encoded_email = _email_to_dirname(current_user["sub"])
    user_dir = AVATAR_UPLOADS_BASE / encoded_email

    if not user_dir.exists():
        return JSONResponse(content=[])

    glb_stems = {
        f.stem for f in user_dir.iterdir()
        if f.suffix == ".glb" and _UUID_GLB_RE.match(f.name)
    }
    json_stems = {
        f.stem for f in user_dir.iterdir()
        if f.suffix == ".json" and _UUID_GLB_RE.match(f.stem + ".glb")
    }
    all_stems = sorted(glb_stems | json_stems)

    avatars = []
    for stem in all_stems:
        has_glb = stem in glb_stems
        has_json = stem in json_stems
        corrupted = not (has_glb and has_json)

        if corrupted:
            missing = ".glb" if has_json else ".json"
            logger.warning(
                f"Corrupted avatar pair for {current_user['sub']}: {stem} missing {missing}"
            )

        gender = "masculine"
        if has_json:
            try:
                gender = json.load((user_dir / f"{stem}.json").open())["gender"]
            except Exception as e:
                logger.warning(f"Failed to read gender sidecar {stem}.json: {e}")

        avatars.append({
            "modelUrl": f"/uploads/{encoded_email}/{stem}.glb",
            "gender": gender,
            "corrupted": corrupted,
        })

    return JSONResponse(content=avatars)


@app.get("/api/resources")
async def get_resources(activity: str = Query(None)) -> JSONResponse:
    """Returns a list of available resources for activities."""
    if activity:
        # Get resources for specific activity
        resources_dir = BASE_SESSION_DIR / "activities" / activity / "resources"
        if not resources_dir.is_dir():
            logger.warning(f"Resources directory not found for activity: {activity}")
            return JSONResponse(
                status_code=404, content={"error": "Resources directory not found"}
            )

        try:
            resources = []
            for resource_file in resources_dir.iterdir():
                if resource_file.is_file() and resource_file.suffix == ".json":
                    resource_name = resource_file.stem
                    path = f"./activities/{activity}/resources/{resource_file.name}"

                    # Try to read the resource title from the JSON file
                    try:
                        with resource_file.open("r", encoding="utf-8") as f:
                            resource_data = json.load(f)
                            title = (
                                resource_data.get("reading_context", {})
                                .get("key_information", {})
                                .get("name", resource_name.replace("_", " ").title())
                            )
                    except Exception:
                        title = resource_name.replace("_", " ").title()

                    resources.append(
                        {"id": resource_name, "title": title, "path": path}
                    )

            return JSONResponse(content=resources)
        except Exception as e:
            logger.error(f"Error loading resources for activity {activity}: {e}")
            return JSONResponse(
                status_code=500, content={"error": "Unable to load resources"}
            )
    else:
        # Return empty list if no activity specified
        return JSONResponse(content=[])


@app.get("/api/resources/indices")
async def get_resource_indices(resourcePath: str = Query(...)) -> JSONResponse:
    """Returns the maximum number of indices for a specific resource."""
    try:
        # Convert relative path to absolute path
        resource_file_path = BASE_SESSION_DIR / resourcePath.lstrip("./")

        if not resource_file_path.exists():
            return JSONResponse(
                status_code=404, content={"error": "Resource file not found"}
            )

        with resource_file_path.open("r", encoding="utf-8") as f:
            resource_data = json.load(f)
            reading_context = resource_data.get("reading_context", {})
            indexable_by = reading_context.get("indexable_by")

            if not indexable_by:
                return JSONResponse(
                    status_code=400, content={"error": "Resource is not indexable"}
                )

            # Get the indexable content array
            index_array = reading_context.get(indexable_by, [])
            max_indices = len(index_array)

        return JSONResponse(
            content={"indexType": indexable_by, "maxIndices": max_indices}
        )

    except Exception as e:
        logger.error(f"Error loading resource indices: {e}")
        return JSONResponse(
            status_code=500, content={"error": "Unable to load resource indices"}
        )


@app.get("/api/activities")
async def get_activities() -> JSONResponse:
    """Fetches predefined activity groups from file.

    Returns:
        JSONResponse: Activity group definitions.
    """
    file_path = BASE_SESSION_DIR / "assets" / "activity_groups.json"
    try:
        with file_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return JSONResponse(content=data)
    except Exception as e:
        logger.error(f"Error loading activities: {e}")
        return JSONResponse(
            status_code=500, content={"error": "Unable to load activities"}
        )


@app.get("/api/activities/{activity_name}/session_config")
async def get_activity_settings(activity_name: str) -> JSONResponse:
    """Loads activity session configuration JSON and filters services by available API keys.

    Args:
        activity_name (str): Name of the activity.

    Returns:
        JSONResponse: Filtered JSON configuration.
    """
    file_path = BASE_SESSION_DIR / "activities" / activity_name / "session_config.json"

    if not file_path.is_file():
        logger.error(f"Session config file not found: {file_path}")
        return JSONResponse(
            status_code=404, content={"error": "Session config file not found"}
        )

    try:
        with file_path.open("r", encoding="utf-8") as f:
            config = json.load(f)

        has_openai = os.getenv("OPENAI_API_KEY") is not None
        has_google = os.getenv("GOOGLE_API_KEY") is not None

        options_props: Dict[str, Any] = (
            config.get("properties", {}).get("options", {}).get("properties", {})
        )

        for key, model_list in {
            "llm_type": ["openai", "openai_gpt-realtime", "gemini"],
            "stt_type": ["openai"],
            "tts_type": ["openai"],
        }.items():
            if key in options_props and "enum" in options_props[key]:
                allowed = options_props[key]["enum"]
                filtered = [
                    m
                    for m in allowed
                    if not (
                        (not has_openai and m in ["openai", "openai_gpt-realtime"])
                        or (not has_google and m == "gemini")
                    )
                ]
                options_props[key]["enum"] = filtered

                if (
                    "default" in options_props[key]
                    and options_props[key]["default"] not in filtered
                ):
                    if filtered:
                        options_props[key]["default"] = filtered[0]
                    else:
                        logger.warning(
                            f"No valid options left for '{key}' after filtering."
                        )
                        del options_props[key]

        return JSONResponse(content=config)

    except Exception as e:
        logger.error(f"Error reading or processing settings file: {e}")
        return JSONResponse(
            status_code=500, content={"error": "Unable to load settings"}
        )


@app.get("/api/sessions")
async def list_sessions(current_user: dict = Depends(get_current_user)) -> JSONResponse:
    """Lists all available sessions."""
    session_root = BASE_SESSION_DIR / "sessions"
    if not session_root.is_dir():
        return JSONResponse(content=[], status_code=200)
    valid_session_ids = []
    for session_dir in session_root.iterdir():
        if not session_dir.is_dir():
            continue
        audio_dir = session_dir / "audios"
        json_dir = session_dir / "json"
        if not (audio_dir.is_dir() and json_dir.is_dir()):
            continue
        wav_files = list(audio_dir.glob("*.wav"))
        if not wav_files:
            continue
        all_json_exist = all(
            (json_dir / (wav_file.stem + ".json")).exists() for wav_file in wav_files
        )
        if all_json_exist:
            valid_session_ids.append(session_dir.name)
    return JSONResponse(content=valid_session_ids)


@app.post("/api/session/add_device_fingerprint")
async def add_device_fingerprint(data: dict = Body(...)) -> JSONResponse:
    """
    Adds a device fingerprint to the session's config.json.
    Expects JSON body: { "sessionid": ..., "devicefingerprint": ... }
    """
    session_id = data.get("sessionid")
    device_fingerprint = data.get("devicefingerprint")
    if not session_id or not device_fingerprint:
        return JSONResponse(
            status_code=400,
            content={"error": "sessionid and devicefingerprint are required"},
        )

    session_dir = BASE_SESSION_DIR / "sessions" / session_id
    config_path = session_dir / "config.json"
    if not config_path.is_file():
        return JSONResponse(content={"error": "Config file not found"}, status_code=404)

    try:
        with config_path.open("r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        return JSONResponse(
            status_code=500, content={"error": f"Failed to read config: {str(e)}"}
        )

    # Add deviceFingerprint to array
    fingerprints = config.get("deviceFingerprints", [])
    if device_fingerprint not in fingerprints:
        fingerprints.append(device_fingerprint)
        config["deviceFingerprints"] = fingerprints
        try:
            with config_path.open("w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print("error", e)
            return JSONResponse(
                status_code=500, content={"error": f"Failed to write config: {str(e)}"}
            )

    return JSONResponse(content={"success": True})


@app.get("/api/session_config/{session_id}")
async def get_session_config(session_id: str) -> JSONResponse:
    """Fetches the configuration for a specific session."""
    session_dir = BASE_SESSION_DIR / "sessions" / session_id
    config_path = session_dir / "config.json"
    if not config_path.is_file():
        return JSONResponse(content={"error": "Config file not found"}, status_code=404)
    with config_path.open("r", encoding="utf-8") as f:
        config = json.load(f)
    return JSONResponse(content=config)


def clean_for_json(obj):
    if isinstance(obj, dict):
        return {k: clean_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_for_json(i) for i in obj]
    elif isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return obj


@app.get("/api/check_session_ended/{session_id}")
def check_session_ended(session_id: str):
    """
    Checks if a session is ended by looking for 'prolific_id' in the session's config.json.
    Returns {"ended": True} if prolific_id is present, else {"ended": False}.
    """
    session_dir = BASE_SESSION_DIR / "sessions" / session_id
    config_path = session_dir / "config.json"

    if not config_path.is_file():
        raise HTTPException(
            status_code=404, detail=f"Config file not found: {config_path}"
        )

    try:
        with config_path.open("r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load config: {str(e)}")

    prolific_id = config.get("prolific_id")
    if config.get("short_term_memory", False):
        return JSONResponse(
            content={"ended": prolific_id is not None, "prolific_id": prolific_id}
        )
    return JSONResponse(content={"ended": False})


@app.get("/api/end_session/{session_id}")
def end_session(session_id: str):
    """
    Ends a session by generating a prolific_id (UUID), adding it to the session's config.json, and saving it.
    Returns the prolific_id as JSON.
    Raises 404 if the config file does not exist.
    """
    session_dir = BASE_SESSION_DIR / "sessions" / session_id
    config_path = session_dir / "config.json"

    if not config_path.is_file():
        raise HTTPException(
            status_code=404, detail=f"Config file not found: {config_path}"
        )

    try:
        with config_path.open("r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load config: {str(e)}")

    prolific_id = str(uuid.uuid4())
    config["prolific_id"] = prolific_id

    try:
        with config_path.open("w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write config: {str(e)}")

    return JSONResponse(content={"prolific_id": prolific_id})


@app.get("/api/audiobooks")
async def get_audiobooks() -> JSONResponse:
    """
    Returns a list of all audiobooks and their chapters.
    Each book contains: key, title, author, chapters (each with key, chapterTitle, bookKey, chapter).
    """
    resources_dir = BASE_SESSION_DIR / "activities" / "audiobook" / "resources"
    if not resources_dir.is_dir():
        return JSONResponse(
            status_code=404, content={"error": "Resources directory not found"}
        )

    books = []
    for book_dir in sorted(resources_dir.iterdir()):
        if not book_dir.is_dir():
            continue
        book_key = book_dir.name
        chapter_files = sorted(
            [f for f in book_dir.iterdir() if f.is_file() and f.suffix == ".json"],
            key=lambda x: int(x.stem) if x.stem.isdigit() else x.stem,
        )
        if not chapter_files:
            continue
        # Read first chapter file for book metadata
        try:
            with chapter_files[0].open("r", encoding="utf-8") as f:
                first_chapter_data = json.load(f)
            title = first_chapter_data.get("title", book_key.replace("_", " ").title())
            author = first_chapter_data.get("author", "Unknown")
        except Exception:
            title = book_key.replace("_", " ").title()
            author = "Unknown"

        chapters = []
        for chapter_file in chapter_files:
            chapter_key = chapter_file.stem
            try:
                with chapter_file.open("r", encoding="utf-8") as f:
                    chapter_data = json.load(f)
                chapter_title = chapter_data.get(
                    "chapterTitle", f"Chapter {chapter_key}"
                )
                chapter_content = chapter_data.get("chapters", [])
            except Exception:
                chapter_title = f"Chapter {chapter_key}"
                chapter_content = []
            chapters.append(
                {
                    "key": chapter_key,
                    "chapterTitle": chapter_title,
                    "bookKey": book_key,
                    "chapter": chapter_content,
                }
            )
        books.append(
            {"key": book_key, "title": title, "author": author, "chapters": chapters}
        )
    return JSONResponse(content=books)


@app.get("/api/audiobook_info")
async def get_audiobook_info(
    book: str = Query(..., description="Book directory name"),
    chapter: str = Query(..., description="Chapter number as string"),
) -> JSONResponse:
    """
    Returns audiobook info for a given book and chapter.
    """
    base_dir = BASE_SESSION_DIR / "activities" / "audiobook" / "resources" / book
    file_path = base_dir / f"{chapter}.json"

    print("file_path", file_path)

    if not file_path.is_file():
        print("A")
        return JSONResponse(
            status_code=404,
            content={
                "error": f"Audiobook info not found for book '{book}', chapter '{chapter}'"
            },
        )
    try:
        with file_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return JSONResponse(content=data)
    except Exception as e:
        print("B", e)
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to load audiobook info: {str(e)}"},
        )


@app.get("/api/session/{session_id}")
async def get_session_data(
    session_id: str, current_user: dict = Depends(get_current_user)
) -> JSONResponse:
    """Fetches the data for a specific session."""
    session_dir = BASE_SESSION_DIR / "sessions" / session_id
    audio_dir = session_dir / "audios"
    json_dir = session_dir / "json"

    if not (audio_dir.is_dir() and json_dir.is_dir()):
        return JSONResponse(content={"error": "Session not found"}, status_code=404)

    results = []
    # List all json files in the json dir
    for json_file in sorted(json_dir.glob("*.json")):
        base_name = json_file.stem
        wav_file = audio_dir / (base_name + ".wav")
        if not wav_file.exists():
            continue
        try:
            with open(json_file, "r") as f:
                data = json.load(f)
        except Exception:
            continue  # skip unreadable files
        # Return audio file as relative path (or signed URL if preferred)
        data["audio_file"] = f"/sessions/{session_id}/audios/{base_name}.wav"
        results.append(data)

    metrics = {}
    metrics_path = session_dir / "metrics_summary.json"
    if metrics_path.exists():
        try:
            with open(metrics_path, "r", encoding="utf-8") as f:
                metrics = json.load(f)
        except Exception:
            metrics = {"error": "Could not read metrics_summary.json"}

    return JSONResponse(
        content=clean_for_json({"data": results, "metrics_summary": metrics})
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles app startup and cleanup.

    Args:
        app (FastAPI): The FastAPI app instance.
    """
    yield
    coros = [pc.close() for pc in pcs_map.values()]
    await asyncio.gather(*coros)
    pcs_map.clear()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WebRTC demo server")
    parser.add_argument(
        "--host", default="0.0.0.0", help="Server hostname (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", type=int, default=7860, help="Port number (default: 7860)"
    )
    parser.add_argument(
        "--verbose", "-v", action="count", help="Enable verbose logging"
    )
    parser.add_argument(
        "--ssl-certfile",
        type=str,
        default=None,
        help="Path to SSL certificate (optional)",
    )
    parser.add_argument(
        "--ssl-keyfile", type=str, default=None, help="Path to SSL key (optional)"
    )
    args = parser.parse_args()

    logger.remove()

    uvicorn_kwargs = {
        "app": app,
        "host": args.host,
        "port": args.port,
    }

    # Only add SSL if both files are provided
    if args.ssl_certfile and args.ssl_keyfile:
        uvicorn_kwargs["ssl_certfile"] = os.path.expanduser(args.ssl_certfile)
        uvicorn_kwargs["ssl_keyfile"] = os.path.expanduser(args.ssl_keyfile)
        logger.add(sys.stderr, level="TRACE" if args.verbose else "DEBUG")
        # logger.add(sys.stderr, level="ERROR")
    else:
        logger.add(sys.stderr, level="TRACE" if args.verbose else "DEBUG")

    uvicorn.run(**uvicorn_kwargs)
