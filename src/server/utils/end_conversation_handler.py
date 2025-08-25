"""
End conversation handler for Riverst sessions.

This module handles conversation termination and session cleanup.
It provides a centralized place for ending conversations gracefully across both
regular bot mode and advanced flows.
"""

from typing import Dict, Any, Optional
from loguru import logger
import asyncio

from pipecat.processors.frameworks.rtvi import RTVIServerMessageFrame, RTVIProcessor
from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.frames.frames import TTSSpeakFrame, TTSStoppedFrame, Frame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


class EndConversationHandler:
    """Handles conversation termination, providing a unified interface for ending sessions."""

    def __init__(self, rtvi: RTVIProcessor):
        """Initialize the handler with RTVI processor for real-time updates."""
        self.rtvi = rtvi

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
            await self.rtvi.push_frame(
                TTSSpeakFrame("It was nice talking to you. Have a nice day!")
            )

            # Send conversation ended message to client
            frame = RTVIServerMessageFrame(
                data={
                    "type": "conversation-ended",
                    "message": "The conversation has ended. Thank you for talking with 'River street'!",
                }
            )
            await self.rtvi.push_frame(frame)
            result = {"status": "conversation_ended"}
            logger.info("Conversation ended successfully")

        except Exception as e:
            logger.error(f"Error ending conversation: {e}")
            result = {
                "status": "error",
                "error": f"Failed to end conversation: {str(e)}",
            }

        return result


class CleanEndProcessor(FrameProcessor):
    """Processor for handling clean end of conversations."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.end_conversation_frame: Frame = None
        self.tts_stopped_received = False

    async def process_frame(self, frame: Frame, direction: FrameDirection):

        await super().process_frame(frame, direction)

        if isinstance(frame, RTVIServerMessageFrame):
            if frame.data.get("type") == "conversation-ended":
                logger.debug("Received conversation-ended frame")
                self.end_conversation_frame = frame
                return  # Do not push frame now

            if (
                frame.data.get("type") == "visemes-event"
                and self.tts_stopped_received
                and self.end_conversation_frame
            ):
                # Extract duration from visemes-event payload
                payload = frame.data.get("payload", {})
                duration = payload.get("duration", 0)
                logger.debug(f"Received visemes-event with duration: {duration}s")

                # Wait for the audio duration + 0.5 seconds
                wait_time = duration + 0.5
                logger.debug(
                    f"Waiting {wait_time}s before sending end conversation frame"
                )

                # Schedule the end conversation frame to be sent after the wait
                asyncio.create_task(self._send_end_frame_after_delay(wait_time))

                # Reset state
                self.tts_stopped_received = False
                self.end_conversation_frame = None

        if isinstance(frame, TTSStoppedFrame) and self.end_conversation_frame:
            logger.debug("Received TTSStoppedFrame after conversation ended")
            self.tts_stopped_received = True

        await self.push_frame(frame)

    async def _send_end_frame_after_delay(self, delay: float):
        """Send the end conversation frame after a delay."""
        await asyncio.sleep(delay)
        if self.end_conversation_frame:
            logger.debug("Sending delayed end conversation frame")
            await self.push_frame(self.end_conversation_frame)
