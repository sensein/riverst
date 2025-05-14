"""
Flow configuration models.

This module defines Pydantic models that represent the structure of
flow configurations in the flow system.
"""
from typing import Dict, List, Any, Optional, Union, Literal
from pydantic import BaseModel, Field


class Message(BaseModel):
    """A message in the flow conversation."""
    role: str
    content: str


class PostAction(BaseModel):
    """An action to perform after a node completes."""
    type: str
    # Additional fields can be added based on action type
    
    class Config:
        extra = "allow"  # Allow additional fields for different action types


class FlowNode(BaseModel):
    """
    A node in the conversation flow.
    
    Represents a specific state in the conversation with its own messages,
    functions, and transition rules.
    """
    role_messages: Optional[List[Message]] = []
    task_messages: Optional[List[Message]] = []
    functions: Optional[List[str]] = []
    next_stage: Optional[str] = None
    post_actions: Optional[List[PostAction]] = None
    
    class Config:
        extra = "allow"  # Allow additional node configuration options


class FlowConfig(BaseModel):
    """
    Configuration for the conversation flow.
    
    Defines the structure of the conversation, including the initial node
    and all available nodes with their properties.
    """
    initial_node: str
    nodes: Dict[str, FlowNode]