"""
Flow configuration models package.

This package contains Pydantic models that define the structure and validation
rules for flow configuration files.
"""

# Import models in dependency order
from .node_models import Message, PostAction, NodesConfig
from .state_models import StageModel, StateConfig

# Import the complete config model last to avoid circular dependencies
from .config_models import FlowConfigurationFile

# Ensure all models are fully rebuilt after all imports
NodesConfig.model_rebuild()
FlowConfigurationFile.model_rebuild()

__all__ = [
    # Flow models
    "Message",
    "PostAction",
    "NodesConfig",
    # State models
    "StageModel",
    "StateConfig",
    # Complete config model
    "FlowConfigurationFile",
]
