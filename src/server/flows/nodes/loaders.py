"""
Functions for loading flow configuration from JSON files.
"""
import os
import json
from typing import Dict, Any, Optional, Union

from ..utils.module_utils import OverwritePolicy, get_module_globals, load_config
from ..models import FlowConfigurationFile, FlowConfig



async def get_flow_nodes(
    flow_config: FlowConfigurationFile,
    module=None,
    overwrite_policy: Union[str, OverwritePolicy] = OverwritePolicy.RAISE,
    initialize_schemas_first: bool = True
) -> Dict[str, Any]:
    """
    Load flow configuration from JSON file and resolve function references
    to actual schema objects in the namespace. This function automatically
    initializes schemas first by default.
    
    Args:
        flow_config_path: Path to the flow configuration JSON file.
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
        from ..config.schema_init import initialize_schemas
        initialize_schemas(flow_config, module, overwrite_policy)
    
    module_globals = get_module_globals(module)
    
    # validate flows config 
    nodes = flow_config.get("flow_config").get("nodes")
    
    missing_functions = set()
    for node_name, node in nodes.items():
    
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


async def get_flow_initial_node(flow_config_path: str) -> Optional[str]:
    """
    Get the initial node from the flow configuration. Validation is handled by load_config.
    
    Args:
        flow_config_path: Path to the flow configuration JSON file.
    
    Returns:
        The name of the initial node or None if not found.
    """
    config = load_config(flow_config_path)
    return config.get("initial_node")
