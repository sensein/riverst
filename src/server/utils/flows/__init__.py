"""
Tools for managing flow configurations and state. Creates dynamic nodes to use in pipecat flows, which check whether tasks have been completed before moving to the next stage.

Key functions:
- load_config: Loads primary JSON file and handles all validation, returns a tple of flow and state

Configuration File:
There is one primary configuration file that defines the flow. It contains three main sections:

2. Flow Config: Node definitions and transition functions between conversation states
3. State Config: Checklist items and information to be collected during the flow, as well as variables to be passed between nodes

Example structure of a config file:
{
    "name": "example_flow",
    
    "description": "Example flow description",
    
    "flow_config": {
        "initial_node": "start_node",
        "nodes": {
            "node_name": {
                "functions": [
                    {
                        "name": "function_name",
                        "args": { "arg1": "value1", "arg2": "value2" },
                        "transition_callback": "callback_function_name",
                        "handler": "handler_function_name"
                    }
                ]
            }
        }
    },
    "state_config": {
        "stages": {
            "stage_name": {
                "checklist": { "field1": false, "field2": false },
                "checklist_incomplete_message": "Missing information: {0}",
                "checklist_complete_message": "All information collected.",
                "next_stage": "next_stage_name"
            }
        },
        "info": { ... },
        "task_variables": { ... }
    }
}
"""

from .loaders import load_config

__all__ = [
    'load_config',
]