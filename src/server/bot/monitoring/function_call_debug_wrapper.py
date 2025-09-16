import json
import traceback
from functools import wraps
from loguru import logger
from pipecat.services.llm_service import FunctionCallParams


def function_call_debug(fn):
    """
    Decorator to add debug logging for function calls.
    """

    @wraps(fn)
    async def wrapper(*args, **kwargs):
        # Extract params from args - could be first arg (standalone function) or second arg (instance method)
        params = args[1] if len(args) > 1 else args[0] if args else kwargs.get("params")
        func_args = (
            params.arguments if isinstance(params, FunctionCallParams) else params
        )
        logger.info(
            "FUNCTION_DEBUG: Function '{}' called with args: {}",
            fn.__name__,
            json.dumps(func_args),
        )
        try:
            result = await fn(*args, **kwargs)
            logger.info(
                "FUNCTION_DEBUG: Function '{}' completed successfully with result: {}",
                fn.__name__,
                json.dumps(result) if result else "None",
            )
            return result
        except Exception as e:
            logger.error(
                "FUNCTION_DEBUG: Error in function '{}': {}",
                fn.__name__,
                str(e),
            )
            logger.error("FUNCTION_DEBUG: {}", traceback.format_exc())

            result = {
                "status": "error",
                "message": f"Execution error in '{fn.__name__}': {str(e)}",
            }

            if isinstance(params, FunctionCallParams):
                await params.result_callback(result)
            else:
                return result

    return wrapper
