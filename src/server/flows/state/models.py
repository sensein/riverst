"""
Data models for flow state validation using Pydantic.
"""
from typing import Dict, Any
from pydantic import BaseModel, Field, validator, root_validator


class ChecklistModel(BaseModel):
    """
    Represents a checklist with boolean values that must be False initially.
    """
    __root__: Dict[str, bool]
    
    @validator('__root__')
    def all_values_must_be_false(cls, checklist):
        for field, value in checklist.items():
            if not isinstance(value, bool):
                raise ValueError(f"Field '{field}' is not a boolean")
            if value is not False:
                raise ValueError(f"Field '{field}' is not initialized to False")
        return checklist


class StageModel(BaseModel):
    """
    Represents a stage with its required fields.
    """
    checklist: ChecklistModel
    checklist_incomplete_message: str
    checklist_complete_message: str


class FlowStateModel(BaseModel):
    """
    Validates the entire flow state structure.
    """
    stages: Dict[str, StageModel] = Field(..., min_items=1)
    info: Dict[str, Any]
    task_variables: Dict[str, Any]
    
    @root_validator
    def check_field_duplication(cls, values):
        """Check for field duplications across different sections."""
        stages = values.get('stages', {})
        info = values.get('info', {})
        task_variables = values.get('task_variables', {})
        
        # collect all checklist fields
        all_checklist_fields = set()
        for stage_data in stages.values():
            all_checklist_fields.update(stage_data.checklist.__root__.keys())
        
        info_fields = set(info.keys())
        task_variable_fields = set(task_variables.keys())
        
        # check for duplications
        checklist_info_duplicates = all_checklist_fields.intersection(info_fields)
        if checklist_info_duplicates:
            raise ValueError(f"Fields {checklist_info_duplicates} are duplicated in checklists and info")
            
        checklist_task_duplicates = all_checklist_fields.intersection(task_variable_fields)
        if checklist_task_duplicates:
            raise ValueError(f"Fields {checklist_task_duplicates} are duplicated in checklists and task_variables")
            
        info_task_duplicates = info_fields.intersection(task_variable_fields)
        if info_task_duplicates:
            raise ValueError(f"Fields {info_task_duplicates} are duplicated in info and task_variables")
            
        return values