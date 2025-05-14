"""
Tools for managing flow configurations and state. Creates dynamic nodes to use in pipecat flows, which check whether tasks have been completed before moving to the next stage.

Key functions:
- load_config: Loads primary JSON file and handles all validation, returns the loaded flow configuration 
- get_flow_nodes: Loads node configurations and automatically initializes schemas from flow configuration
- get_flow_initial_node: Gets the initial node from flow configuration
- get_flow_state: Loads flow state configuration from flow configuration
- initialize_schemas: Explicitly initialize schemas if needed (usually not required)

Configuration File:
There is one primary configuration file that defines the flow. It contains three main sections:

1. Schemas: Function schemas that define the available functions in your flow, they are called in the Flow Config
2. Flow Config: Node definitions and transition rules between conversation states
3. State Config: Definition of state variables and validation rules

Example structure of a config file:
{
    "name": "example_flow",
    
    "description": "Example flow description",
    
    "schemas": {
        "schema_name": {
            "name": "function_name",
            "description": "Function description",
            "parameters": { ... }
        }
    },
    "flow_config": {
        "initial_node": "start_node",
        "nodes": {
            "node_name": {
                "functions": ["function1", "function2"],
                "next_node": "next_node_name"
            }
        }
    },
    "state_config": {
        "stages": {
            "stage_name": {
                "checklist": { "field1": false, "field2": false },
                "checklist_incomplete_message": "Missing information: {0}",
                "checklist_complete_message": "All information collected."
            }
        },
        "info": { ... },
        "task_variables": { ... }
    }
}
"""
from .nodes.loaders import get_flow_nodes, get_flow_initial_node
from .nodes.schema_init import initialize_schemas
from .state.loaders import get_flow_state
from .utils.module_utils import OverwritePolicy, load_config

__all__ = [
    'get_flow_nodes',
    'get_flow_initial_node',
    'get_flow_state',
    'initialize_schemas',
    'OverwritePolicy',
    'load_config',
]