"""
Schema models for flow configuration.

This module defines Pydantic models that represent the structure of
schema configurations in the flow system.
"""
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, RootModel


class SchemaProperty(BaseModel):
    """A property in a schema definition."""
    type: str
    description: str
    items: Optional[Dict[str, Any]] = None
    enum: Optional[List[Any]] = None


class FunctionSchema(BaseModel):
    """
    A function schema definition for flow system.
    
    Defines the structure and validation rules for a function that can be
    called during a flow conversation.
    """
    name: str
    description: str
    properties: Dict[str, SchemaProperty]
    required: List[str]
    transition_callback: Optional[str] = None
    transition_to: Optional[str] = None
    
    model_config = {"extra": "allow"} 


class SchemasConfig(RootModel):
    """
    Configuration for all function schemas in the flow.
    
    This is a collection of named function schemas that can be used
    throughout the flow.
    """
    root: Dict[str, FunctionSchema]
    
    def __getitem__(self, key):
        return self.root[key]
    
    def __iter__(self):
        return iter(self.root)
    
    def __len__(self):
        return len(self.root)
    
    def items(self):
        return self.root.items()
    
    def keys(self):
        return self.root.keys()
    
    def values(self):
        return self.root.values()