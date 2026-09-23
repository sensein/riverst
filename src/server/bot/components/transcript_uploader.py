"""Uploads a session's transcript to S3, if durable storage is configured for this environment."""

import asyncio
import os

import boto3
from loguru import logger


async def upload_transcript(session_id: str, transcript_path: str) -> None:
    """Copy a session's local transcript file to S3, if configured.

    No-ops when ``RIVERST_TRANSCRIPTS_BUCKET`` is unset (e.g. local
    development). Never raises: a failed upload is only logged, and the
    local file is left untouched either way, so this can never block or
    delay session teardown for the user.

    Args:
        session_id: The session's directory name; used as the S3 key prefix.
        transcript_path: Local path to that session's transcript.json.
    """
    bucket = os.environ.get("RIVERST_TRANSCRIPTS_BUCKET")
    if not bucket:
        logger.debug("RIVERST_TRANSCRIPTS_BUCKET not set; skipping transcript upload")
        return

    key = f"{session_id}/transcript.json"
    try:
        await asyncio.to_thread(
            boto3.client("s3").upload_file, transcript_path, bucket, key
        )
        logger.info(
            f"Uploaded transcript for session {session_id} to s3://{bucket}/{key}"
        )
    except Exception as e:
        logger.error(f"Failed to upload transcript for session {session_id} to S3: {e}")
