"""
Animation handler for Riverst avatars.

This module handles animation triggering and management for avatar animations.
It provides a centralized place for defining available animations and handling animation requests.
"""
import traceback
from typing import Dict, Any, List, Optional

from pipecat.services.llm_service import FunctionCallParams
from pipecat.processors.frameworks.rtvi import RTVIServerMessageFrame, RTVIProcessor
from loguru import logger


VALID_ANIMATIONS = [
    {"id": "dance", "description": "When you want to dance, you trigger the 'dance' animation."},
    {"id": "wave", "description": "When you welcome the user or greet them or introduce yourself, you always trigger the 'wave' animation."},
    {"id": "i_have_a_question", "description": "When you have a question, sometimes, you can do the 'i_have_a_question' animation."},
    {"id": "thank_you", "description": "When you want to thank the user, you do the 'thank_you' animation."},
    {"id": "i_dont_know", "description": "When you don’t know something, you do the 'i_dont_know' animation."},
    {"id": "ok", "description": "When you want to say 'ok', you can do the 'ok' animation."},
    {"id": "thumbup", "description": "When you want to give a thumbs up, you can do the 'thumbup' animation."},
    {"id": "thumbdown", "description": "When you want to give a thumbs down, you can do the 'thumbdown' animation."},
    {"id": "happy", "description": "When you are happy, you can do the 'happy' animation."},
    {"id": "sad", "description": "When you are sad, you can do the 'sad' animation."},
    {"id": "angry", "description": "When you are angry, you can do the 'angry' animation."},
    {"id": "fear", "description": "When you are scared, you can do the 'fear' animation."},
    {"id": "disgust", "description": "When you are disgusted, you can do the 'disgust' animation."},
    {"id": "love", "description": "When you are in love with someone or something, you can do the 'love' animation."},
    {"id": "sleep", "description": "When you are sleepy, you can do the 'sleep' animation."},
]

class AnimationHandler:
    """Handles avatar animations, providing a unified interface for triggering animations."""
    
    @staticmethod
    def get_valid_animation_ids() -> List[str]:
        """Get list of all valid animation IDs.
        
        Returns:
            List of valid animation IDs
        """
        return [animation["id"] for animation in VALID_ANIMATIONS]
    
    @staticmethod
    def get_animation_instruction(enabled_animations: List[str]) -> str:
        """Build animation instruction string for LLM prompts based on enabled animations.
        
        Args:
            enabled_animations: List of enabled animation IDs
            
        Returns:
            Animation instruction string
        """
        if not enabled_animations:
            return ""
            
        animation_map = {a["id"]: a["description"] for a in VALID_ANIMATIONS}
        instructions = [
            animation_map[anim_id]
            for anim_id in set(enabled_animations) & set(animation_map)
        ]
        
        return f"Animation Instruction: {' '.join(instructions)}\n" if instructions else ""
    
    @staticmethod
    def build_animation_tools_schema(enabled_animations: List[str]) -> Dict:
        """Build tools schema for animations.
        
        Args:
            enabled_animations: List of enabled animation IDs
            
        Returns:
            Function schema for LLM tool registration
        """
        valid_ids = {a["id"] for a in VALID_ANIMATIONS}
        animations = list(set(enabled_animations or []) & valid_ids)
        
        return {
            "name": "trigger_animation",
            "description": "Trigger an avatar animation (only one at a time).",
            "properties": {
                "animation_id": {
                    "type": "string",
                    "enum": animations,
                    "description": "The animation ID to trigger.",
                }
            },
            "required": ["animation_id"]
        }
    
    @staticmethod
    async def handle_animation(params, rtvi: RTVIProcessor, allowed_animations: List[str]) -> Optional[Dict[str, Any]]:
        """Handle animation - works with both regular Pipecat and Pipecat Flows"""
        
        # Extract arguments regardless of paradigm
        args = params.arguments if isinstance(params, FunctionCallParams) else params
        animation_id = args.get("animation_id")
        
        try:
            if animation_id and animation_id in allowed_animations:
                frame = RTVIServerMessageFrame(data={
                    "type": "animation-event", 
                    "payload": {"animation_id": animation_id}
                })
                await rtvi.push_frame(frame)
                result = {"status": "animation_triggered"}
            else:
                result = {
                    "status": "error",
                    "error": f"Invalid animation ID. Valid IDs: {allowed_animations}"
                }
        except Exception as e:
            result = {"status": "error", "error": f"Failed to handle animation: {str(e)}"}
        
        # Handle result based on paradigm
        if isinstance(params, FunctionCallParams):
            await params.result_callback(result)
        else:
            return result
            