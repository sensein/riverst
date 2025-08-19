from typing import Dict, Any, Tuple, Optional
import json
from pathlib import Path

from pipecat_flows import NodeConfig, FlowConfig

from .models.config_models import FlowConfigurationFile
from .handlers import (
    get_session_variable_handler,
    general_handler,
    get_info_variable_handler,
    get_variable_action_handler,
)


def load_config(
    flow_config_path: str,
    activity_variables_path: Optional[str] = None,
    user_activity_variables: Optional[dict[str, Any]] = None,
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
            flow_config_data["state_config"]["activity_variables"] = activity_variables

    elif user_activity_variables:
        # If user_activity_variables is provided, use it directly
        flow_config_data["state_config"][
            "user_activity_variables"
        ] = user_activity_variables

    # Validate the complete configuration
    flow_config_data = FlowConfigurationFile(**flow_config_data)

    # Extract state and flow configurations
    state = get_flow_state(flow_config_data)
    flow_config = get_flow_config(
        flow_config_data, end_conversation_handler=end_conversation_handler
    )

    return flow_config, state


def load_activity_variables(activity_variables_path: Optional[str]) -> Dict[str, Any]:
    """
    [Your existing docstring - but remove Optional from return type since you return {} not None]
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
    config: FlowConfigurationFile, end_conversation_handler=None
) -> FlowConfig:
    """
    Extracts and processes the flow configuration from a validated configuration object.

    This function resolves handler references in the flow configuration to actual function references,
    and validates the final node configurations against the NodeConfig schema.

    Args:
        config: A validated FlowConfigurationFile object containing the complete configuration
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
                if func_def.get("function", {}).get("handler") == "general_handler":
                    func_def["function"]["handler"] = general_handler
                elif (
                    func_def.get("function", {}).get("handler")
                    == "get_session_variable_handler"
                ):
                    func_def["function"]["handler"] = get_session_variable_handler
                elif (
                    func_def.get("function", {}).get("handler")
                    == "get_info_variable_handler"
                ):
                    func_def["function"]["handler"] = get_info_variable_handler

        # Actions also need to resolve handlers
        if "pre_actions" in node_dict:
            for action in node_dict["pre_actions"]:
                if action.get("handler") == "get_variable_action_handler":
                    action["handler"] = get_variable_action_handler
                if action.get("handler") == "end_conversation_handler":
                    if end_conversation_handler is None:
                        raise ValueError(
                            "Configuration requests 'end_conversation_handler', but no handler was provided."
                        )
                    action["handler"] = end_conversation_handler.handle_end_conversation

        if "post_actions" in node_dict:
            for action in node_dict["post_actions"]:
                if action.get("handler") == "get_variable_action_handler":
                    action["handler"] = get_variable_action_handler

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
        "info": state_config.info,
        "activity_variables": state_config.activity_variables,
    }

    return state_dict
