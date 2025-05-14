"""
Handlers for flow state management and transitions.
"""
from typing import Dict, Any
from pipecat_flows import FlowArgs, FlowResult, FlowManager


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


def create_next_node(flow_manager: FlowManager) -> Dict[str, Any]:
    """
    Create the configuration for the next node based on current stage.
    
    Args:
        flow_manager: Flow manager instance
        
    Returns:
        Next node configuration
    """
    stage = flow_manager.current_node
    next_stage = flow_manager.state["stages"][stage]["next_stage"]
    return flow_manager.get_node(next_stage)


async def general_handler(args: FlowArgs, flow_manager: FlowManager) -> FlowResult:
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
        await flow_manager.set_node("next", create_next_node(flow_manager))