"""
State configuration models.

This module defines Pydantic models that represent the structure of
state configurations in the flow system.
"""
from typing import Dict, Any, Set
from pydantic import BaseModel, model_validator, field_validator



class StageModel(BaseModel):
    """
    A stage in the flow with its checklist and messages.
    """
    checklist: Dict[str, bool] 
    checklist_incomplete_message: str
    checklist_complete_message: str
    next_stage: str
    
    model_config = {"extra": "allow"} 
    
    @field_validator('checklist')
    @classmethod
    def validate_checklist(cls, checklist):
        """Validates that all checklist items are booleans initialized to False."""
        for key, value in checklist.items():
            if not isinstance(value, bool):
                raise ValueError(f"Checklist item '{key}' must be a boolean, got {type(value)}")
            if value is not False:
                raise ValueError(f"Checklist item '{key}' must be initialized to False")
        return checklist
    
    @field_validator('checklist_incomplete_message', 'checklist_complete_message', 'next_stage')
    def validate_str_fields(cls, message):
        """Validates that all these fields are strings."""
        if not isinstance(message, str):
            raise ValueError(f"{message} must be a string, got {type(message)}")
        return message


class StateConfig(BaseModel):
    """
    Configuration for the application state.
    
    Defines the structure of the state, including stages with checklists,
    general information, and task-specific variables.
    """
    stages: Dict[str, StageModel]
    info: Dict[str, Any]
    task_variables: Dict[str, Any]
    
        
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
    def validate_field_uniqueness(self):
        """
        Validates that field names are unique across different sections.
        
        Ensures there's no overlap between checklist fields, info fields,
        and task_variable fields.
        """
        # Collect all checklist fields
        checklist_fields: Set[str] = set()
        for stage in self.stages.values():
            checklist_fields.update(stage.checklist.keys())
            
        info_fields = set(self.info.keys())
        task_variable_fields = set(self.task_variables.keys())
        
        # Check for overlaps
        info_checklist_overlap = checklist_fields.intersection(info_fields)
        if info_checklist_overlap:
            raise ValueError(f"Fields {info_checklist_overlap} appear in both checklist and info")
            
        task_checklist_overlap = checklist_fields.intersection(task_variable_fields)
        if task_checklist_overlap:
            raise ValueError(f"Fields {task_checklist_overlap} appear in both checklist and task_variables")
            
        info_task_overlap = info_fields.intersection(task_variable_fields)
        if info_task_overlap:
            raise ValueError(f"Fields {info_task_overlap} appear in both info and task_variables")
            
        return self
    

