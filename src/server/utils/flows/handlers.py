"""
Handlers for flow state management and transitions.
"""

from typing import Dict, Any, Tuple, Union
from pipecat_flows import FlowArgs, FlowManager, NodeConfig
from pipecat.frames.frames import LLMMessagesAppendFrame
from loguru import logger
from pprint import pformat
import operator
import json


def update_checklist_fields(args: FlowArgs, checklist: Dict[str, bool]) -> None:
    """
    Mark checklist items as complete based on checklist values in args.

    Args:
        args: Flow arguments containing field values
        checklist: Checklist dictionary to update
    """
    logger.info("Checklist before updating:\n{}", pformat(checklist))
    checklist.update(
        {field: True for field in args if args[field] and field in checklist}
    )
    logger.info("Checklist after updating:\n{}", pformat(checklist))


def update_user_fields(args: FlowArgs, flow_manager: FlowManager) -> None:
    """
    Update the user session fields in the flow state with values from args.

    Args:
        args: Flow arguments containing field values
        flow_manager: Flow manager instance
    """
    logger.info(
        "User session fields before updating:\n{}", pformat(flow_manager.state["user"])
    )
    flow_manager.state["user"].update(
        {field: args[field] for field in args if field in flow_manager.state["user"]}
    )
    logger.info(
        "User session fields after updating:\n{}", pformat(flow_manager.state["user"])
    )


def create_next_node(flow_manager: FlowManager) -> Tuple[str, NodeConfig]:
    """
    Determine the next node ID based on current stage and transition logic.

    This function evaluates transition conditions (found in flows config) and routes to the appropriate target node.

    Steps:
    1. Get the current stage from flow manager
    2. Check if stage uses next_stage (legacy) or transition_logic (new dynamic transitions)
    3a. If using next_stage, use that directly
    3b. If using transition_logic, evaluate conditions:
       - If a condition is met, route to the target node specified in that condition
       - If no conditions are met or there are no conditions, route to the default target node

    Args:
        flow_manager: Flow manager instance

    Returns:
        Tuple containing the next node ID and its configuration.
    """
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

    stage = flow_manager.current_node
    if not stage:
        raise ValueError("Current stage is not set in flow manager.")

    transition_logic = flow_manager.state["stages"][stage]["transition_logic"]
    conditions = transition_logic.get("conditions", [])
    default_target = transition_logic.get("default_target_node")

    # If no default target is specified, raise an error
    if not default_target:
        raise ValueError(f"No default_target_node specified for stage '{stage}'.")

    # Evaluate each condition in order
    for condition in conditions:
        user_variable = condition["parameters"]["variable_path"]
        matching_value = condition["parameters"]["value"]
        operator_str = condition["parameters"]["operator"]

        if user_variable not in flow_manager.state["user"]:
            raise ValueError(
                f"User variable '{user_variable}' not found in flow manager state."
            )

        true_value = flow_manager.state["user"][user_variable]

        if operator_str not in OPERATORS:
            raise ValueError(f"Unsupported operator: {operator_str}")

        # Check if condition matches
        if OPERATORS[operator_str](true_value, matching_value):
            # Condition is true, route to target node
            target_node = condition["target_node"]
            node = flow_manager.nodes.get(target_node)
            if not node:
                raise ValueError(
                    f"Node '{target_node}' not found in flow manager nodes."
                )
            logger.info(
                f"Condition matched: {user_variable} {operator_str} {matching_value}, routing to {target_node}"
            )
            return target_node, node

    # If no conditions matched, use the default target
    logger.info(f"No conditions matched, using default target: {default_target}")
    node = flow_manager.nodes.get(default_target)
    if not node:
        raise ValueError(
            f"Default target node '{default_target}' not found in flow manager nodes."
        )
    return default_target, node


def create_current_node(flow_manager: FlowManager, message: str) -> NodeConfig:
    """
    Create the configuration for the current node based on the current stage.

    Args:
        flow_manager: Flow manager instance
        checklist: Checklist dictionary for the current stage

    Returns:
        Current node configuration
    """
    current_node = flow_manager.current_node
    if not current_node:
        raise ValueError("Current stage is not set in flow manager.")

    node = flow_manager.nodes.get(current_node)
    if not node:
        raise ValueError(f"Node '{current_node}' not found in flow manager nodes.")

    node["task_messages"][0]["content"] += f"\n\n{message}"
    node["pre_actions"] = []

    return node


async def general_handler(
    args: FlowArgs, flow_manager: FlowManager
) -> Tuple[Dict[str, Any], NodeConfig]:
    """
    General handler to check progress through a stage, store details in flow state, and handle transitions.

    note: Updated to match pipecat-flows 0.0.18 consolidated functions

    Steps:
    1. Update info fields in flow state with args
    2. Update checklist fields in the current stage's checklist
    3. Check if all checklist items are complete
    4. If complete, create next node and return success message
    5. If incomplete, create current node with error message and return it

    Args:
        args: Flow arguments
        flow_manager: Flow manager instance

    Returns:
        Tuple containing:
            - Result dictionary with status and message
            - Next node configuration if complete, or current node configuration if incomplete
    """
    update_user_fields(args, flow_manager)
    stage = flow_manager.current_node
    checklist = flow_manager.state["stages"][stage]["checklist"]
    update_checklist_fields(args, checklist)
    complete = all(checklist.values())

    if complete:
        message = "Complete"
        _, next_node = create_next_node(flow_manager)
    else:
        message = flow_manager.state["stages"][stage][
            "checklist_incomplete_message"
        ].format(", ".join([item for item, done in checklist.items() if not done]))
        message = (
            "CRITICAL: You're rejoining mid-flow. CHECK YOUR INSTRUCTIONS CAREFULLY - complete only "
            "required tasks, skip any I haven't asked you to repeat: " + message
        )
        next_node = create_current_node(flow_manager, message)

    result = {"status": "success" if complete else "error", "message": message}

    # Debug: Check if result contains any function objects
    def check_for_functions(obj, path=""):
        if callable(obj):
            logger.error(f"FOUND FUNCTION OBJECT in result at {path}: {obj}")
            return True
        elif isinstance(obj, dict):
            found_func = False
            for key, value in obj.items():
                if check_for_functions(value, f"{path}.{key}"):
                    found_func = True
            return found_func
        elif isinstance(obj, (list, tuple)):
            found_func = False
            for i, item in enumerate(obj):
                if check_for_functions(item, f"{path}[{i}]"):
                    found_func = True
            return found_func
        return False

    if check_for_functions(result):
        logger.error("CRITICAL: Result contains function objects!")
    else:
        logger.info("DEBUG: Result is clean (no function objects)")

    return result, next_node


def handle_indexable_variable(
    variable_name: str,
    flow_manager: FlowManager,
    current_index: int = None,
    source: str = "activity",
) -> Dict[str, Any]:
    """
    Helper function to handle indexable variable logic.

    Args:
        variable_name: Name of the variable
        flow_manager: Flow manager instance
        current_index: Index provided in function call
        source: Source field in flow_manager.state to get variable from

    Returns:
        Dictionary with status and either data or error message
    """
    logger.info("Current %s state:\n%s", source, pformat(flow_manager.state[source]))
    # Get the variable data
    root_data = flow_manager.state[source].get(variable_name)
    if root_data is None:
        return {"status": "error", "message": f"Variable '{variable_name}' not found"}

    index_field = isinstance(root_data, dict) and root_data.get("indexable_by", None)

    if not index_field:
        # Simple variable - return as is
        return {"status": "success", "data": root_data}

    # Indexable variable - handle index logic
    indexable_items = root_data.get(index_field, [])
    item_count = len(indexable_items)
    options = f"1-{item_count}" if item_count > 0 else "none available"

    index_error_message = (
        "Available information - {variable_name}: {data}. "
        "Variable '{variable_name}' is indexable by {index_field}. "
        "At an appropriate moment, ask the user for a proper index in very natural language given the context, "
        "then call get_reading_context function with 'current_index' set to their response. "
        "Continue as you otherwise would afterwards, this should be subtle."
    )

    # Determine the index to use
    index = None

    # Case 1: Index is provided in the current function call
    if current_index is not None:
        try:
            index = int(current_index)
            if index < 0 or index >= item_count:
                raise ValueError("Index out of range")

            # Valid index - update the state
            flow_manager.state[source]["index"] = index

        except ValueError:
            return {
                "status": "error",
                "message": index_error_message.format(
                    variable_name=variable_name,
                    index_field=index_field,
                    options=options,
                ),
            }

    # Case 2: Try to get index from session configuration
    elif (index := flow_manager.state.get("user", {}).get("index")) is not None:
        try:
            index = int(index) - 1  # Adjust for 0-based index
            if index < 0 or index >= item_count:
                raise ValueError("Index out of range")
        except (ValueError, KeyError):
            return {
                "status": "error",
                "message": index_error_message.format(
                    variable_name=variable_name,
                    index_field=index_field,
                    options=options,
                ),
            }

    # Case 3: No index available - need to prompt
    else:
        key_information = root_data.get("key_information", "No data available")
        if isinstance(key_information, dict):
            key_information = json.dumps(key_information, indent=2)
        return {
            "status": "error",
            "message": index_error_message.format(
                variable_name=variable_name,
                index_field=index_field,
                options=options,
                data=key_information,
            ),
        }

    # Get the indexed item
    indexed_data = indexable_items[index]

    data = {
        k: v for k, v in root_data.items() if k != "indexable_by" and k != index_field
    }

    data[f"current_{index_field}"] = indexed_data

    return {"status": "success", "data": data}


async def get_activity_handler(
    args: Union[FlowArgs, dict], flow_manager: FlowManager
) -> Dict[str, Any]:
    """
    Handler to retrieve activity variables from the flow state.

    For simple variables: returns the variable directly
    For indexable variables: root[root["indexable_by"]][index][field] (if field specified)

    Args:
        args: Flow arguments:
            - variable_name (required): Name of the session variable
            - current_index (optional): Index for indexable variables
        flow_manager: Flow manager instance

    Returns:
        Flow result with the requested variable value
    """
    variable_name = args.get("variable_name")
    if not variable_name:
        return {"status": "error", "message": "No variable name provided"}

    current_index = args.get("current_index")

    return handle_indexable_variable(
        variable_name=variable_name,
        flow_manager=flow_manager,
        current_index=current_index,
        source="activity",
    )


async def get_user_handler(
    args: Union[FlowArgs, dict], flow_manager: FlowManager
) -> Dict[str, Any]:
    """
    Handler to retrieve a user-session variable from the flow state.

    Args:
        args: Flow arguments, should include 'variable_name'
        flow_manager: Flow manager instance

    Returns:
        Flow result with the requested variable value
    """
    variable_name = args.get("variable_name")

    if not variable_name:
        return {"status": "error", "message": "No variable name provided"}

    if variable_name not in flow_manager.state["user"]:
        return {
            "status": "error",
            "error": f"Variable '{variable_name}' not found in session user",
        }

    return {"status": "success", "data": flow_manager.state["user"].get(variable_name)}


async def get_variable_action_handler(action: dict, flow_manager: FlowManager) -> None:
    """
    Post-action handler that adds a variable value to the LLM context.

    This handler retrieves the value of the specified variable and adds it
    directly to the LLM context as a system message for use in subsequent
    interactions. It supports multiple LLM providers including OpenAI,
    Anthropic, Google/Gemini, and AWS Bedrock.

    Checks if variable is indexable and retrieves the indexed item if the index is set.
    It will not prompt the user for an index!

    Args:
        action: Action configuration with variable_name field
        flow_manager: Flow manager instance
    """
    variable_name = action.get("variable_name")
    if not variable_name:
        logger.error("Missing variable_name in add_to_context action")
        return

    source = action.get("source", "activity")

    if source not in flow_manager.state:
        logger.error(f"Source '{source}' not found in flow manager state")
        return

    if variable_name not in flow_manager.state[source]:
        logger.error(
            f"Variable '{variable_name}' not found in {source} within flow manager state"
        )
        return

    # Use helper function to handle indexable variable logic
    result = handle_indexable_variable(
        variable_name=variable_name,
        flow_manager=flow_manager,
        current_index=None,  # Pre-actions don't provide current_index
        source=source,
    )

    if result["status"] == "error":
        content = result["message"]
        logger.error(f"Error retrieving variable '{variable_name}': {content}")
    else:
        # Successfully retrieved the variable value
        value = result["data"]

        # Format the content based on the variable type
        if isinstance(value, dict):
            content = f"Available information - {variable_name}: {json.dumps(value, indent=2)}"
        else:
            content = f"Available information - {variable_name}: {value}"

    await flow_manager.task.queue_frame(
        LLMMessagesAppendFrame(messages=[{"role": "system", "content": content}])
    )

    logger.debug(f"Added system message for variable '{variable_name}': {content}")
