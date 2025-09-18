"""
Animation handler for Riverst avatars.

This module handles animation triggering and management for avatar animations.
It provides a centralized place for defining available animations and handling animation requests.
"""

from typing import Dict, Any, List, Optional

from pipecat.services.llm_service import FunctionCallParams
from pipecat.processors.frameworks.rtvi import RTVIServerMessageFrame, RTVIProcessor
from pipecat.adapters.schemas.function_schema import FunctionSchema

from ...monitoring import function_call_debug

VALID_ANIMATIONS = [
    {
        "id": "dance",
        "description": "When you want to dance, you trigger the 'dance' animation.",
        "duration": 5.0,
    },
    {
        "id": "wave",
        "description": (
            "When you welcome the user or greet them or introduce yourself, "
            "you trigger the 'wave' animation."
        ),
        "duration": 2.5, 
    },
    {
        "id": "i_have_a_question",
        "description": (
            "When you have a question and explicitly say that you have a question, "
            "you can do the 'i_have_a_question' animation as to indicate that you have a question."
        ),
        "duration": 2.0,
    },
    {
        "id": "thank_you",
        "description": "When you want to thank the user for something, you can do the 'thank_you' animation.",
        "duration": 2.5,
    },
    {
        "id": "i_dont_know",
        "description": "When you don’t know something, you can do the 'i_dont_know' animation.",
        "duration": 2.0,
    },
    {
        "id": "ok",
        "description": "When you want to say 'ok', you can do the 'ok' animation.",
        "duration": 1.5,
    },
    {
        "id": "thumbup",
        "description": "When you want to give a thumbs up, you can do the 'thumbup' animation.",
        "duration": 2.0,
    },
    {
        "id": "thumbdown",
        "description": "When you want to give a thumbs down, you can do the 'thumbdown' animation.",
        "duration": 2.0,
    },
    {"id": "happy", "description": "When you are happy, you do the 'happy' animation.", "duration": 3.5},
    {"id": "sad", "description": "When you are sad, you do the 'sad' animation.", "duration": 4.0},
    {"id": "angry", "description": "When you are angry, you do the 'angry' animation.", "duration": 3.0},
    {"id": "fear", "description": "When you are scared, you do the 'fear' animation.", "duration": 2.5},
    {
        "id": "disgust",
        "description": "When you are disgusted, you do the 'disgust' animation.",
        "duration": 3.0,
    },
    {
        "id": "love",
        "description": "When you are in love with someone or something, you can do the 'love' animation.",
        "duration": 3.5,
    },
    {
        "id": "sleep",
        "description": "When you are sleepy, you can do the 'sleep' animation.",
        "duration": 5.0,
    },
]


ANIMATION_MAP = {anim["id"]: anim["description"] for anim in VALID_ANIMATIONS}
ANIMATION_DURATION_MAP = {anim["id"]: anim["duration"] for anim in VALID_ANIMATIONS}
VALID_ANIMATION_IDS = list(ANIMATION_MAP.keys())


class AnimationHandler:
    """Handles avatar animations, providing a unified interface for triggering animations."""

    def __init__(self, rtvi: RTVIProcessor, allowed_animations: List[str]):
        """Initialize the animation handler with dependencies.

        Args:
            rtvi: RTVIProcessor instance for sending animation events.
            allowed_animations: List of allowed animation IDs for this session.
        """
        self.rtvi = rtvi
        self.allowed_animations = allowed_animations

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
    def build_animation_tools_schema(allowed_animations: List[str]) -> "FunctionSchema":
        """Build JSON schema for animation tool using provided allowed animations.

        Args:
            allowed_animations: List of allowed animation IDs for this session.

        Returns:
            Schema dict for LLM tool registration.
        """
        animations = [
            anim_id for anim_id in allowed_animations if anim_id in VALID_ANIMATION_IDS
        ]
        return FunctionSchema(
            name="trigger_animation",
            description="Trigger an avatar animation (only one at a time). You determine the duration for gestures and moods based on the flow of the conversation. If duration is not specified, select an appropriate value according to context.",
            properties={
                "animation_id": {
                    "type": "string",
                    "enum": animations,
                    "description": "The animation ID to trigger.",
                },
                "duration": {
                    "type": "number",
                    "minimum": 0.5,
                    "maximum": 10.0,
                    "description": "Duration in seconds for the animation. Default is based on animation type. Use shorter durations (0.5-3s) for quick gestures, longer durations (4-10s) for sustained moods or complex animations.",
                }
            },
            required=["animation_id"],
        )

    @function_call_debug
    async def handle_animation(
        self, params: FunctionCallParams
    ) -> Optional[Dict[str, Any]]:
        """Trigger avatar animation if allowed.

        Args:
            params: FunctionCallParams or dict containing 'animation_id' and optional 'duration'.

        Returns:
            Response dict if not using result_callback.
        """
        args = params.arguments if isinstance(params, FunctionCallParams) else params
        animation_id = args.get("animation_id")
        # Get default duration from ANIMATION_DURATION_MAP if not provided
        default_duration = ANIMATION_DURATION_MAP.get(animation_id, 3.0)
        duration = args.get("duration", default_duration)

        # Validate duration
        if duration < 0.5 or duration > 10.0:
            result = {
                "status": "error",
                "error": f"Invalid duration {duration}. Duration must be between 0.5 and 10.0 seconds.",
            }
        elif animation_id not in self.allowed_animations:
            result = {
                "status": "error",
                "error": f"Invalid animation ID. Valid IDs: {self.allowed_animations}",
            }
        else:
            try:
                frame = RTVIServerMessageFrame(
                    data={
                        "type": "animation-event",
                        "payload": {
                            "animation_id": animation_id,
                            "duration": duration
                        },
                    }
                )
                await self.rtvi.push_frame(frame)
                result = {"status": "animation_triggered", "duration": duration}
            except Exception as e:
                result = {
                    "status": "error",
                    "error": f"Failed to handle animation: {str(e)}",
                }

        if isinstance(params, FunctionCallParams):
            await params.result_callback(result)
            return None

        return result
