"""
End conversation handler for Riverst sessions.

This module handles conversation termination and session cleanup.
It provides a centralized place for ending conversations gracefully across both
regular bot mode and advanced flows.
"""

from typing import Dict, Any, Optional
from loguru import logger

from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.frames.frames import TTSSpeakFrame


class EndConversationHandler:
    """Handles conversation termination, providing a unified interface for ending sessions."""

    def __init__(self, task):
        """Initialize the handler with pipeline task for frame queuing."""
        self.task = task

    @staticmethod
    def get_end_conversation_instruction() -> str:
        """Build end conversation instruction string for LLM prompts.

        Returns:
            Formatted instruction string explaining when to use end_conversation function.
        """
        instruction = (
            "End Conversation Instruction: Call the end_conversation function ONLY when you want to "
            "end the ENTIRE tutoring session. Use it when the user clearly indicates they want to "
            "finish the whole session, says goodbye, or expresses their intention to leave completely. "
            "Do NOT use this function when transitioning between activities or sections within the "
            "tutoring session (like finishing a review section to move on to something else). "
            "Only use it for final session endings.\n"
        )
        return instruction

    @staticmethod
    def build_end_conversation_tools_schema() -> FunctionSchema:
        """Build JSON schema for end conversation tool.

        Returns:
            Schema dict for LLM tool registration.
        """
        return FunctionSchema(
            name="end_conversation",
            description="End the conversation naturally and terminate the session cleanly.",
            properties={},
            required=[],
        )

    async def handle_end_conversation(
        self, action: Dict[str, Any], flow_manager: Any
    ) -> Optional[Dict[str, Any]]:
        """Handle conversation termination request.

        Args:
            action: Action configuration dict from flow system
            flow_manager: FlowManager instance

        Returns:
            Response dict for action system.
        """
        logger.info("End conversation requested by LLM")

        try:
            await self.task.queue_frame(TTSSpeakFrame("Thanks for talking today, bye!"))

            # Use stop_when_done for graceful termination
            await self.task.stop_when_done()
            result = {"status": "conversation_ended"}
            logger.info("Conversation ended successfully")

        except Exception as e:
            logger.error(f"Error ending conversation: {e}")
            result = {
                "status": "error",
                "error": f"Failed to end conversation: {str(e)}",
            }

        return result
