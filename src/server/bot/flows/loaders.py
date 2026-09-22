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


def _load_shared_persona() -> str:
    """
    Read and format the shared behavioral persona from shared_persona.json.

    Reads from disk on every call so scenario changes take effect in the next
    session without a server restart. Returns an empty string if the file is
    absent or malformed so callers can safely skip injection.

    Returns:
        A formatted system-prompt string assembled from all scenario
        instructions, or an empty string if the file is missing or invalid.
    """
    shared_persona_path = Path(__file__).parent.parent / "shared_persona.json"
    if not shared_persona_path.exists():
        return ""
    try:
        data = json.loads(shared_persona_path.read_text())
    except (json.JSONDecodeError, OSError):
        return ""
    scenarios = data.get("scenarios", [])
    if not scenarios:
        return ""
    lines = ["--- Shared Behavioral Guidelines ---"]
    for scenario in scenarios:
        name = scenario.get("name", "")
        instruction = scenario.get("instruction", "")
        if instruction:
            lines.append(f"[{name}] {instruction}")
    lines.append("--- End Shared Behavioral Guidelines ---")
    return "\n".join(lines)


def _inject_shared_persona(flow_config_data: Dict[str, Any]) -> None:
    """
    Inject the shared behavioral persona into every node's role_messages.

    Appends a system message containing all shared scenario instructions to
    the role_messages list of each node. Nodes without an existing
    role_messages field have one created. This is a no-op if the shared
    persona file is missing or contains no scenarios.

    Args:
        flow_config_data: Raw flow configuration dict, modified in place.
    """
    shared_persona_text = _load_shared_persona()
    if not shared_persona_text:
        return
    nodes = flow_config_data.get("flow_config", {}).get("nodes", {})
    for node_data in nodes.values():
        if not isinstance(node_data, dict):
            continue
        role_msgs = node_data.setdefault("role_messages", [])
        role_msgs.append({"role": "system", "content": shared_persona_text})


def load_config(
    flow_config_path: str,
    activity_variables_path: Optional[str] = None,
    user_variables: Optional[dict[str, Any]] = None,
    end_conversation_handler=None,
) -> Tuple[FlowConfig, Dict[str, Any]]:
    """
    Load and validate the flow configuration from a JSON file.

    Reads the flow config JSON, optionally merges activity and user variables
    into the state config, injects the shared behavioral persona into every
    node's role_messages, and validates the result against the
    FlowConfigurationFile schema.

    Args:
        flow_config_path: Path to the activity's flow_config.json file.
        activity_variables_path: Optional path to an activity variables JSON
            file whose contents are merged into state_config.activity.
        user_variables: Optional dict of user-specific values merged into
            state_config.user (takes precedence over existing keys).
        end_conversation_handler: Optional handler object whose
            handle_end_conversation method is wired to end_conversation_handler
            actions in pre_actions.

    Returns:
        A tuple of (FlowConfig, state_dict) ready for pipeline construction.

    Raises:
        FileNotFoundError: If flow_config_path does not exist.
        ValueError: If state_config is missing or handler resolution fails.
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

    # Inject shared behavioral persona into every node's role_messages
    _inject_shared_persona(flow_config_data)

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
    """
    Load activity variables from a JSON file.

    Args:
        activity_variables_path: Path to the activity variables JSON file,
            or None to return an empty dict.

    Returns:
        Dict of activity variable key-value pairs, or an empty dict if path
        is None.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file contains invalid JSON.
    """
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
