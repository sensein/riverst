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
    {"id": "wave", "description": "When you welcome the user or greet them or introduce yourself, you always wave with your hand (animation)."},
    {"id": "dance", "description": "When you congratulate or appreciate the user or are happy, you dance (animation)."},
    {"id": "i_dont_know", "description": "When you don't know something, you do the 'I don't know' animation."},
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
    
    # Helper class to add arguments attribute
    class ArgumentsDict(dict):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.arguments = self.copy()  # Add arguments attribute as a copy of self

    @staticmethod
    async def handle_animation(params, rtvi: Optional[RTVIProcessor] = None) -> Dict[str, Any]:
        """Handle animation triggers for both regular Pipecat and Pipecat Flows.
        
        Args:
            params: Either FunctionCallParams or a dict with arguments
            rtvi: Optional RTVI processor, required when called directly
            
        Returns:
            Dict with status and any error messages
        """
        # Use logger.error to ensure visibility in logs
        logger.error("ANIMATION_HANDLER_DEBUG: Received params type: {}", type(params))
        
        # Check if params has arguments attribute
        has_arguments = hasattr(params, 'arguments')
        logger.error("ANIMATION_HANDLER_DEBUG: Has arguments attribute: {}", has_arguments)
        
        # Log params content
        if isinstance(params, dict):
            logger.error("ANIMATION_HANDLER_DEBUG: Dict keys: {}", list(params.keys()))
            for key, value in params.items():
                logger.error("ANIMATION_HANDLER_DEBUG: Key '{}' = {}", key, value)
        elif hasattr(params, '__dict__'):
            logger.error("ANIMATION_HANDLER_DEBUG: __dict__: {}", params.__dict__)
        
        # For FunctionCallParams object, log its attributes
        if hasattr(params, 'arguments'):
            logger.info("Params has 'arguments' attribute: {}", params.arguments)
            
        # Log call stack to see where we're being called from
        import traceback
        call_stack = "".join(traceback.format_stack())
        logger.error("ANIMATION_HANDLER_DEBUG: Call stack:\n{}", call_stack)
        
        # Check for pipecat-flows in call stack
        is_from_pipecat_flows = "pipecat_flows/manager.py" in call_stack
        logger.error("ANIMATION_HANDLER_DEBUG: Called from pipecat_flows: {}", is_from_pipecat_flows)
        
        # Handle different parameter types
        if isinstance(params, FunctionCallParams):
            # Standard pipecat format
            args = params.arguments
            logger.error("ANIMATION_HANDLER_DEBUG: Using arguments from FunctionCallParams")
        elif hasattr(params, 'arguments') and isinstance(params.arguments, dict):
            # For our ArgumentsDict solution
            args = params.arguments
            logger.error("ANIMATION_HANDLER_DEBUG: Using params.arguments attribute")
        elif isinstance(params, dict):
            logger.error("ANIMATION_HANDLER_DEBUG: Params keys: {}", list(params.keys()))
            
            if "arguments" in params:
                # For pipecat-flows function call format v1
                args = params["arguments"]
                logger.error("ANIMATION_HANDLER_DEBUG: Using arguments from params dict with 'arguments' key")
            elif "function_call" in params and isinstance(params["function_call"], dict):
                # Extract from function_call structure for pipecat-flows
                func_call = params["function_call"]
                logger.error("ANIMATION_HANDLER_DEBUG: Function_call keys: {}", list(func_call.keys()))
                
                if isinstance(func_call.get("arguments"), dict):
                    args = func_call["arguments"]
                    logger.error("ANIMATION_HANDLER_DEBUG: Using arguments from function_call.arguments dict")
                elif isinstance(func_call.get("arguments"), str):
                    # Handle string JSON arguments
                    try:
                        import json
                        args = json.loads(func_call["arguments"])
                        logger.error("ANIMATION_HANDLER_DEBUG: Using parsed JSON from function_call.arguments string")
                    except Exception as e:
                        logger.error("ANIMATION_HANDLER_DEBUG: Failed to parse arguments: {}", str(e))
                        args = {}
                else:
                    args = {}
                    logger.error("ANIMATION_HANDLER_DEBUG: No valid arguments found in function_call")
            elif "function" in params and "name" in params.get("function", {}):
                # This might be the pipecat-flows format
                function_data = params.get("function", {})
                logger.error("ANIMATION_HANDLER_DEBUG: Function keys: {}", list(function_data.keys()))
                
                if isinstance(function_data.get("arguments"), str):
                    try:
                        import json
                        args = json.loads(function_data["arguments"])
                        logger.error("ANIMATION_HANDLER_DEBUG: Using parsed JSON from function.arguments string")
                    except Exception as e:
                        logger.error("ANIMATION_HANDLER_DEBUG: Failed to parse arguments string: {}", str(e))
                        args = {}
                elif isinstance(function_data.get("arguments"), dict):
                    args = function_data["arguments"]
                    logger.error("ANIMATION_HANDLER_DEBUG: Using arguments from function.arguments dict")
                else:
                    # If we get here, try the direct dict as fallback
                    args = params
                    logger.error("ANIMATION_HANDLER_DEBUG: Falling back to using the entire params dict")
            else:
                # Special handling for pipecat-flows if detected in call stack
                if is_from_pipecat_flows:
                    logger.error("ANIMATION_HANDLER_DEBUG: Called from pipecat_flows.manager")
                    # Try to extract animation_id from various possible locations
                    animation_id = None
                    
                    # Common parameter keys to check
                    if params.get("animation_id"):
                        animation_id = params.get("animation_id")
                        args = {"animation_id": animation_id}
                        logger.error("ANIMATION_HANDLER_DEBUG: Found animation_id at root level: {}", animation_id)
                    elif "function" in params:
                        # Try to extract from function.arguments if it's a string (JSON)
                        func_args = params.get("function", {}).get("arguments", "{}")
                        if isinstance(func_args, str):
                            try:
                                import json
                                json_args = json.loads(func_args)
                                animation_id = json_args.get("animation_id")
                                args = json_args
                                logger.error("ANIMATION_HANDLER_DEBUG: Parsed animation_id from function.arguments JSON: {}", animation_id)
                            except Exception as e:
                                logger.error("ANIMATION_HANDLER_DEBUG: Failed to parse function.arguments JSON: {}", str(e))
                        elif isinstance(func_args, dict):
                            animation_id = func_args.get("animation_id")
                            args = func_args
                            logger.error("ANIMATION_HANDLER_DEBUG: Found animation_id in function.arguments dict: {}", animation_id)
                    
                    # If we still don't have animation_id, use entire params as fallback
                    if animation_id is None:
                        args = params
                        logger.error("ANIMATION_HANDLER_DEBUG: No animation_id found, using entire params as fallback")
                else:
                    # Direct arguments dict (assuming animation_id is at the root level)
                    args = params
                    logger.error("ANIMATION_HANDLER_DEBUG: Using entire params dict as arguments")
        else:
            # Unknown format
            logger.error("ANIMATION_HANDLER_DEBUG: Received unexpected params type: {}", type(params))
            args = {}
            
        # Debugging
        logger.debug(f"Animation handler params type: {type(params)}")
        logger.debug(f"Animation handler args: {args}")
            
        animation_id = args.get("animation_id")
        
        try:
            if rtvi is None and not isinstance(params, FunctionCallParams):
                return {
                    "status": "error",
                    "error": "RTVI processor required when not called via LLM function"
                }
                        
            # If coming from LLM, we have no rtvi reference but we do need the allowed_animations
            # This logic would be extended by the function wrapper in bot.py
            allowed_animations = args.get("_allowed_animations", [])
            
            # For pipecat-flows compatibility
            if not allowed_animations and isinstance(params, dict) and "_allowed_animations" in params:
                allowed_animations = params.get("_allowed_animations", [])
                
            # Ensure animation_id is explicitly copied if found in params but not in args
            if "animation_id" not in args and isinstance(params, dict) and "animation_id" in params:
                args["animation_id"] = params["animation_id"]
                logger.error("ANIMATION_HANDLER_DEBUG: Copied animation_id from params to args: {}", params['animation_id'])
                
            # Last resort: for 'dict has no attribute arguments' error from pipecat_flows.manager
            if not args.get("animation_id") and "function" in params and hasattr(params.get("function"), "arguments"):
                func_arguments = params["function"].arguments
                if isinstance(func_arguments, str):
                    try:
                        import json
                        json_args = json.loads(func_arguments)
                        args["animation_id"] = json_args.get("animation_id")
                        logger.error("ANIMATION_HANDLER_DEBUG: Extracted animation_id from function.arguments JSON: {}", args['animation_id'])
                    except Exception as e:
                        logger.error("ANIMATION_HANDLER_DEBUG: Error parsing function.arguments: {}", str(e))
                elif isinstance(func_arguments, dict):
                    args["animation_id"] = func_arguments.get("animation_id")
                    logger.error("ANIMATION_HANDLER_DEBUG: Extracted animation_id from function.arguments dict: {}", args['animation_id'])
            
            if animation_id and animation_id in allowed_animations:
                frame = RTVIServerMessageFrame(data={
                    "type": "animation-event", 
                    "payload": {"animation_id": animation_id}
                })
                await rtvi.push_frame(frame)
                logger.info(f"Animation triggered: {animation_id}")
                result = {"status": "animation_triggered"}
            else:
                result = {
                    "status": "error",
                    "error": f"Invalid animation ID. Valid IDs: {allowed_animations}"
                }
        except Exception as e:
            logger.error(f"Animation handler error: {str(e)}")
            result = {
                "status": "error", 
                "error": f"Failed to handle animation: {str(e)}\n{traceback.format_exc()}"
            }
        
        # Handle result based on paradigm
        if isinstance(params, FunctionCallParams):
            await params.result_callback(result)
        
        return result