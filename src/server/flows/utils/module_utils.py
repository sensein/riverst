"""
Utility functions for module manipulation and configuration.
"""
import sys
import os
from enum import Enum
from typing import Dict, Any, Optional
from ..models import FlowConfigurationFile
from ..configs.models import StateConfig
from ..configs.models import FlowConfig
from ..configs.models import SchemasConfig




class OverwritePolicy(str, Enum):
    """
    Enum defining policies for handling variable name conflicts during initialization.
    """
    RAISE = "raise"     # Raise an error if variables would be overwritten
    WARN = "warn"       # Print warning and continue with overwrite
    SKIP = "skip"       # Skip overwriting existing variables
    FORCE = "force"     # Overwrite without warnings


def get_module_globals(module=None) -> Dict[str, Any]:
    """
    Get the globals dictionary from a module or the caller's frame.
    
    Args:
        module: Module object whose globals should be returned.
                If None, get globals from the caller's frame.
    
    Returns:
        The globals dictionary from the specified module or frame.
    """
    if module is None:
        frame = sys._getframe(2)  # Two frames up to account for the wrapper
        return frame.f_globals
    return module.__dict__


def load_config(flow_config_path: str) -> FlowConfigurationFile:
    """
    Load and validate the flow configuration from a JSON file.
    """
    if not os.path.exists(flow_config_path):
        raise FileNotFoundError(f"Configuration file not found: {flow_config_path}")    
    
    with open(flow_config_path, 'r') as f:
        config = json.load(f)
        
    # validate the overall config
    FlowConfigurationFile(**config)
    
    # validate the subcomponents
    SchemasConfig(**config.get("schemas", {}))
    FlowConfig(**config.get("flow_config", {}))
    StateConfig(**config.get("state_config", {}))
    
    
    return config
