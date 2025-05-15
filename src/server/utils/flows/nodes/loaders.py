"""
Functions for loading flow configuration from JSON files.
"""
from typing import Dict, Union

from ..utils.module_utils import OverwritePolicy, get_module_globals
from ..models import FlowConfigurationFile

from pipecat_flows import NodeConfig

def get_flow_nodes(
    flow_config: FlowConfigurationFile,
    module=None,
    overwrite_policy: Union[str, OverwritePolicy] = OverwritePolicy.RAISE,
    initialize_schemas_first: bool = True
) -> Dict[str, NodeConfig]:
    """
    Load flow configuration from JSON file and resolve function references
    to actual schema objects in the namespace. This function automatically
    initializes schemas first by default.
    
    Args:
        flow_config: FlowConfigurationFile object containing the flow configuration.
        module: Module object where to look for schema objects. 
                Defaults to the calling module.
        overwrite_policy: How to handle conflicts with existing variables
        initialize_schemas_first: Whether to automatically initialize schemas
                                  before loading nodes (default: True)
    
    Returns:
        The flow nodes with resolved function references
        
    Raises:
        ValueError: If function references can't be resolved or variable conflicts exist
    """
    
    if isinstance(overwrite_policy, str):
        overwrite_policy = OverwritePolicy(overwrite_policy.lower())
    
    
    # Initialize schemas first if requested
    if initialize_schemas_first:
        from .schema_init import initialize_schemas
        initialize_schemas(flow_config, module, overwrite_policy)
    
    module_globals = get_module_globals(module)
    
    # validate flows config 
    nodes = flow_config.get("flow_config").get("nodes")
    
    missing_functions = set()
    for _, node in nodes.items():
    
        if "functions" in node and isinstance(node["functions"], list):
            resolved_functions = []
            for func_name in node["functions"]:
                if func_name in module_globals and callable(module_globals[func_name]):
                    resolved_functions.append(module_globals[func_name])
                else:
                    missing_functions.add(func_name)
                    # keep the string reference for now
                    resolved_functions.append(func_name)
            node["functions"] = resolved_functions
    
    if missing_functions:
        missing_list = ", ".join(missing_functions)
        raise ValueError(f"The following functions were not found in the namespace: {missing_list}")
    
    return nodes


def get_flow_initial_node(flow_config: FlowConfigurationFile) -> str:
    """
    Get the initial node from the flow configuration.
    
    Args:
        flow_config: FlowConfigurationFile object containing the flow configuration.
    
    Returns:
        The name of the initial node.
        
    Raises:
        ValueError: If no initial node is found in the configuration.
    """
    init_node = flow_config.get("node_config").get("initial_node")
    if not init_node:
        raise ValueError("No initial node found in the configuration.")

    return init_node