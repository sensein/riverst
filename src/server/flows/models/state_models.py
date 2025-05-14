"""
State configuration models.

This module defines Pydantic models that represent the structure of
state configurations in the flow system.
"""
from typing import Dict, List, Any, Optional, Union, Set
from pydantic import BaseModel, Field, root_validator


class ChecklistModel(BaseModel):
    """
    A checklist of boolean flags for a stage.
    
    Each item in the checklist must be initialized to False.
    """
    __root__: Dict[str, bool]
    
    @root_validator(pre=True)
    def validate_all_false(cls, values):
        """Validates that all checklist items are initialized to False."""
        if not isinstance(values.get("__root__", {}), dict):
            return values
            
        for key, value in values["__root__"].items():
            if not isinstance(value, bool):
                raise ValueError(f"Checklist item '{key}' must be a boolean, got {type(value)}")
            if value is not False:
                raise ValueError(f"Checklist item '{key}' must be initialized to False")
        return values


class StageModel(BaseModel):
    """
    A stage in the flow with its checklist and messages.
    """
    checklist: ChecklistModel
    checklist_incomplete_message: str
    checklist_complete_message: str
    next_stage: Optional[str] = None
    
    class Config:
        extra = "allow"  # Allow additional stage configuration


class StateConfig(BaseModel):
    """
    Configuration for the application state.
    
    Defines the structure of the state, including stages with checklists,
    general information, and task-specific variables.
    """
    stages: Dict[str, StageModel]
    info: Dict[str, Any]
    task_variables: Dict[str, Any]
    
    @root_validator
    def validate_field_uniqueness(cls, values):
        """
        Validates that field names are unique across different sections.
        
        Ensures there's no overlap between checklist fields, info fields,
        and task_variable fields.
        """
        if not all(k in values for k in ["stages", "info", "task_variables"]):
            # Skip validation if any required field is missing
            return values
            
        # Collect all checklist fields
        checklist_fields: Set[str] = set()
        for stage in values["stages"].values():
            checklist_fields.update(stage.checklist.__root__.keys())
            
        info_fields = set(values["info"].keys())
        task_variable_fields = set(values["task_variables"].keys())
        
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
            
        return values

