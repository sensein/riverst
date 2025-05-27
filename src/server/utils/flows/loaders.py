import os
from typing import Dict, Any, Tuple, Optional
import json
from pydantic import ValidationError

from pipecat_flows import NodeConfig, FlowConfig

from .models.config_models import FlowConfigurationFile
from .handlers import general_transition_callback, get_session_variable_handler, general_handler, get_info_variable_handler


def load_config(flow_config_path: str, session_variables_path: Optional[str]) -> Tuple[FlowConfig, Dict[str, Any]]:
    """
    Loads and validates a flow configuration from a JSON file.
    
    This function reads the JSON file, validates its structure against the FlowConfigurationFile
    schema, and extracts both the flow configuration and state configuration.
    
    Args:
        flow_config_path: Path to the JSON configuration file containing both flow and state configurations
        
    Returns:
        A tuple containing:
            - flow_config (Dict[str, NodeConfig]): The validated flow configuration with node definitions
            - state (Dict[str, Any]): The validated state configuration containing state information
            
    Raises:
        FileNotFoundError: If the specified configuration file doesn't exist
        JSONDecodeError: If the file contains invalid JSON
        ValidationError: If the configuration doesn't match the expected schema
    """
    if not os.path.exists(flow_config_path):
        raise FileNotFoundError(f"Configuration file not found: {flow_config_path}")    
    
    with open(flow_config_path, 'r') as f:
        config_data = json.load(f)
    session_variables = load_session_variables(session_variables_path)
    
    if session_variables:
        if config_data.get('state_config') is None:
            raise ValueError("State configuration is missing in the flow configuration file.")
        config_data['state_config']['session_variables'] = session_variables

    # Validate the complete configuration
    config_data = FlowConfigurationFile(**config_data)
    
    # Extract state and flow configurations
    state = get_flow_state(config_data)
    flow_config = get_flow_config(config_data)
    
    return flow_config, state


def load_session_variables(session_variables_path: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Loads session variables from a JSON file.
    
    This function reads the JSON file containing session variables and returns them as a dictionary.
    
    Args:
        session_variables_path: Path to the JSON file containing session variables
        
    Returns:
        Dict[str, Any]: A dictionary containing the session variables, or an empty dictionary if the path is None
        
    Raises:
        FileNotFoundError: If the specified file doesn't exist
        JSONDecodeError: If the file contains invalid JSON
    """
    if not session_variables_path:
        return {}
    
    if not os.path.exists(session_variables_path):
        raise FileNotFoundError(f"Session variables file not found: {session_variables_path}")
    
    with open(session_variables_path, 'r') as f:
        session_variables = json.load(f)
    
    return session_variables
    


def get_flow_config(config: FlowConfigurationFile) -> FlowConfig:
    """
    Extracts and processes the flow configuration from a validated configuration object.
    
    This function resolves transition function references to actual callback functions,
    assigns handlers, and validates the final node configurations against the NodeConfig schema.
    
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
        
        # Process functions to assign actual callback references
        if 'functions' in node_dict and node_dict['functions']:
            for func_def in node_dict['functions']:
                if func_def.get('function', {}).get('transition_callback') == 'general_transition_callback':
                    func_def['function']['transition_callback'] = general_transition_callback
                if func_def.get('function', {}).get('handler') == 'general_handler':
                    func_def['function']['handler'] = general_handler
                elif func_def.get('function', {}).get('handler') == 'get_session_variable_handler':
                    func_def['function']['handler'] = get_session_variable_handler
                elif func_df.get('function', {}).get('handler') == 'get_info_variable_handler':
                    func_def['function']['handler'] = get_info_variable_handler
        
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



