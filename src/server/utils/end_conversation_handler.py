"""
End conversation handler for Riverst sessions.

This module handles conversation termination and session cleanup.
It provides a centralized place for ending conversations gracefully across both
regular bot mode and advanced flows.
"""

from typing import Dict, Any, Optional
from loguru import logger

from pipecat.services.llm_service import FunctionCallParams
from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.frames.frames import EndFrame
from pipecat.pipeline.task import PipelineTask


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
        params: FunctionCallParams, task: Optional[PipelineTask] = None
    ) -> Optional[Dict[str, Any]]:
        """Handle conversation termination request.

        Args:
            params: FunctionCallParams containing the task and other context.

        Returns:
            Response dict if not using result_callback.
        """
        logger.info("End conversation requested by LLM")

        try:
            # Queue EndFrame to gracefully terminate the pipeline
            await task.queue_frame(EndFrame())
            result = {"status": "conversation_ended"}
            logger.info("Conversation ended successfully with EndFrame")

        except Exception as e:
            logger.error(f"Error ending conversation: {e}")
            result = {
                "status": "error",
                "error": f"Failed to end conversation: {str(e)}",
            }

        await params.result_callback(result)
        return None
