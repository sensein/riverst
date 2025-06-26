import os
from typing import Dict, Any, Tuple, Optional
import json
from pydantic import ValidationError
from pathlib import Path

from pipecat_flows import NodeConfig, FlowConfig

from .models.config_models import FlowConfigurationFile
from .handlers import get_session_variable_handler, general_handler, get_info_variable_handler, general_transition_callback, get_variable_action_handler


def load_config(flow_config_path: str, session_variables_path: Optional[str] = None) -> Tuple[FlowConfig, Dict[str, Any]]:
    """
    [Your existing docstring]
    """
    flow_config_file = Path(flow_config_path)
    
    if not flow_config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {flow_config_path}")

    config_data = json.loads(flow_config_file.read_text())

    if 'state_config' not in config_data:
        raise ValueError("State configuration is missing in the flow configuration file.")

    # Only check session variables if path is provided
    if session_variables_path:
        session_variables_file = Path(session_variables_path)
        if session_variables_file.exists():
            session_variables = load_session_variables(session_variables_path)
            config_data['state_config']['session_variables'] = session_variables

    # Validate the complete configuration
    config_data = FlowConfigurationFile(**config_data)

    # Extract state and flow configurations
    state = get_flow_state(config_data)
    flow_config = get_flow_config(config_data)

    return flow_config, state


def load_session_variables(session_variables_path: Optional[str]) -> Dict[str, Any]:
    """
    [Your existing docstring - but remove Optional from return type since you return {} not None]
    """
    if not session_variables_path:
        return {}
    
    session_variables_file = Path(session_variables_path)
    
    if not session_variables_file.exists():
        raise FileNotFoundError(f"Session variables file not found: {session_variables_path}")

    try:
        session_variables = json.loads(session_variables_file.read_text())
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in session variables file: {session_variables_path}") from e
    
    return session_variables
    


def get_flow_config(config: FlowConfigurationFile) -> FlowConfig:
    """
    Extracts and processes the flow configuration from a validated configuration object.
    
    This function resolves handler references in the flow configuration to actual function references,
    and validates the final node configurations against the NodeConfig schema.
    
    Args:
        config: A validated FlowConfigurationFile object containing the complete configuration
    
    Returns:
        FlowConfig: A validated flow configuration with function references resolved
    """
    # Get raw dictionary data
    flow_config_dict = {
        'initial_node': config.flow_config.initial_node,
        'nodes': {}
    }
    
    # Process nodes to resolve function references
    for node_id, node in config.flow_config.nodes.items():
        # Convert to dict if not already
        node_dict = node
        if not isinstance(node, dict):
            node_dict = node.model_dump() if hasattr(node, 'model_dump') else node
        
        # Process functions to assign actual handler references
        if 'functions' in node_dict:
            for func_def in node_dict['functions']:
                if func_def.get('function', {}).get('transition_callback') == 'general_transition_callback':
                    func_def['function']['transition_callback'] = general_transition_callback
                if func_def.get('function', {}).get('handler') == 'general_handler':
                    func_def['function']['handler'] = general_handler
                elif func_def.get('function', {}).get('handler') == 'get_session_variable_handler':
                    func_def['function']['handler'] = get_session_variable_handler
                elif func_def.get('function', {}).get('handler') == 'get_info_variable_handler':
                    func_def['function']['handler'] = get_info_variable_handler
                    
                    
        # Actions also need to resolve handlers
        if 'pre_actions' in node_dict:
            for action in node_dict['pre_actions']:
                if action.get('handler') == 'get_variable_action_handler':
                    action['handler'] = get_variable_action_handler
                    
        if 'post_actions' in node_dict:
            for action in node_dict['post_actions']:
                if action.get('handler') == 'get_variable_action_handler':
                    action['handler'] = get_variable_action_handler
                    
        # Store the processed node
        flow_config_dict['nodes'][node_id] = NodeConfig(**node_dict)
    
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
        'stages': {k: v.model_dump() if hasattr(v, 'model_dump') else v for k, v in state_config.stages.items()},
        'info': state_config.info,
        'session_variables': state_config.session_variables
    }
    
    return state_dict



