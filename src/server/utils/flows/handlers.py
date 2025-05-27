"""
Handlers for flow state management and transitions.
"""
from typing import Dict, Any, Tuple
from pipecat_flows import FlowArgs, FlowResult, FlowManager, NodeConfig
from loguru import logger
from pprint import pformat


def update_checklist_fields(args: FlowArgs, checklist: Dict[str, bool]) -> None:    
    """
    Mark checklist items as complete based on checklist values in args.
    
    Args:
        args: Flow arguments containing field values
        checklist: Checklist dictionary to update
    """    
    logger.info("Checklist before updating:\n{}", pformat(checklist))
    checklist.update({field: True for field in args if args[field] and field in checklist})
    logger.info("Checklist after updating:\n{}", pformat(checklist))


def update_info_fields(args: FlowArgs, flow_manager: FlowManager) -> None:
    """
    Update the info fields in the flow state with values from args.
    
    Args:
        args: Flow arguments containing field values
        flow_manager: Flow manager instance
    """
    logger.info("Info before updating:\n{}", pformat(flow_manager.state["info"]))
    flow_manager.state["info"].update({field: args[field] for field in args if field in flow_manager.state["info"]})
    logger.info("Info after updating:\n{}", pformat(flow_manager.state["info"]))



def create_next_node(flow_manager: FlowManager) -> Tuple[str , NodeConfig]:
    """
    Create the configuration for the next node based on current stage. 
    
    This is actually rather sneaky because 
    we are technically initializing the flow manager with static transitions, but actually we are using callbacks
    and dynamic transitions, mimicing static transitions mostly. This is only because the static transitions don't 
    quite have all the functionality we need.
    
    Args:
        flow_manager: Flow manager instance
        
    Returns:
        Next node configuration
    """
    stage = flow_manager.current_node
    if not stage:
        raise ValueError("Current stage is not set in flow manager.")
    
    next_stage = flow_manager.state["stages"][stage]["next_stage"]
    if not next_stage or type(next_stage) is not str:
        raise ValueError(f"Next stage '{next_stage}' is not a valid string.")
    node = flow_manager.nodes.get(next_stage)
    if not node:
        raise ValueError(f"Node '{next_stage}' not found in flow manager nodes.")
    return next_stage, node


def create_current_node(flow_manager: FlowManager, message: str) -> NodeConfig:
    """
    Create the configuration for the current node based on the current stage.
    
    Args:
        flow_manager: Flow manager instance
        checklist: Checklist dictionary for the current stage
        
    Returns:
        Current node configuration
    """    
    stage = flow_manager.current_node
    if not stage:
        raise ValueError("Current stage is not set in flow manager.")
    
    node = flow_manager.nodes.get(stage)
    if not node:
        raise ValueError(f"Node '{stage}' not found in flow manager nodes.")
    
    node["task_messages"][0]["content"] += f"\n\n{message}"
    node["pre_actions"] = []
    
    return node



async def general_handler(args: FlowArgs, flow_manager: FlowManager) -> Dict[str, Any]:
    """
    General handler to check progress through a stage, store details in flow state, and handle transitions.
    
    Args:
        args: Flow arguments
        flow_manager: Flow manager instance
        
    Returns:
        Flow result with status and message
    """
    logger.info("GENERAL_DEBUG: general_handler called with args: {}", args)
    update_info_fields(args, flow_manager)
    stage = flow_manager.current_node
    checklist = flow_manager.state["stages"][stage]["checklist"]
    update_checklist_fields(args, checklist)
    complete = all(checklist.values())
    
    if complete:
        message = flow_manager.state["stages"][stage]["checklist_complete_message"]
    else:
        message = flow_manager.state["stages"][stage]["checklist_incomplete_message"].format(
            ", ".join([item for item, done in checklist.items() if not done])
        )
        
    return {
        "status": "success" if complete else "error",
        "checklist": checklist,
        "message": message
    }


async def general_transition_callback(args: Dict, result: FlowResult, flow_manager: FlowManager):
    """
    Handle transitions to the next node.
    
    Args:
        args: Flow arguments
        result: Flow result
        flow_manager: Flow manager instance
    """
    if result.get("status") == "success":
        try:
            next_stage, node = create_next_node(flow_manager)
            await flow_manager.set_node(next_stage, node)
        except Exception as e:
            import traceback
    else:
        message = result.get("message", "Please ensure you have completed all required checklist items.")
        await flow_manager.set_node(flow_manager.current_node, create_current_node(flow_manager, message))
    
    


async def get_session_variable_handler(args: FlowArgs, flow_manager: FlowManager) -> Dict[str, Any]:
    """
    Handler to retrieve task variables from the flow state.
    
    For simple variables: returns the variable directly
    For indexable variables: root[root["indexable_by"]][index][field] (if field specified)
    
    Args:
        args: Flow arguments:
            - variable_name (required): Name of the session variable
            - current_index (optional): Index for indexable variables
            - field (optional): Field name to extract from indexed item
        flow_manager: Flow manager instance
        
    Returns:
        Flow result with the requested variable value
    """
    index_error_message = "Variable '{variable_name}' is indexable by {index_field} (valid indices: {options}). Please ask the user for a proper index in very natural language given the context, then call this function again with 'current_index' set to their response. If there was an error in how they responded, please try to correct the user in a very natural way."
    
    variable_name = args.get('variable_name')
    if not variable_name:
        return {
            "status": "error",
            "message": "No variable name provided"
        }
    
    # Get the variable data
    root_data = flow_manager.state["session_variables"].get(variable_name)
    if root_data is None:
        return {
            "status": "error",
            "message": f"Variable '{variable_name}' not found"
        }
    
    # Check if this is an indexable variable
    index_field = root_data.get("indexable_by", None)
    
    if not index_field:
        # Simple variable - return as is
        return {
            "status": "success",
            "data": root_data
        }
    
    # Indexable variable - handle index logic
    indexable_items = root_data.get(index_field, [])
    item_count = len(indexable_items)
    options = f"0-{item_count-1}" if item_count > 0 else "none available"
    
    # Determine the index to use
    index = None
    
    # Case 1: Index is provided in the current function call
    if args.get("current_index") is not None:
        try:
            index = int(args.get("current_index"))
            if index < 0 or index >= item_count:
                raise ValueError("Index out of range")
            
            # Valid index - update the state
            flow_manager.state["session_variables"][variable_name]["current_index"] = index
        except ValueError:
            return {
                "status": "error",
                "message": index_error_message.format(
                    variable_name=variable_name,
                    index_field=index_field,
                    options=options
                )
            }
    
    # Case 2: Try to get index from previously stored state
    else:
        stored_index = root_data.get("current_index", None)
        if stored_index is None:
            return {
                "status": "error",
                "message": index_error_message.format(
                    variable_name=variable_name,
                    index_field=index_field,
                    options=options
                )
            }
        index = int(stored_index)
    
    # Get the indexed item: root[root["indexable_by"]][index]
    indexed_data = indexable_items[index]
    
    
    data = {
        k: v for k, v in root_data.items() if k != "indexable_by" and k != index_field
    }
    if flow_manager.current_node == "warm_up":
        indexed_data.pop("vocab_words", None)
    data[f"current_{index_field}"] = indexed_data
    
    
    return {
        "status": "success",
        "data": data
    }
    
async def get_info_variable_handler(args: FlowArgs, flow_manager: FlowManager) -> Dict[str, Any]:
    """
    Handler to retrieve a task variable from the flow state.
    
    Args:
        args: Flow arguments, should include 'variable_name'
        flow_manager: Flow manager instance
        
    Returns:
        Flow result with the requested variable value
    """
    variable_name = args.get('variable_name')
    
    if not variable_name:
        return {
            "status": "error",
            "message": "No variable name provided"
        }
    
    if variable_name not in flow_manager.state["info"]:
        return {
            "status": "error",
            "error": f"Variable '{variable_name}' not found in session info"
        }        
    
    return {
        "status": "success",
        "data": flow_manager.state["info"].get(variable_name)
    }