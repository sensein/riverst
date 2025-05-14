"""
Tools for managing flow configurations and state. Creates dynamic nodes to use in pipecat flows, which check whether tasks have been completed before moving to the next stage.

Key functions:
- get_flow_nodes: Loads node configurations and automatically initializes schemas
- get_flow_initial_node: Gets the initial node from flow configuration
- get_flow_state: Loads and validates flow state configuration
- initialize_schemas: Explicitly initialize schemas if needed (usually not required)

Configuration Files:
Users should create JSON configuration files in a 'configs' directory to define
the structure and flow of conversations. These config files control:

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

Set the FLOW_CONFIG_PATH environment variable to the path of your config file.
"""
from .nodes.loaders import get_flow_nodes, get_flow_initial_node
from .nodes.schema_init import initialize_schemas
from .state.loaders import get_flow_state, validate_flow_config
from .utils.module_utils import OverwritePolicy

__all__ = [
    'get_flow_nodes',
    'get_flow_initial_node',
    'get_flow_state',
    'initialize_schemas',
    'OverwritePolicy',
    'validate_flow_config'
]