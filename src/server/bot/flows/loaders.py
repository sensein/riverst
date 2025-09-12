from typing import Dict, Any, Tuple, Optional
import json
import importlib.util
import sys
from pathlib import Path

from pipecat_flows import NodeConfig, FlowConfig

from .models.config_models import FlowConfigurationFile
from .handlers import (
    get_activity_handler,
    general_handler,
    get_user_handler,
    get_variable_action_handler,
)


def load_custom_handler(handler_name: str, flow_config_path: str) -> callable:
    """
    Load a custom handler function from an activity's handlers.py file.

    Args:
        handler_name: Name of the handler function to load
        flow_config_path: Path to the flow_config.json file

    Returns:
        The handler function

    Raises:
        FileNotFoundError: If handlers.py doesn't exist for the activity
        AttributeError: If the handler function doesn't exist in the module
        ImportError: If there's an error importing the handlers module
    """
    # Get activity directory from flow_config path
    flow_config_file = Path(flow_config_path)
    activity_dir = flow_config_file.parent
    handlers_file = activity_dir / "handlers.py"

    if not handlers_file.exists():
        raise FileNotFoundError(
            f"Custom handler file not found: {handlers_file}. "
            f"Create handlers.py in the activity directory."
        )

    try:
        # Create a unique module name to avoid conflicts
        activity_name = activity_dir.name
        module_name = f"activity_{activity_name}_handlers"

        # Load the module
        spec = importlib.util.spec_from_file_location(module_name, handlers_file)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load module spec for {handlers_file}")

        module = importlib.util.module_from_spec(spec)

        # Add to sys.modules to handle potential circular imports
        sys.modules[module_name] = module

        # Execute the module
        spec.loader.exec_module(module)

        # Get the handler function
        if not hasattr(module, handler_name):
            available_handlers = [
                attr for attr in dir(module) if not attr.startswith("_")
            ]
            raise AttributeError(
                f"Handler '{handler_name}' not found in {handlers_file}. "
                f"Available handlers: {available_handlers}"
            )

        handler_func = getattr(module, handler_name)

        # Verify it's callable
        if not callable(handler_func):
            raise ValueError(
                f"'{handler_name}' in {handlers_file} is not a callable function"
            )

        return handler_func

    except Exception as e:
        raise ImportError(
            f"Error loading custom handler '{handler_name}' from {handlers_file}: {str(e)}"
        ) from e


def resolve_handler(handler_string: str, flow_config_path: str) -> callable:
    """
    Resolve a handler string to the actual handler function.

    Args:
        handler_string: Handler identifier (e.g., "general_handler" or "activity:my_handler")
        flow_config_path: Path to the flow_config.json file

    Returns:
        The resolved handler function
    """
    # Handle built-in handlers
    if handler_string == "general_handler":
        return general_handler
    elif handler_string == "get_activity_handler":
        return get_activity_handler
    elif handler_string == "get_user_handler":
        return get_user_handler
    elif handler_string == "get_variable_action_handler":
        return get_variable_action_handler

    # Handle custom activity handlers
    elif handler_string.startswith("activity:"):
        handler_name = handler_string[9:]  # Remove "activity:" prefix
        return load_custom_handler(handler_name, flow_config_path)

    else:
        raise ValueError(
            f"Unknown handler: '{handler_string}'. "
            f"Use built-in handlers (general_handler, get_activity_handler, etc.) "
            f"or custom handlers with 'activity:' prefix."
        )


def load_config(
    flow_config_path: str,
    activity_variables_path: Optional[str] = None,
    user_variables: Optional[dict[str, Any]] = None,
    end_conversation_handler=None,
) -> Tuple[FlowConfig, Dict[str, Any]]:
    """
    Loads and validates the flow configuration from a JSON file.
    """
    flow_config_file = Path(flow_config_path)

    if not flow_config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {flow_config_path}")

    flow_config_data = json.loads(flow_config_file.read_text())

    if "state_config" not in flow_config_data:
        raise ValueError(
            "State configuration is missing in the flow configuration file."
        )

    # Only check session variables if path is provided
    if activity_variables_path:
        activity_variables_file = Path(activity_variables_path)
        if activity_variables_file.exists():
            activity_variables = load_activity_variables(activity_variables_path)
            flow_config_data["state_config"]["activity"] = activity_variables

        # If user_variables is provided, merge it with existing user data
        existing_user = flow_config_data["state_config"].get("user", {})
        flow_config_data["state_config"]["user"] = {**existing_user, **user_variables}

    # Validate the complete configuration
    flow_config_data = FlowConfigurationFile(**flow_config_data)

    # Extract state and flow configurations
    state = get_flow_state(flow_config_data)
    flow_config = get_flow_config(
        flow_config_data,
        flow_config_path,
        end_conversation_handler=end_conversation_handler,
    )

    return flow_config, state


def load_activity_variables(activity_variables_path: Optional[str]) -> Dict[str, Any]:

    if not activity_variables_path:
        return {}

    activity_variables_file = Path(activity_variables_path)

    if not activity_variables_file.exists():
        raise FileNotFoundError(
            f"Session variables file not found: {activity_variables_path}"
        )

    try:
        activity_variables = json.loads(activity_variables_file.read_text())
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Invalid JSON in session variables file: {activity_variables_path}"
        ) from e

    return activity_variables


def get_flow_config(
    config: FlowConfigurationFile, flow_config_path: str, end_conversation_handler=None
) -> FlowConfig:
    """
    Extracts and processes the flow configuration from a validated configuration object.

    This function resolves handler references in the flow configuration to actual function references,
    and validates the final node configurations against the NodeConfig schema.

    Args:
        config: A validated FlowConfigurationFile object containing the complete configuration
        flow_config_path: The file path to the flow configuration
        end_conversation_handler: Optional handler for ending conversations

    Returns:
        FlowConfig: A validated flow configuration with function references resolved
    """
    # Get raw dictionary data
    flow_config_dict = {"initial_node": config.flow_config.initial_node, "nodes": {}}

    # Process nodes to resolve function references
    for node_id, node in config.flow_config.nodes.items():
        # Convert to dict if not already
        node_dict = node
        if not isinstance(node, dict):
            node_dict = node.model_dump() if hasattr(node, "model_dump") else node

        # Process functions to assign actual handler references
        if "functions" in node_dict:
            for func_def in node_dict["functions"]:
                handler_string = func_def.get("function", {}).get("handler")
                if handler_string:
                    try:
                        func_def["function"]["handler"] = resolve_handler(
                            handler_string, flow_config_path
                        )
                    except (
                        FileNotFoundError,
                        AttributeError,
                        ImportError,
                        ValueError,
                    ) as e:
                        raise ValueError(
                            f"Failed to resolve handler '{handler_string}' in node '{node_id}': {str(e)}"
                        ) from e

        # Actions also need to resolve handlers
        if "pre_actions" in node_dict:
            for action in node_dict["pre_actions"]:
                handler_string = action.get("handler")
                if handler_string == "end_conversation_handler":
                    if end_conversation_handler is None:
                        raise ValueError(
                            "Configuration requests 'end_conversation_handler', but no handler was provided."
                        )
                    action["handler"] = end_conversation_handler.handle_end_conversation
                elif handler_string:
                    try:
                        action["handler"] = resolve_handler(
                            handler_string, flow_config_path
                        )
                    except (
                        FileNotFoundError,
                        AttributeError,
                        ImportError,
                        ValueError,
                    ) as e:
                        raise ValueError(
                            f"Failed to resolve pre_action handler '{handler_string}' in node '{node_id}': {str(e)}"
                        ) from e

        if "post_actions" in node_dict:
            for action in node_dict["post_actions"]:
                handler_string = action.get("handler")
                if handler_string:
                    try:
                        action["handler"] = resolve_handler(
                            handler_string, flow_config_path
                        )
                    except (
                        FileNotFoundError,
                        AttributeError,
                        ImportError,
                        ValueError,
                    ) as e:
                        raise ValueError(
                            f"Failed to resolve post_action handler '{handler_string}' in node '{node_id}': {str(e)}"
                        ) from e

        # Store the processed node
        flow_config_dict["nodes"][node_id] = NodeConfig(**node_dict)

    return FlowConfig(**flow_config_dict)


def get_flow_state(config: FlowConfigurationFile) -> Dict[str, Any]:
    """
    Extracts and validates the state configuration from a validated configuration object.

    This function retrieves the state configuration portion and validates it against
    the StateConfig schema to ensure it contains all required fields and proper structure.

    Args:
        config: A validated FlowConfigurationFile object containing the complete configuration

    Returns:
        Dict[str, Any]: The validated state configuration containing initial state values,
        stage definitions, and any custom state information

    Raises:
        ValidationError: If the state configuration fails validation against the StateConfig schema
    """
    state_config = config.state_config

    state_dict = {
        "stages": {
            k: v.model_dump() if hasattr(v, "model_dump") else v
            for k, v in state_config.stages.items()
        },
        "user": state_config.user,
        "activity": state_config.activity,
    }

    return state_dict
