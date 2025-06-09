import argparse
import asyncio
import sys
import json
import datetime
import uuid
import os
from pathlib import Path
from typing import Dict, Optional, Any

import uvicorn
from fastapi import BackgroundTasks, FastAPI, Request, Query, Body
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from loguru import logger

from utils.bot import run_bot
from pipecat_ai_small_webrtc_prebuilt.frontend import SmallWebRTCPrebuiltUI
from pipecat.transports.network.webrtc_connection import SmallWebRTCConnection
from fastapi.staticfiles import StaticFiles

# Load environment variables
load_dotenv(override=True)

app = FastAPI()

BASE_SESSION_DIR = Path(__file__).parent

(BASE_SESSION_DIR / "sessions").mkdir(exist_ok=True)
app.mount("/sessions", StaticFiles(directory=BASE_SESSION_DIR / "sessions"), name="sessions")

# Enable CORS for all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Track active WebRTC connections
pcs_map: Dict[str, SmallWebRTCConnection] = {}

# ICE servers for WebRTC connection
ice_servers = ["stun:stun.l.google.com:19302"]

# Mount the default frontend
app.mount("/prebuilt", SmallWebRTCPrebuiltUI)


@app.get("/", include_in_schema=False)
async def root_redirect() -> RedirectResponse:
    """Redirects to the default frontend UI."""
    return RedirectResponse(url="/prebuilt/")


@app.post("/api/session")
async def create_session(config: dict = Body(...)) -> JSONResponse:
    """Creates a new session and stores its config.

    Args:
        config (dict): Configuration dictionary.

    Returns:
        JSONResponse: Contains the newly generated session ID.
    """
    if not config.get("user_id"):
        return JSONResponse(status_code=400, content={"error": "User ID is required"})
    user_id = config['user_id']
    session_id = user_id + "__" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + str(uuid.uuid4())[:8]
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
        return JSONResponse(status_code=400, content={"error": "Invalid config file format"})

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

        background_tasks.add_task(run_bot, pipecat_connection, config=config, session_dir=str(session_dir))

    answer = pipecat_connection.get_answer()
    pcs_map[answer["pc_id"]] = pipecat_connection
    return JSONResponse(answer)


@app.get("/health")
async def health_check() -> JSONResponse:
    """Health check endpoint.

    Returns:
        JSONResponse: Service status message.
    """
    return JSONResponse({"status": "ok"})

@app.get("/avatars")
async def get_avatars() -> JSONResponse:
    """Returns a list of available avatars."""
    file_path = BASE_SESSION_DIR / "assets" / "avatars.json"
    try:
        with file_path.open("r", encoding="utf-8") as f:
            avatars = json.load(f)
        return JSONResponse(content=avatars)
    except Exception as e:
        logger.error(f"Error loading avatars: {e}")
        return JSONResponse(status_code=500, content={"error": "Unable to load avatars"})
        
@app.get("/books")
async def get_books() -> JSONResponse:
    """Returns a list of available books for vocabulary tutoring."""
    books_dir = BASE_SESSION_DIR / "assets" / "books"
    if not books_dir.is_dir():
        logger.error("Books directory not found")
        return JSONResponse(status_code=404, content={"error": "Books directory not found"})
    
    try:
        books = []
        for book_dir in books_dir.iterdir():
            if book_dir.is_dir() and (book_dir / "paginated_story.json").exists():
                book_name = book_dir.name
                path = f"./assets/books/{book_name}/paginated_story.json"
                
                # Try to read the book title from the JSON file
                try:
                    with (book_dir / "paginated_story.json").open("r", encoding="utf-8") as f:
                        book_data = json.load(f)
                        title = book_data.get("reading_context", {}).get("book_title", book_name)
                except:
                    title = book_name.replace("_", " ").title()
                
                books.append({
                    "id": book_name,
                    "title": title,
                    "path": path
                })
        
        return JSONResponse(content=books)
    except Exception as e:
        logger.error(f"Error loading books: {e}")
        return JSONResponse(status_code=500, content={"error": "Unable to load books"})

@app.get("/activities")
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
        return JSONResponse(status_code=500, content={"error": "Unable to load activities"})


@app.get("/activities/settings/{settings_path:path}")
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
        return JSONResponse(status_code=404, content={"error": "Settings file not found"})

    try:
        with file_path.open("r", encoding="utf-8") as f:
            config = json.load(f)

        has_openai = os.getenv("OPENAI_API_KEY") is not None
        has_google = os.getenv("GOOGLE_API_KEY") is not None

        options_props: Dict[str, Any] = (
            config.get("properties", {})
                  .get("options", {})
                  .get("properties", {})
        )

        for key, model_list in {
            "llm_type": ["openai", "openai_realtime_beta", "gemini"],
            "stt_type": ["openai"],
            "tts_type": ["openai"]
        }.items():
            if key in options_props and "enum" in options_props[key]:
                allowed = options_props[key]["enum"]
                filtered = [
                    m for m in allowed
                    if not (
                        (not has_openai and m in ["openai", "openai_realtime_beta"]) or
                        (not has_google and m == "gemini")
                    )
                ]
                options_props[key]["enum"] = filtered

                if "default" in options_props[key] and options_props[key]["default"] not in filtered:
                    if filtered:
                        options_props[key]["default"] = filtered[0]
                    else:
                        logger.warning(f"No valid options left for '{key}' after filtering.")
                        del options_props[key]

        return JSONResponse(content=config)

    except Exception as e:
        logger.error(f"Error reading or processing settings file: {e}")
        return JSONResponse(status_code=500, content={"error": "Unable to load settings"})


@app.get("/api/sessions")
async def list_sessions() -> JSONResponse:
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
        all_json_exist = all((json_dir / (wav_file.stem + ".json")).exists() for wav_file in wav_files)
        if all_json_exist:
            valid_session_ids.append(session_dir.name)
    return JSONResponse(content=valid_session_ids)

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


@app.get("/api/session/{session_id}")
async def get_session_data(session_id: str) -> JSONResponse:
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
        except Exception as e:
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

    return JSONResponse(content={
        "data": results,
        "metrics_summary": metrics
    })

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
    parser.add_argument("--host", default="localhost", help="Server hostname (default: localhost)")
    parser.add_argument("--port", type=int, default=7860, help="Port number (default: 7860)")
    parser.add_argument("--verbose", "-v", action="count", help="Enable verbose logging")
    args = parser.parse_args()

    logger.remove(0)
    logger.add(sys.stderr, level="TRACE" if args.verbose else "DEBUG")

    uvicorn.run(app, host=args.host, port=args.port)
