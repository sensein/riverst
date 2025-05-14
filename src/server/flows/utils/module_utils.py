"""
Utility functions for module manipulation and configuration.
"""
import sys
import os
from enum import Enum
from typing import Dict, Any, Optional
from ..models import FlowConfigurationFile


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


def load_config() -> FlowConfigurationFile:
    """
    Load and validate the flow configuration from a JSON file, set in FLOW_CONFIG_PATH environment variable.
    """
    json_file_path: str = os.getenv("FLOW_CONFIG_PATH"),
    with open(json_file_path, 'r') as f:
        config = json.load(f)
        
    # validate the config
    FlowConfigurationFile(**config)
    
    return config
