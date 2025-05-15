"""
Complete flow configuration models.

This module defines Pydantic models that represent the full structure of
the configuration files used in the flow system.
"""
from typing import Any
from pydantic import BaseModel, model_validator

from .schema_models import SchemasConfig
from .node_models import NodesConfig
from .state_models import StateConfig



class FlowConfigurationFile(BaseModel):
    """
    Complete configuration for a flow.
    
    This model represents the entire structure of a flow configuration file,
    including metadata, state configuration, flow configuration, and schemas.
    """
    name: str
    description: str
    state_config: StateConfig
    nodes_config: NodesConfig
    schemas: SchemasConfig
    
    def __getitem__(self, key: str) -> Any:
        """Allow dictionary-like access to attributes."""
        return getattr(self, key)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Implement dictionary-like get method with default value."""
        try:
            return getattr(self, key)
        except AttributeError:
            return default
    
    def keys(self):
        """Return a list of attribute names."""
        return self.model_fields.keys()
    
    def items(self):
        """Return (key, value) pairs for all attributes."""
        return {k: getattr(self, k, None) for k in self.model_fields.keys()}.items()
    
    def values(self):
        """Return values of all attributes."""
        return [getattr(self, k, None) for k in self.model_fields.keys()]
    
    @model_validator(mode='after')
    def validate_flow_structure(self):
        """
        Validates that the flow structure is consistent.
        
        Checks:
        1. All functions referenced in nodes exist in schemas
        2. All stage names in state_config match node names in node_config
        """
        # Access values via self attributes
        node_config = self.nodes_config
        schemas = self.schemas
        state_config = self.state_config

        
        # Check that all function references exist
        for node_name, node in node_config.nodes.items():
            if node["functions"]:
                for func_name in node["functions"]:
                    if str(func_name) not in schemas:
                        raise ValueError(f"Node '{node_name}' references non-existent function '{func_name}'")
        
        # Check that all stage names match node names
        stage_names = set(state_config.stages.keys())
        node_names = set(node_config.nodes.keys())
        missing_stages = stage_names - node_names
        if missing_stages:
            raise ValueError(f"The following stages in state_config do not have matching nodes: {missing_stages}")
            
        return self