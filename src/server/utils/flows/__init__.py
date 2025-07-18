"""
Tools for managing flow configurations and state. Creates dynamic nodes to use in pipecat flows,
which check whether tasks have been completed before moving to the next stage.

Key functions:
- load_config: Loads primary JSON file and handles all validation, returns a tuple of flow and state
- load_session_variables: Loads task variables from a JSON file (ex: data regarding book for reading session)

Task Configuration File:
This is the primary configuration file that defines the flow, which exists across sessions.
It contains two main sections:

1. Flow Config: Node definitions and transition functions between conversation states
2. State Config: Checklist items and information to be collected during the flow, placed in flow_manager state

Session Configuration File:
The session configuration file contains task variables that are used in the flow for a particular session.
This file is loaded separately.

1. Session Variables: Task variables that are used in the flow for a particular session
    - example: reading context, user information, etc.


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

                # OR with dynamic transitions:
                "transition_logic": {
                    "conditions": [
                        {
                            "parameters": {
                                "variable_path": "info_field_name",
                                "operator": "==",
                                "value": true
                            },
                            "target_node": "node_name"
                        }
                    ],
                    "default_target_node": "default_node_name"
                }
            }
        },
        "info": { ... }
        "session_variables" : { This is defined from the session variables file }
    }
}
"""

from .loaders import load_config, load_session_variables

__all__ = ["load_config", "load_session_variables"]
