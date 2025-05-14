"""
Complete flow configuration models.

This module defines Pydantic models that represent the full structure of
the configuration files used in the flow system.
"""
from typing import Dict, List, Any, Optional, Union
from pydantic import BaseModel, Field, root_validator

from .schema_models import SchemasConfig
from .flow_models import FlowConfig
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
    flow_config: FlowConfig
    schemas: SchemasConfig
    
    @root_validator
    def validate_flow_structure(cls, values):
        """
        Validates that the flow structure is consistent.
        
        Checks:
        1. All nodes referenced in next_stage exist
        2. All functions referenced in nodes exist in schemas
        3. All stage names in state_config match node names in flow_config
        """
        if not all(k in values for k in ["flow_config", "schemas", "state_config"]):
            # Skip validation if any required field is missing
            return values
            
        flow_config = values["flow_config"]
        schemas = values["schemas"].__root__
        state_config = values["state_config"]
        
        # Check that all next_stage references exist
        for node_name, node in flow_config.nodes.items():
            if node.next_stage and node.next_stage not in flow_config.nodes:
                raise ValueError(f"Node '{node_name}' references non-existent next_stage '{node.next_stage}'")
        
        # Check that all function references exist
        for node_name, node in flow_config.nodes.items():
            if node.functions:
                for func_name in node.functions:
                    if func_name not in schemas:
                        raise ValueError(f"Node '{node_name}' references non-existent function '{func_name}'")
        
        # Check that all stage names match node names
        stage_names = set(state_config.stages.keys())
        node_names = set(flow_config.nodes.keys())
        missing_stages = stage_names - node_names
        if missing_stages:
            raise ValueError(f"The following stages in state_config do not have matching nodes: {missing_stages}")
            
        return values