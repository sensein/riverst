"""
Animation handler for Riverst avatars.

This module handles animation triggering and management for avatar animations.
It provides a centralized place for defining available animations and handling animation requests.
"""

from typing import Dict, Any, List, Optional
import traceback

from pipecat.services.llm_service import FunctionCallParams
from pipecat.processors.frameworks.rtvi import RTVIServerMessageFrame, RTVIProcessor
from pipecat.adapters.schemas.function_schema import FunctionSchema

VALID_ANIMATIONS = [
    {
        "id": "dance",
        "description": "When you want to dance, you trigger the 'dance' animation.",
    },
    {
        "id": "wave",
        "description": (
            "When you welcome the user or greet them or introduce yourself, "
            "you trigger the 'wave' animation."
        ),
    },
    {
        "id": "i_have_a_question",
        "description": (
            "When you have a question and explicitly say that you have a question, "
            "you can do the 'i_have_a_question' animation as to indicate that you have a question."
        ),
    },
    {
        "id": "thank_you",
        "description": "When you want to thank the user for something, you can do the 'thank_you' animation.",
    },
    {
        "id": "i_dont_know",
        "description": "When you don’t know something, you can do the 'i_dont_know' animation.",
    },
    {
        "id": "ok",
        "description": "When you want to say 'ok', you can do the 'ok' animation.",
    },
    {
        "id": "thumbup",
        "description": "When you want to give a thumbs up, you can do the 'thumbup' animation.",
    },
    {
        "id": "thumbdown",
        "description": "When you want to give a thumbs down, you can do the 'thumbdown' animation.",
    },
    {"id": "happy", "description": "When you are happy, you do the 'happy' animation."},
    {"id": "sad", "description": "When you are sad, you do the 'sad' animation."},
    {"id": "angry", "description": "When you are angry, you do the 'angry' animation."},
    {"id": "fear", "description": "When you are scared, you do the 'fear' animation."},
    {
        "id": "disgust",
        "description": "When you are disgusted, you do the 'disgust' animation.",
    },
    {
        "id": "love",
        "description": "When you are in love with someone or something, you can do the 'love' animation.",
    },
    {
        "id": "sleep",
        "description": "When you are sleepy, you can do the 'sleep' animation.",
    },
    {
        "id": "thinking",
        "description": (
            "When you are thinking, you can do the 'thinking' animation, "
            "When the user finishes speaking and before you reply and if he/she asked a question that is a bit thought-provoking, trigger 'thinking' animation immediately. End it the moment you start speaking. Don’t retrigger if already active, and never run animations while you’re speaking."
        ),
        
    }
]


ANIMATION_MAP = {anim["id"]: anim["description"] for anim in VALID_ANIMATIONS}
VALID_ANIMATION_IDS = list(ANIMATION_MAP.keys())


class AnimationHandler:
    """Handles avatar animations, providing a unified interface for triggering animations."""

    @staticmethod
    def get_valid_animation_ids() -> List[str]:
        """Return all valid animation IDs."""
        return VALID_ANIMATION_IDS

    @staticmethod
    def get_animation_instruction(enabled_animations: List[str]) -> str:
        """Build animation instruction string for LLM prompts.

        Args:
            enabled_animations: List of enabled animation IDs.

        Returns:
            Formatted instruction string.
        """
        instructions = [
            ANIMATION_MAP[anim_id]
            for anim_id in enabled_animations
            if anim_id in ANIMATION_MAP
        ]
        return (
            f"Animation Instruction: {' '.join(instructions)}\n" if instructions else ""
        )

    @staticmethod
    def build_animation_tools_schema(enabled_animations: List[str]) -> "FunctionSchema":
        """Build JSON schema for animation tool.

        Args:
            enabled_animations: List of enabled animation IDs.

        Returns:
            Schema dict for LLM tool registration.
        """
        animations = [
            anim_id for anim_id in enabled_animations if anim_id in VALID_ANIMATION_IDS
        ]
        return FunctionSchema(
            name="trigger_animation",
            description="Trigger an avatar animation (only one at a time).",
            properties={
                "animation_id": {
                    "type": "string",
                    "enum": animations,
                    "description": "The animation ID to trigger.",
                }
            },
            required=["animation_id"],
        )
    
    @staticmethod
    def build_stop_animation_tools_schema() -> "FunctionSchema":
        """Build JSON schema for stop animation tool.

        Returns:
            Schema dict for LLM tool registration.
        """
        return FunctionSchema(
            name="stop_animation",
            description="Stop any currently playing animation.",
            properties={},
            required=[],
        )

    @staticmethod
    async def handle_animation(
        params: Any, rtvi: RTVIProcessor, allowed_animations: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Trigger avatar animation if allowed.

        Args:
            params: FunctionCallParams or dict containing 'animation_id'.
            rtvi: RTVIProcessor to send the animation event.
            allowed_animations: List of allowed animation IDs.

        Returns:
            Response dict if not using result_callback.
        """
        args = params.arguments if isinstance(params, FunctionCallParams) else params
        animation_id = args.get("animation_id")

        if animation_id not in allowed_animations:
            result = {
                "status": "error",
                "error": f"Invalid animation ID. Valid IDs: {allowed_animations}",
            }
        else:
            try:
                frame = RTVIServerMessageFrame(
                    data={
                        "type": "animation-event",
                        "payload": {"animation_id": animation_id},
                    }
                )
                await rtvi.push_frame(frame)
                result = {"status": "animation_triggered"}
            except Exception as e:
                result = {
                    "status": "error",
                    "error": f"Failed to handle animation: {str(e)}",
                }

        if isinstance(params, FunctionCallParams):
            await params.result_callback(result)
            return None

        return result

    @staticmethod
    async def handle_stop_animation(
        params: Any, rtvi: RTVIProcessor
    ) -> Optional[Dict[str, Any]]:
        """Stop any currently playing animation.

        Args:
            params: FunctionCallParams or dict.
            rtvi: RTVIProcessor to send the stop event.

        Returns:
            Response dict if not using result_callback.
        """
        from loguru import logger
        
        logger.info("STOP_ANIMATION_DEBUG: handle_stop_animation called with params: {}", params)
        logger.info("STOP_ANIMATION_DEBUG: RTVI processor state: {}", rtvi)
        
        try:
            frame = RTVIServerMessageFrame(
                data={"type": "animation-event", "payload": {"stop": True}}
            )
            logger.info("STOP_ANIMATION_DEBUG: Created RTVI frame: {}", frame.data)
            
            await rtvi.push_frame(frame)
            logger.info("STOP_ANIMATION_DEBUG: Successfully pushed frame to RTVI")
            
            result = {"status": "animation_stopped"}
        except Exception as e:
            logger.error("STOP_ANIMATION_DEBUG: Exception in handle_stop_animation: {}", str(e))
            logger.error("STOP_ANIMATION_DEBUG: Exception traceback: {}", traceback.format_exc())
            result = {
                "status": "error",
                "error": f"Failed to stop animation: {str(e)}",
            }

        logger.info("STOP_ANIMATION_DEBUG: Final result: {}", result)

        if isinstance(params, FunctionCallParams):
            await params.result_callback(result)
            return None

        return result