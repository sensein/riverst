""" 
Node configuration models.

This module defines Pydantic models that represent the structure of 
node configurations in the flow system. 
"""
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, model_validator

from pipecat_flows import NodeConfig



class Message(BaseModel):
    """A message in the flow conversation."""
    role: str
    content: str


class PostAction(BaseModel):
    """An action to perform after a node completes."""
    type: str
    
    model_config = {"extra": "allow"} 

    


class NodesConfig(BaseModel):
    """
    Configuration for the conversation flow.
    
    Defines the structure of the conversation, including the initial node
    and all available nodes with their properties.
    """
    initial_node: str
    nodes: Dict[str, NodeConfig]
    
    @model_validator(mode='after')
    def validate_node_config(self):
        
        """Validate the node configuration structure."""
        # Check that the initial node exists
        if self.initial_node not in self.nodes:
            raise ValueError(f"Initial node '{self.initial_node}' not found in nodes")
    
        return self
    
    def __getitem__(self, key: str) -> Any:
        """Allow dictionary-like access to attributes."""
        if key == "nodes" and hasattr(self, "nodes"):
            return self.nodes
        if key == "initial_node" and hasattr(self, "initial_node"):
            return self.initial_node
        return getattr(self, key)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Implement dictionary-like get method with default value."""
        try:
            return self[key]
        except (KeyError, AttributeError):
            return default
    
    def keys(self):
        """Return a list of attribute names."""
        return self.model_dump().keys()
    
    def items(self):
        """Return (key, value) pairs for all attributes."""
        return self.model_dump().items()
    
    def values(self):
        """Return values of all attributes."""
        return self.model_dump().values()