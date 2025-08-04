"""
End conversation handler for Riverst sessions.

This module handles conversation termination and session cleanup.
It provides a centralized place for ending conversations gracefully across both
regular bot mode and advanced flows.
"""

from typing import Dict, Any, Optional
from loguru import logger

from pipecat.services.llm_service import FunctionCallParams
from pipecat.processors.frameworks.rtvi import RTVIServerMessageFrame, RTVIProcessor
from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.frames.frames import TTSSpeakFrame


class EndConversationHandler:
    """Handles conversation termination, providing a unified interface for ending sessions."""

    @staticmethod
    def get_end_conversation_instruction() -> str:
        """Build end conversation instruction string for LLM prompts.

        Returns:
            Formatted instruction string explaining when to use end_conversation function.
        """
        instruction = (
            "End Conversation Instruction: Call the end_conversation() function when you want to "
            "end the conversation naturally. IMPORTANT: MAKE SURE TO SAY GOODBYE BEFORE "
            "CALLING IT! Use this when you determine it's appropriate to end "
            "the interaction, or when the user indicates they want to finish the session.\n"
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

    @staticmethod
    async def handle_end_conversation(
        params: Any, rtvi: RTVIProcessor
    ) -> Optional[Dict[str, Any]]:
        """Handle conversation termination request.

        Args:
            params: FunctionCallParams or dict (no parameters needed for end_conversation).
            rtvi: RTVIProcessor to send the termination event.

        Returns:
            Response dict if not using result_callback.
        """
        logger.info("End conversation requested by LLM")

        try:
            print("End conversation requested by LLM 1")
            await rtvi.push_frame(
                TTSSpeakFrame("It was nice talking to you. Have a nice day!")
            )

            # Send conversation ended message to client
            frame = RTVIServerMessageFrame(
                data={
                    "type": "conversation-ended",
                    "message": "The conversation has ended. Thank you for talking with 'River street'!",
                }
            )
            await rtvi.push_frame(frame)
            result = {"status": "conversation_ended"}
            logger.info("Conversation ended successfully")

        except Exception as e:
            logger.error(f"Error ending conversation: {e}")
            result = {
                "status": "error",
                "error": f"Failed to end conversation: {str(e)}",
            }

        if isinstance(params, FunctionCallParams):
            await params.result_callback(result)
            return None

        return result
