"""
State configuration models.

This module defines Pydantic models that represent the structure of
state configurations in the flow system.
"""

from typing import Dict, Any, Set, List, Optional, Literal
from pydantic import BaseModel, model_validator, field_validator


class ConditionParameters(BaseModel):
    """Parameters for a condition in transition logic."""

    variable_path: str
    operator: Literal["==", "!=", ">", ">=", "<", "<=", "in", "not_in"]
    value: Any


class Condition(BaseModel):
    """A condition for determining the next node in a flow."""

    parameters: ConditionParameters
    target_node: str


class TransitionLogic(BaseModel):
    """Logic for determining the next node in a flow."""

    conditions: List[Condition] = []
    default_target_node: str


class StageModel(BaseModel):
    """
    A stage in the flow with its checklist and messages.
    """

    checklist: Dict[str, bool]
    checklist_incomplete_message: str
    checklist_complete_message: Optional[str] = None
    next_stage: Optional[str] = None
    transition_logic: Optional[TransitionLogic] = None

    model_config = {"extra": "allow"}

    @field_validator("checklist")
    @classmethod
    def validate_checklist(cls, checklist):
        """Validates that all checklist items are booleans initialized to False."""
        for key, value in checklist.items():
            if not isinstance(value, bool):
                raise ValueError(
                    f"Checklist item '{key}' must be a boolean, got {type(value)}"
                )
            if value is not False:
                raise ValueError(f"Checklist item '{key}' must be initialized to False")
        return checklist

    @field_validator("checklist_incomplete_message")
    @classmethod
    def validate_messages(cls, value, info):
        """Validates that message fields are strings and contain the expected format."""
        if not isinstance(value, str):
            raise ValueError(f"{info.field_name} must be a string, got {type(value)}")

        # For incomplete message, ensure it has a placeholder for the missing items
        if "{}" not in value:
            raise ValueError(
                "checklist_incomplete_message must contain a placeholder '{}' for missing items"
            )

        return value

    @model_validator(mode="after")
    def validate_transition_fields(self):
        """Validates that either next_stage or transition_logic is provided, but not both."""
        if self.next_stage is None and self.transition_logic is None:
            raise ValueError("Either next_stage or transition_logic must be provided")
        if self.next_stage is not None and self.transition_logic is not None:
            raise ValueError(
                "Only one of next_stage or transition_logic can be provided"
            )
        return self


class StateConfig(BaseModel):
    """
    Configuration for the application state.

    Defines the structure of the state, including stages with checklists,
    general information, and task-specific variables.
    """

    stages: Dict[str, StageModel]
    info: Dict[str, Any]
    session_variables: Dict[str, Any]

    @model_validator(mode="after")
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
        task_variable_fields = set(self.session_variables.keys())

        # Check for overlaps
        info_checklist_overlap = checklist_fields.intersection(info_fields)
        if info_checklist_overlap:
            raise ValueError(
                f"Fields {info_checklist_overlap} appear in both checklist and info"
            )

        task_checklist_overlap = checklist_fields.intersection(task_variable_fields)
        if task_checklist_overlap:
            raise ValueError(
                f"Fields {task_checklist_overlap} appear in both checklist and session_variables"
            )

        info_task_overlap = info_fields.intersection(task_variable_fields)
        if info_task_overlap:
            raise ValueError(
                f"Fields {info_task_overlap} appear in both info and session_variables"
            )

        # Validate stage connections
        stage_names = set(self.stages.keys())
        for stage_name, stage in self.stages.items():
            if stage.next_stage is not None:
                if stage.next_stage != "end" and stage.next_stage not in stage_names:
                    raise ValueError(
                        f"Stage '{stage_name}' has invalid next_stage '{stage.next_stage}'"
                    )

            if stage.transition_logic is not None:
                # Check that all target nodes exist
                for condition in stage.transition_logic.conditions:
                    if (
                        condition.target_node != "end"
                        and condition.target_node not in stage_names
                    ):
                        raise ValueError(
                            f"Stage '{stage_name}' has condition with invalid target_node '{condition.target_node}'"
                        )

                # Check default target node
                default = stage.transition_logic.default_target_node
                if default != "end" and default not in stage_names:
                    raise ValueError(
                        f"Stage '{stage_name}' has invalid default_target_node '{default}'"
                    )

        return self

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
