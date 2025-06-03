"""
Complete flow configuration models.

This module defines Pydantic models that represent the full structure of
the configuration files used in the flow system.
"""
from typing import Any, Dict
from pydantic import BaseModel, model_validator, Field

# Import required models
from .node_models import NodesConfig
from .state_models import StateConfig
    


class FlowConfigurationFile(BaseModel):
    """
    Complete configuration for a flow.
    
    This model represents the entire structure of a flow configuration file,
    including metadata, state configuration, and flow configuration.
    """
    name: str
    description: str
    state_config: StateConfig
    flow_config: NodesConfig  # Updated from node_config to flow_config to match JSON structure
    
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
        """
        # Access values via self attributes
        flow_config = self.flow_config
        state_config = self.state_config
        
        # Check that all stage names match node names
        stage_names = set(state_config.stages.keys())
        node_names = set(flow_config.nodes.keys())
        
        missing_stages = stage_names - node_names
        if missing_stages:
            raise ValueError(f"The following stages in state_config do not have matching nodes: {missing_stages}")
        
        # Check that an 'end' node exists
        if 'end' not in flow_config.nodes:
            raise ValueError("Configuration must include an 'end' node")
            
        # Check that all checklist items for each stage have corresponding parameters in function
        for stage_name, stage in state_config.stages.items():
            if stage_name == 'end':
                continue  # Skip checks for end node
                
            node = flow_config.nodes.get(stage_name)
            if not node or not hasattr(node, 'functions') or not node.functions:
                continue
                
            checklist_keys = set(stage.checklist.keys())
            
            # Check each function
            for func in node.functions:
                if not hasattr(func, 'function') or not hasattr(func.function, 'parameters'):
                    continue
                    
                params = func.function.parameters
                properties = params.get('properties', {})
                
                # Check that all checklist items have corresponding parameters
                property_keys = set(properties.keys())
                missing_checklist_params = checklist_keys - property_keys
                
                if missing_checklist_params:
                    raise ValueError(
                        f"Node '{stage_name}' checklist items {missing_checklist_params} "
                        f"do not have corresponding function parameters"
                    )
        
        return self