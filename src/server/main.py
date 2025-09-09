import argparse
import asyncio
import datetime
import json
import math
import os
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
    Request,
    Query,
    Body,
    Depends,
    HTTPException,
    status,
)
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger

from bot.core.bot_runner import run_bot
from pipecat.transports.network.webrtc_connection import (
    IceServer,
    SmallWebRTCConnection,
)
from src.server.authorization.auth import (
    verify_google_token,
    load_authorized_users,
    log_rejected_login,
    create_access_token,
    get_current_user,
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
            detail="Access denied. Your account is not authorized to access this application. Go on, git!",
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


@app.get("/api/books")
async def get_books() -> JSONResponse:
    """Returns a list of available books for vocabulary tutoring."""
    books_dir = BASE_SESSION_DIR / "assets" / "books"
    if not books_dir.is_dir():
        logger.error("Books directory not found")
        return JSONResponse(
            status_code=404, content={"error": "Books directory not found"}
        )

    try:
        books = []
        for book_dir in books_dir.iterdir():
            if book_dir.is_dir() and (book_dir / "paginated_story.json").exists():
                book_name = book_dir.name
                path = f"./assets/books/{book_name}/paginated_story.json"

                # Try to read the book title from the JSON file
                try:
                    with (book_dir / "paginated_story.json").open(
                        "r", encoding="utf-8"
                    ) as f:
                        book_data = json.load(f)
                        title = (
                            book_data.get("reading_context", {})
                            .get("key_information", {})
                            .get("book_title", book_name)
                        )
                except Exception:
                    title = book_name.replace("_", " ").title()

                books.append({"id": book_name, "title": title, "path": path})

        return JSONResponse(content=books)
    except Exception as e:
        logger.error(f"Error loading books: {e}")
        return JSONResponse(status_code=500, content={"error": "Unable to load books"})


@app.get("/api/book-chapters")
async def get_book_chapters(bookPath: str = Query(...)) -> JSONResponse:
    """Returns the maximum number of chapters for a specific book."""
    try:
        # Convert relative path to absolute path
        book_file_path = BASE_SESSION_DIR / bookPath.lstrip("./")

        if not book_file_path.exists():
            return JSONResponse(
                status_code=404, content={"error": "Book file not found"}
            )

        with book_file_path.open("r", encoding="utf-8") as f:
            book_data = json.load(f)
            chapters = book_data.get("reading_context", {}).get("chapters", [])
            max_chapters = len(chapters)

        return JSONResponse(content={"maxChapters": max_chapters})

    except Exception as e:
        logger.error(f"Error loading book chapters: {e}")
        return JSONResponse(
            status_code=500, content={"error": "Unable to load book chapters"}
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


@app.get("/api/activities/settings/{settings_path:path}")
async def get_activity_settings(settings_path: str) -> JSONResponse:
    """Loads activity settings JSON and filters services by available API keys.

    Args:
        settings_path (str): Relative path to the settings file.

    Returns:
        JSONResponse: Filtered JSON configuration.
    """
    file_path = BASE_SESSION_DIR / "assets" / "activities" / "settings" / settings_path

    if not file_path.is_file():
        logger.error(f"Settings file not found: {file_path}")
        return JSONResponse(
            status_code=404, content={"error": "Settings file not found"}
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
