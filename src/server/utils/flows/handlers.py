"""
Handlers for flow state management and transitions.
"""

from typing import Dict, Any, Tuple, Union, Optional
from pipecat_flows import FlowArgs, FlowManager, NodeConfig
from pipecat.frames.frames import LLMMessagesAppendFrame
from loguru import logger
from pprint import pformat
import operator
import json


class IndexableVariableHandler:
    """Handles retrieval and indexing of variables from flow state."""

    def __init__(self, flow_manager: FlowManager):
        self.flow_manager = flow_manager

    def get_variable(
        self,
        variable_name: str,
        source: str = "activity",
        current_index: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Retrieve a variable, handling indexable logic if needed.

        Returns:
            Dict with 'status' and either 'data' or 'message'
        """
        logger.info(
            "Current %s state:\n%s",
            source,
            pformat(self.flow_manager.state.get(source, {})),
        )

        # Validate source and variable exist
        if source not in self.flow_manager.state:
            return self._error(f"Source '{source}' not found")

        root_data = self.flow_manager.state[source].get(variable_name)
        if root_data is None:
            return self._error(f"Variable '{variable_name}' not found")

        # Handle non-indexable variables
        if not self._is_indexable(root_data):
            return self._success(root_data)

        # Handle indexable variables
        return self._handle_indexable(variable_name, root_data, current_index)

    def _is_indexable(self, data: Any) -> bool:
        """Check if data is indexable."""
        return isinstance(data, dict) and "indexable_by" in data

    def _handle_indexable(
        self,
        variable_name: str,
        root_data: dict,
        current_index: Optional[int],
    ) -> Dict[str, Any]:
        """Process indexable variable logic."""
        index_field = root_data["indexable_by"]
        items = root_data.get(index_field, [])

        # Try to resolve index from multiple sources
        index = self._resolve_index(current_index, len(items))

        if index is None:
            return self._create_index_prompt(variable_name, root_data, index_field)

        if not self._validate_index(index, len(items)):
            return self._create_index_prompt(variable_name, root_data, index_field)

        # Store resolved index in user state where _resolve_index looks for it
        self.flow_manager.state["user"]["index"] = index

        # Build response data
        return self._build_indexed_response(root_data, index_field, index)

    def _resolve_index(
        self, current_index: Optional[int], item_count: int
    ) -> Optional[int]:
        """Resolve index from available sources."""
        # Priority 1: Explicit current_index from prompting user (1-based, needs adjustment)
        if current_index is not None:
            try:
                return int(current_index) - 1
            except (ValueError, TypeError):
                return None

        # Priority 2: User session index from settings (1-based, needs adjustment)
        user_index = self.flow_manager.state.get("user", {}).get("index")
        if user_index is not None:
            try:
                return int(user_index) - 1
            except (ValueError, TypeError):
                return None

        return None

    def _validate_index(self, index: int, item_count: int) -> bool:
        """Validate index is within bounds."""
        return 0 <= index < item_count

    def _create_index_prompt(
        self,
        variable_name: str,
        root_data: dict,
        index_field: str,
    ) -> Dict[str, Any]:
        """Create prompt message for missing/invalid index."""
        key_info = root_data.get("key_information", "No data available")
        if isinstance(key_info, dict):
            key_info = json.dumps(key_info, indent=2)

        message = (
            f"Available information - {variable_name}: {key_info}. "
            f"Variable '{variable_name}' is indexable by {index_field}. "
            f"At an appropriate moment, ask the user for a proper index in very natural language given the context, "
            f"then call get_reading_context function with 'current_index' set to their response. "
            f"Continue as you otherwise would afterwards, this should be subtle."
        )

        return self._error(message)

    def _build_indexed_response(
        self, root_data: dict, index_field: str, index: int
    ) -> Dict[str, Any]:
        """Build response for successfully indexed variable."""
        # Copy all fields except indexing metadata
        data = {
            k: v for k, v in root_data.items() if k not in ["indexable_by", index_field]
        }

        # Add current indexed item
        data[f"current_{index_field}"] = root_data[index_field][index]

        # Update chapter number if key_information exists
        if "key_information" in data:
            if isinstance(data["key_information"], dict):
                data["key_information"]["Chapter Number"] = index + 1

        return self._success(data)

    def _success(self, data: Any) -> Dict[str, Any]:
        """Create success response."""
        return {"status": "success", "data": data}

    def _error(self, message: str) -> Dict[str, Any]:
        """Create error response."""
        return {"status": "error", "message": message}


class VariableFormatter:
    """Format variables for LLM context."""

    @staticmethod
    def format(variable_name: str, value: Any) -> str:
        """Format variable value for clean presentation."""
        if not isinstance(value, dict):
            return f"Available information ({variable_name}): {value}"

        lines = []
        for key, val in value.items():
            formatted_key = key.replace("_", " ").title()
            lines.append(VariableFormatter._format_value(formatted_key, val))

        return "\n".join(lines)

    @staticmethod
    def _format_value(key: str, value: Any) -> str:
        """Format a single key-value pair."""
        if isinstance(value, dict):
            sub_items = [
                f"  • {k.replace('_', ' ').title()}: {v}" for k, v in value.items()
            ]
            return f"**{key}:**\n" + "\n".join(sub_items)

        if isinstance(value, list):
            return f"**{key}:** {', '.join(str(v) for v in value)}"

        return f"**{key}:** {value}"


# ====================
# Flow State Management
# ====================


class FlowStateManager:
    """Manages flow state updates and transitions."""

    OPERATORS = {
        "==": operator.eq,
        "!=": operator.ne,
        ">": operator.gt,
        ">=": operator.ge,
        "<": operator.lt,
        "<=": operator.le,
        "in": operator.contains,
        "not_in": lambda a, b: not operator.contains(a, b),
    }

    def __init__(self, flow_manager: FlowManager):
        self.flow_manager = flow_manager

    def update_checklist(self, args: FlowArgs, checklist: Dict[str, bool]) -> None:
        """Mark checklist items as complete based on args."""
        logger.info("Checklist before updating:\n{}", pformat(checklist))
        checklist.update(
            {field: True for field in args if args[field] and field in checklist}
        )
        logger.info("Checklist after updating:\n{}", pformat(checklist))

    def update_user_fields(self, args: FlowArgs) -> None:
        """Update user session fields with values from args."""
        user_state = self.flow_manager.state.get("user", {})
        logger.info("User session before updating:\n{}", pformat(user_state))

        user_state.update({field: args[field] for field in args if field in user_state})

        logger.info("User session after updating:\n{}", pformat(user_state))

    def determine_next_node(self) -> Tuple[str, NodeConfig]:
        """Determine next node based on transition logic."""
        stage = self.flow_manager.current_node
        if not stage:
            raise ValueError("Current stage is not set")

        transition_logic = self.flow_manager.state["stages"][stage]["transition_logic"]
        conditions = transition_logic.get("conditions", [])
        default_target = transition_logic.get("default_target_node")

        if not default_target:
            raise ValueError(f"No default_target_node for stage '{stage}'")

        # Evaluate conditions
        for condition in conditions:
            if self._evaluate_condition(condition):
                target = condition["target_node"]
                node = self._get_node(target)
                logger.info(f"Condition matched, routing to {target}")
                return target, node

        # Use default
        logger.info(f"No conditions matched, using default: {default_target}")
        return default_target, self._get_node(default_target)

    def _evaluate_condition(self, condition: dict) -> bool:
        """Evaluate a single transition condition."""
        params = condition["parameters"]
        variable_path = params["variable_path"]
        expected_value = params["value"]
        operator_str = params["operator"]

        user_state = self.flow_manager.state.get("user", {})
        if variable_path not in user_state:
            raise ValueError(f"Variable '{variable_path}' not found in user state")

        actual_value = user_state[variable_path]

        if operator_str not in self.OPERATORS:
            raise ValueError(f"Unsupported operator: {operator_str}")

        return self.OPERATORS[operator_str](actual_value, expected_value)

    def _get_node(self, node_id: str) -> NodeConfig:
        """Get node configuration by ID."""
        node = self.flow_manager._nodes.get(node_id)
        if not node:
            raise ValueError(f"Node '{node_id}' not found")
        return node

    def create_current_node(self, message: str) -> NodeConfig:
        """Create configuration for current node with additional message."""
        current_node = self.flow_manager.current_node
        if not current_node:
            raise ValueError("Current stage is not set")

        node = self._get_node(current_node)
        node["task_messages"][0]["content"] += f"\n\n{message}"
        node["pre_actions"] = []

        return node


# ====================
# Handler Functions
# ====================


async def general_handler(
    args: FlowArgs, flow_manager: FlowManager
) -> Tuple[Dict[str, Any], NodeConfig]:
    """
    General handler for flow progression and state management.

    Handles checklist updates, field updates, and node transitions.
    """
    state_manager = FlowStateManager(flow_manager)

    # Update user fields
    state_manager.update_user_fields(args)

    # Update checklist
    stage = flow_manager.current_node
    checklist = flow_manager.state["stages"][stage]["checklist"]
    state_manager.update_checklist(args, checklist)

    # Check completion
    complete = all(checklist.values())

    if complete:
        message = "Complete"
        _, next_node = state_manager.determine_next_node()
    else:
        incomplete_items = [item for item, done in checklist.items() if not done]
        base_message = flow_manager.state["stages"][stage][
            "checklist_incomplete_message"
        ]
        message = base_message.format(", ".join(incomplete_items))
        message = (
            "CRITICAL: You're rejoining mid-flow. CHECK YOUR INSTRUCTIONS CAREFULLY - "
            "complete only required tasks, skip any I haven't asked you to repeat: "
            + message
        )
        next_node = state_manager.create_current_node(message)

    result = {"status": "success" if complete else "error", "message": message}

    return result, next_node


async def get_activity_handler(
    args: Union[FlowArgs, dict], flow_manager: FlowManager
) -> Dict[str, Any]:
    """Handler to retrieve activity variables."""
    variable_name = args.get("variable_name")
    if not variable_name:
        return {"status": "error", "message": "No variable name provided"}

    handler = IndexableVariableHandler(flow_manager)
    return handler.get_variable(
        variable_name=variable_name,
        source="activity",
        current_index=args.get("current_index"),
    )


async def get_user_handler(
    args: Union[FlowArgs, dict], flow_manager: FlowManager
) -> Dict[str, Any]:
    """Handler to retrieve user-session variables."""
    variable_name = args.get("variable_name")

    if not variable_name:
        return {"status": "error", "message": "No variable name provided"}

    user_state = flow_manager.state.get("user", {})
    if variable_name not in user_state:
        return {
            "status": "error",
            "message": f"Variable '{variable_name}' not found in session user",
        }

    return {"status": "success", "data": user_state[variable_name]}


async def get_variable_action_handler(action: dict, flow_manager: FlowManager) -> None:
    """Post-action handler that adds a variable value to the LLM context."""
    variable_name = action.get("variable_name")
    if not variable_name:
        logger.error("Missing variable_name in add_to_context action")
        return

    source = action.get("source", "activity")
    handler = IndexableVariableHandler(flow_manager)
    result = handler.get_variable(variable_name, source)

    if result["status"] == "error":
        logger.error(
            f"Error retrieving variable '{variable_name}': {result['message']}"
        )
        content = result["message"]
    else:
        content = VariableFormatter.format(variable_name, result["data"])

    # Queue the message to LLM
    await flow_manager.task.queue_frame(
        LLMMessagesAppendFrame(messages=[{"role": "system", "content": content}])
    )

    logger.debug(f"Added system message for variable '{variable_name}': {content}")
