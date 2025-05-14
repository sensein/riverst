"""
Functions for loading and validating flow state configuration.
"""
import os
import json
from typing import Dict, Any, Optional
from pydantic import ValidationError

from ..configs.models import StateConfig
from ..utils import load_config


async def get_flow_state() -> Dict[str, Any]:
    """
    Get and validate the flow state configuration.
    
    Returns:
        The validated flow state configuration
    """

    # Load the configuration file (validated structure)
    config = load_config()

    state = config.get("state_config")

    # Validate state against model
    StateConfig(**state)
    
    return state

