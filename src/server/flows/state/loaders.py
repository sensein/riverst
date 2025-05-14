"""
Functions for loading and validating flow state configuration.
"""
import os
import json
from typing import Dict, Any, Optional
from pydantic import ValidationError

from ..utils import load_config
from ..models import FlowConfigurationFile



async def get_flow_state(flow_config: FlowConfigurationFile) -> Dict[str, Any]:
    """
    Get and validate the flow state configuration.
    
    Args:
        flow_config: validated FlowConfigurationFile object.
    
    Returns:
        The validated flow state configuration
    """
    state = flow_config.get("state_config")
    
    return state

