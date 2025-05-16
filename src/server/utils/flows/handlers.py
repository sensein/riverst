"""
Handlers for flow state management and transitions.
"""
from typing import Dict, Any, Tuple
from pipecat_flows import FlowArgs, FlowResult, FlowManager, NodeConfig


def update_checklist_fields(args: FlowArgs, checklist: Dict[str, bool]) -> None:    
    """
    Mark checklist items as complete based on checklist values in args.
    
    Args:
        args: Flow arguments containing field values
        checklist: Checklist dictionary to update
    """    
    checklist.update({field: True for field in args if args[field] and field in checklist})


def update_info_fields(args: FlowArgs, flow_manager: FlowManager) -> None:
    """
    Update the info fields in the flow state with values from args.
    
    Args:
        args: Flow arguments containing field values
        flow_manager: Flow manager instance
    """
    flow_manager.state["info"].update({field: args[field] for field in args if field in flow_manager.state["info"]})


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
    
    next_stage = flow_manager.state[stage]["next_stage"]
    if not next_stage or type(next_stage) is not str:
        raise ValueError(f"Next stage '{next_stage}' is not a valid string.")
    node = flow_manager.nodes.get(next_stage)
    if not node:
        raise ValueError(f"Node '{next_stage}' not found in flow manager nodes.")
    return next_stage, node


async def general_handler(args: FlowArgs, flow_manager: FlowManager) -> Dict[str, Any]:
    """
    General handler to check progress through a stage, store details in flow state, and handle transitions.
    
    Args:
        args: Flow arguments
        flow_manager: Flow manager instance
        
    Returns:
        Flow result with status and message
    """
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
        next_stage, node = create_next_node(flow_manager)
        await flow_manager.set_node(next_stage, node)
        
    