"""
End conversation handler for Riverst sessions.

This module handles conversation termination and session cleanup.
It provides a centralized place for ending conversations gracefully across both
regular bot mode and advanced flows.
"""

import asyncio
from loguru import logger

from pipecat.services.llm_service import FunctionCallParams
from pipecat.processors.frameworks.rtvi import RTVIServerMessageFrame
from pipecat.frames.frames import EndFrame


async def end_conversation_handler(params: FunctionCallParams) -> None:
    """Handle the end_conversation function call from the LLM.

    This function:
    1. Logs the conversation termination
    2. Sends a termination message to the client
    3. Triggers session cleanup and disconnection

    Args:
        params: Function call parameters (currently unused but required for signature)
    """
    logger.info("End conversation requested by LLM")

    try:
        # Note: In flows mode, the task context should be available through the flow manager
        # The goodbye message and frame queueing will be handled by the flow system
        logger.info("Conversation ended successfully")

    except Exception as e:
        logger.error(f"Error ending conversation: {e}")


def create_end_conversation_handler(task=None, session_dir: str = None):
    """Factory function to create an end conversation handler for regular bot mode.

    Args:
        task: The pipeline task
        session_dir: Directory for session artifacts

    Returns:
        Callable function for handling end conversation requests
    """

    async def end_conversation_wrapper(params: FunctionCallParams) -> None:
        """Wrapper function that includes task context for regular bot mode."""
        logger.info("End conversation requested by LLM")

        try:
            # Send a goodbye message to the client before terminating
            goodbye_message = RTVIServerMessageFrame(
                data={
                    "type": "conversation-ended",
                    "message": "The conversation has ended. Thank you for talking with Riverst!",
                }
            )

            if task:
                await task.queue_frame(goodbye_message)

                # Wait a brief moment for the message to be sent
                await asyncio.sleep(0.5)

                # Send end frame to terminate the pipeline
                await task.queue_frame(EndFrame())

            logger.info("Conversation ended successfully")

        except Exception as e:
            logger.error(f"Error ending conversation: {e}")

    return end_conversation_wrapper


# Function definition for LLM registration
END_CONVERSATION_FUNCTION_DEFINITION = {
    "name": "end_conversation",
    "description": (
        "Call this function when you want to end the conversation naturally. "
        "This will cleanly terminate the session and thank the user. "
        "Use this when the conversation has reached a natural conclusion, "
        "when the user says goodbye, or when you determine it's appropriate to end the interaction."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}
