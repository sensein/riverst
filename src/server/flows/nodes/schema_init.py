"""
Functions for initializing function schemas from JSON configurations.
"""
import json
import os
import warnings
from typing import Dict, Any, Optional, Union

from pipecat_flows import FlowsFunctionSchema
from ..utils.module_utils import OverwritePolicy, get_module_globals, load_config
from ..state.handlers import general_handler

from ..models import FlowConfigurationFile


def initialize_schemas(
    flow_config: FlowConfigurationFile,
    module=None, 
    overwrite_policy: Union[str, OverwritePolicy] = OverwritePolicy.RAISE
) -> Dict[str, FlowsFunctionSchema]:
    """
    Load schemas from JSON file and convert to FlowsFunctionSchema objects.
    Sets them as global variables in the module, defaults to calling module.
    
    Args:
        flow_config: FlowConfigurationFile object containing the configuration data.
        module: Module object where schemas should be added as globals
                Defaults to the calling module
        overwrite_policy: How to handle conflicts with existing variables:
                          'raise' - Raise an error if any variables would be overwritten
                          'warn' - Print warning and continue with overwrite
                          'skip' - Skip overwriting existing variables
                          'force' - Overwrite without warnings

    Returns:
        A dictionary of schema names to FlowsFunctionSchema objects.
        
    Raises:
        ValueError: If overwrite_policy is 'raise' and conflicts are found
        FileNotFoundError: If json_file_path doesn't exist
    """
    if isinstance(overwrite_policy, str):
        overwrite_policy = OverwritePolicy(overwrite_policy.lower())
    
    module_globals = get_module_globals(module)
    
    schema_data = flow_config.get("schemas")

    
    schemas = {}
    for schema_name, config in schema_data.items():
        schemas[schema_name] = FlowsFunctionSchema(
            **config,
            handler=general_handler
        )
    
    conflicts = [name for name in schemas if name in module_globals]    
    if conflicts and overwrite_policy == OverwritePolicy.RAISE:
        raise ValueError(
            f"The following schema names would overwrite existing variables: {', '.join(conflicts)}. "
            "Use a different overwrite_policy to proceed."
        )
    
    skipped = []
    for schema_name, schema_obj in schemas.items():
        if schema_name in module_globals:
            if overwrite_policy == OverwritePolicy.WARN:
                warnings.warn(f"Overwriting existing variable '{schema_name}'")
                module_globals[schema_name] = schema_obj
            elif overwrite_policy == OverwritePolicy.SKIP:
                skipped.append(schema_name)
            elif overwrite_policy == OverwritePolicy.FORCE:
                module_globals[schema_name] = schema_obj
        else:
            module_globals[schema_name] = schema_obj
    
    if skipped and overwrite_policy == OverwritePolicy.SKIP:
        warnings.warn(f"Skipped setting the following schemas as they would overwrite existing variables: {', '.join(skipped)}")
            
    return schemas