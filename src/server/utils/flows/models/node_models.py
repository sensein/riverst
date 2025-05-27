""" 
Node configuration models.

This module defines Pydantic models that represent the structure of 
node configurations in the flow system. 
"""
from typing import Dict, Any, List, Optional, Union, Literal
from pydantic import BaseModel, model_validator, field_validator, Field
from pipecat_flows import NodeConfig


class Message(BaseModel):
    """A message in the flow conversation."""
    role: str
    content: str


class PostAction(BaseModel):
    """An action to perform after a node completes."""
    type: str
    
    model_config = {"extra": "allow"} 


class FunctionParameters(BaseModel):
    """Parameters for a function in a node."""
    type: Literal["object"]
    properties: Dict[str, Dict[str, Any]]
    required: List[str]


class FunctionDefinition(BaseModel):
    """Definition of a function in a node."""
    name: str
    description: str
    parameters: FunctionParameters
    transition_callback: Optional[str] = None
    
    @field_validator('parameters')
    @classmethod
    def validate_parameters(cls, parameters):
        """Validates that the parameters structure is valid."""
        if parameters.type != "object":
            raise ValueError("Parameters type must be 'object'")
        
        if not parameters.properties:
            raise ValueError("Parameters must have properties")
        
        return parameters


class Function(BaseModel):
    """A function in a node."""
    type: Literal["function"]
    function: FunctionDefinition
    
    @field_validator('function')
    @classmethod
    def validate_function(cls, function):
        """Validates the function structure."""
        # Ensure transition_callback is present
        if not function.transition_callback:
            raise ValueError("Function must include transition_callback")
        
        # Ensure transition_to is not present
        if hasattr(function, 'transition_to'):
            raise ValueError("Function must not include transition_to")
        
        return function


class Node(BaseModel):
    """A node in the flow configuration."""
    role_messages: Optional[List[Message]] = None
    task_messages: List[Message]
    functions: List[Function] = Field(default_factory=list)
    post_actions: Optional[List[PostAction]] = None
    
    @field_validator('functions')
    @classmethod
    def validate_functions(cls, functions, info):
        """Validates the functions list."""
        # For nodes other than 'end', ensure there is at least one function (for transition)
        if info.data.get('name') != 'end' and len(functions) < 1:
            raise ValueError(f"Node functions list must have at least one element, found {len(functions)}")
        
        return functions


class NodesConfig(BaseModel):
    """
    Configuration for the conversation flow.
    
    Defines the structure of the conversation, including the initial node
    and all available nodes with their properties.
    """
    initial_node: str
    nodes: Dict[str, Any]  # Changed from NodeConfig to Any to handle raw dictionaries
    
    @model_validator(mode='after')
    def validate_node_config(self):
        """Validate the node configuration structure."""
        # Check that the initial node exists
        if self.initial_node not in self.nodes:
            raise ValueError(f"Initial node '{self.initial_node}' not found in nodes")
        
        # Check that the initial node has role_messages
        initial_node = self.nodes[self.initial_node]
        if not isinstance(initial_node, dict):
            initial_node = initial_node.model_dump() if hasattr(initial_node, 'model_dump') else initial_node
            
        if 'role_messages' not in initial_node or not initial_node['role_messages']:
            raise ValueError("Initial node must have role_messages")
        
        # Check that all nodes have the required fields
        for node_id, node in self.nodes.items():
            if node_id == 'end':
                continue  # Skip validation for 'end' node
                
            node_dict = node
            if not isinstance(node, dict):
                node_dict = node.model_dump() if hasattr(node, 'model_dump') else node
                
            # Check task_messages exist
            if 'task_messages' not in node_dict or not node_dict['task_messages']:
                raise ValueError(f"Node '{node_id}' must have task_messages")
                
            # Check functions exist and are a list
            if 'functions' not in node_dict or not isinstance(node_dict['functions'], list):
                raise ValueError(f"Node '{node_id}' must have a functions list")
    
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