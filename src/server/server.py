#
# Copyright (c) 2024–2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

import argparse
import asyncio
import sys
from contextlib import asynccontextmanager
from typing import Dict

import uvicorn
from bot import run_bot
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import RedirectResponse
from loguru import logger
from pipecat_ai_small_webrtc_prebuilt.frontend import SmallWebRTCPrebuiltUI
from fastapi.middleware.cors import CORSMiddleware

from pipecat.transports.network.webrtc_connection import SmallWebRTCConnection
from fastapi.responses import JSONResponse, RedirectResponse

# Load environment variables
load_dotenv(override=True)

app = FastAPI()

# Configure CORS to allow requests from any origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store connections by pc_id
pcs_map: Dict[str, SmallWebRTCConnection] = {}

ice_servers = ["stun:stun.l.google.com:19302"]

# Mount the frontend at /
app.mount("/prebuilt", SmallWebRTCPrebuiltUI)


@app.get("/", include_in_schema=False)
async def root_redirect():
    return RedirectResponse(url="/prebuilt/")


@app.post("/api/offer")
async def offer(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    pc_id = data.get("pc_id")

    if pc_id and pc_id in pcs_map:
        pipecat_connection = pcs_map[pc_id]
        logger.info(f"Reusing existing connection for pc_id: {pc_id}")
        await pipecat_connection.renegotiate(
            sdp=data["sdp"], type=data["type"], restart_pc=data.get("restart_pc", False)
        )
    else:
        pipecat_connection = SmallWebRTCConnection(ice_servers)
        await pipecat_connection.initialize(sdp=data["sdp"], type=data["type"])

        @pipecat_connection.event_handler("closed")
        async def handle_disconnected(webrtc_connection: SmallWebRTCConnection):
            logger.info(f"Discarding peer connection for pc_id: {webrtc_connection.pc_id}")
            pcs_map.pop(webrtc_connection.pc_id, None)

        background_tasks.add_task(run_bot, pipecat_connection)

    answer = pipecat_connection.get_answer()
    pcs_map[answer["pc_id"]] = pipecat_connection

    return answer


@app.get("/health")
async def health_check():
    """Health check endpoint to verify server status.

    Returns:
        JSONResponse: A simple status message
    """
    print("Health check endpoint called")
    return JSONResponse({"status": "ok"})

stored_avatar_url = 'https://models.readyplayer.me/67eaadeeffcddc994a40ed15.glb?morphTargets=mouthOpen,Oculus Visemes' 

@app.post("/avatar")
async def save_avatar(request: Request):
    data = await request.json()
    global stored_avatar_url
    stored_avatar_url = data.get("avatar_url")
    print("Avatar URL received and saved:", stored_avatar_url)
    return JSONResponse({"status": "ok", "stored_avatar_url": stored_avatar_url})

@app.get("/avatar")
async def get_avatar():
    """Returns the currently stored avatar URL."""
    if stored_avatar_url:
        return JSONResponse({"avatar_url": stored_avatar_url})
    return JSONResponse({"avatar_url": None})



@asynccontextmanager
async def lifespan(app: FastAPI):
    yield  # Run app
    coros = [pc.close() for pc in pcs_map.values()]
    await asyncio.gather(*coros)
    pcs_map.clear()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WebRTC demo")
    parser.add_argument(
        "--host", default="localhost", help="Host for HTTP server (default: localhost)"
    )
    parser.add_argument(
        "--port", type=int, default=7860, help="Port for HTTP server (default: 7860)"
    )
    parser.add_argument("--verbose", "-v", action="count")
    args = parser.parse_args()

    logger.remove(0)
    if args.verbose:
        logger.add(sys.stderr, level="TRACE")
    else:
        logger.add(sys.stderr, level="DEBUG")

    uvicorn.run(app, host=args.host, port=args.port)
