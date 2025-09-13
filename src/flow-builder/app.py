from flask import Flask, render_template, request, jsonify, send_file
import json
import os
import traceback
from datetime import datetime

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/generate_json", methods=["POST"])
def generate_json():
    try:
        # Debug incoming data
        print("Received data:", json.dumps(request.json, indent=2))

        data = request.json

        # Check if we're saving to an existing file
        original_filename = data.get("filename", "")

        # Extract file name without extension
        if original_filename and original_filename.endswith(".json"):
            # If it's a path with directory components, extract just the filename
            if "/" in original_filename:
                original_filename = original_filename.split("/")[-1]
            base_name = original_filename[:-5]
        else:
            # Generate new filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name = f"flow_{timestamp}"

        # Create the user and activity variables content
        user_variables = data.get("user_variables", {})
        activity_variables = data.get("activity_variables", {})

        # If activity resource data is provided, use it instead of activity_variables
        activity_resource_data = data.get("activity_resource_data")
        if activity_resource_data:
            print("Using provided activity resource data instead of form variables")
            activity_variables = activity_resource_data

        # Format the flow data using new user/activity structure
        flow_data = {
            "name": data.get("name", ""),
            "description": data.get("description", ""),
            "state_config": {
                "stages": {},
                "user": user_variables,  # New user state structure
                "activity": activity_variables,  # New activity state structure
            },
            "flow_config": {
                "initial_node": (
                    data.get("nodes", [])[0]["node_name"] if data.get("nodes") else ""
                ),
                "nodes": {},
            },
        }

        # Process nodes for flow_config and stages
        nodes = data.get("nodes", [])
        for i, node in enumerate(nodes):
            node_name = node.get("node_name", "")
            print(f"Processing node {i+1}: {node_name}")

            # Create node entry
            node_data = {
                "task_messages": [
                    {"role": "system", "content": node.get("task_message", "")}
                ],
                "functions": [],
            }

            # Add the node schema function reference
            node_data["functions"].append(
                {
                    "type": "function",
                    "function": {
                        "name": f"check_{node_name}_progress",
                        "description": (
                            "From the non-summarizing elements of the conversation, "
                            "return whether the task has been accomplished, and for info fields, "
                            "return an accurate and precise answer."
                        ),
                        "parameters": {
                            "type": "object",
                            "properties": {},
                            "required": [],
                        },
                        "handler": "general_handler",
                        "transition_callback": "general_transition_callback",
                    },
                }
            )

            # Add functions for session variables
            node_functions = node.get("functions", [])
            print(f"Node {node_name} has {len(node_functions)} functions")

            for func in node_functions:
                print(f"Processing function: {func}")
                func_name = func.get("name", "")
                variable = func.get("variable", "")
                source = func.get("source", "activity")  # Default to activity
                description = func.get(
                    "description", f"Get the {variable} from {source}"
                )

                # Map old handler names to new ones
                old_handler = func.get("handler", "get_activity_handler")
                handler_mapping = {
                    "get_session_variable_handler": "get_activity_handler",
                    "get_info_variable_handler": "get_user_handler",
                }
                handler = handler_mapping.get(old_handler, old_handler)

                if func_name and variable:
                    # Create parameters object based on source
                    if handler == "get_user_handler":
                        parameters = {
                            "type": "object",
                            "properties": {
                                "variable_name": {
                                    "type": "string",
                                    "description": "The name of the user variable to retrieve",
                                    "enum": [variable],
                                }
                            },
                            "required": ["variable_name"],
                        }
                    else:  # get_activity_handler
                        parameters = {
                            "type": "object",
                            "properties": {
                                "variable_name": {
                                    "type": "string",
                                    "description": "The name of the activity variable to retrieve",
                                    "enum": [variable],
                                }
                            },
                            "required": ["variable_name"],
                        }

                        # Add current_index parameter for activity handlers (for indexable variables)
                        if handler == "get_activity_handler":
                            parameters["properties"]["current_index"] = {
                                "type": "integer",
                                "description": "The current index for indexable content",
                            }

                    func_data = {
                        "type": "function",
                        "function": {
                            "name": func_name,
                            "description": description,
                            "parameters": parameters,
                            "handler": handler,  # handler at same level as parameters
                        },
                    }
                    node_data["functions"].append(func_data)
                else:
                    print(
                        f"Warning: Skipping function with missing name or variable: {func}"
                    )

            # Add role_message to the initial node only
            if i == 0 and data.get("role_message"):
                node_data["role_messages"] = [
                    {"role": "system", "content": data.get("role_message", "")}
                ]

            # Process actions (both pre and post)
            pre_actions = []
            post_actions = []

            # Process pre-actions that are TTS actions
            if "pre_actions" in node:
                for pre_action in node["pre_actions"]:
                    # Only TTS actions go in pre-actions
                    if pre_action.get("type") == "tts_say":
                        pre_actions.append(pre_action)
                    # Function actions using variables will go to post-actions
                    elif pre_action.get("type") == "function":
                        # Create a function post-action in the simplified format
                        function_data = pre_action.get("function", {})

                        # Get handler type from either location
                        handler_type = pre_action.get("handler") or function_data.get(
                            "handler"
                        )

                        # If it's a variable getter, use get_variable_action_handler instead
                        if handler_type in [
                            "get_activity_handler",
                            "get_user_handler",
                            "get_session_variable_handler",  # Legacy support
                            "get_info_variable_handler",  # Legacy support
                        ]:
                            # Extract variable name from parameters
                            variable_name = None
                            if function_data and "parameters" in function_data:
                                var_enum = (
                                    function_data.get("parameters", {})
                                    .get("properties", {})
                                    .get("variable_name", {})
                                    .get("enum", [])
                                )
                                if var_enum and len(var_enum) > 0:
                                    variable_name = var_enum[0]

                            if variable_name:
                                # Create new post_action in the simplified format
                                # Determine the source based on the handler type
                                if handler_type in [
                                    "get_user_handler",
                                    "get_info_variable_handler",
                                ]:
                                    source = "user"
                                else:  # get_activity_handler, get_session_variable_handler
                                    source = "activity"

                                new_post_action = {
                                    "type": "get_variable",
                                    "handler": "get_variable_action_handler",
                                    "variable_name": variable_name,
                                    "source": source,
                                }
                                post_actions.append(new_post_action)

            # Add existing post-actions if specified
            if "post_actions" in node:
                for post_action in node["post_actions"]:
                    post_actions.append(post_action)

            # Add the actions to the node configuration
            if pre_actions:
                node_data["pre_actions"] = pre_actions

            if post_actions:
                node_data["post_actions"] = post_actions

            flow_data["flow_config"]["nodes"][node_name] = node_data

            # Create stage entry with checklist
            checklist = {}
            for checklist_item in node.get("checklist_items", []):
                checklist[checklist_item] = False

            # Create stage with checklist and standardized incomplete message
            stage_data = {
                "checklist": checklist,
                "checklist_incomplete_message": (
                    "Please complete the following items from the instruction, and only these items. "
                    "Everything else is completed: {}"
                ),
            }

            # Always use transition_logic, even if no conditions are provided
            stage_data["transition_logic"] = {
                "conditions": node.get("transition_conditions", []),
                "default_target_node": node.get("default_target_node", "end"),
            }

            flow_data["state_config"]["stages"][node_name] = stage_data

            # Add properties to the schema for this node
            schema = node_data["functions"][0]["function"]["parameters"]

            # Add checklist items to properties
            for checklist_item in node.get("checklist_items", []):
                if checklist_item in node.get("checklist_descriptions", {}):
                    schema["properties"][checklist_item] = {
                        "type": "boolean",
                        "description": node["checklist_descriptions"][checklist_item],
                    }
                    schema["required"].append(checklist_item)

            # Add user state fields to properties (these were previously called info_fields)
            for user_field in node.get("user_fields", []):
                if user_field in data.get("user_field_descriptions", {}):
                    field_type = data.get("user_field_types", {}).get(
                        user_field, "boolean"
                    )

                    # Create property based on field type
                    if field_type == "array" or field_type == "number_array":
                        # Handle array types
                        schema["properties"][user_field] = {
                            "type": "array",
                            "items": {
                                "type": "string" if field_type == "array" else "number"
                            },
                            "description": data["user_field_descriptions"][user_field],
                        }
                    else:
                        schema["properties"][user_field] = {
                            "type": field_type,
                            "description": data["user_field_descriptions"][user_field],
                        }

                    schema["required"].append(user_field)

            # Legacy support - still handle info_fields but map them to user state
            for info_field in node.get("info_fields", []):
                if info_field in data.get("info_descriptions", {}):
                    field_type = data.get("info_types", {}).get(info_field, "boolean")

                    # Create property based on field type
                    if field_type == "array" or field_type == "number_array":
                        # Handle array types
                        schema["properties"][info_field] = {
                            "type": "array",
                            "items": {
                                "type": "string" if field_type == "array" else "number"
                            },
                            "description": data["info_descriptions"][info_field],
                        }
                    else:
                        schema["properties"][info_field] = {
                            "type": field_type,
                            "description": data["info_descriptions"][info_field],
                        }

                    schema["required"].append(info_field)

            # Remove special case for current_word_number in review nodes

        # Add end node if needed
        if nodes:
            flow_data["flow_config"]["nodes"]["end"] = {
                "task_messages": [
                    {
                        "role": "system",
                        "content": (
                            "The session is now complete. Say goodbye in a friendly and "
                            "encouraging way. Please call the end_conversation function now."
                        ),
                    }
                ],
                "functions": [],  # Empty functions array for end node
            }

        # Create necessary directories
        os.makedirs(os.path.join("static", "output", "flows"), exist_ok=True)
        os.makedirs(
            os.path.join("static", "output", "session_variables"), exist_ok=True
        )

        # Save the flow JSON file
        flow_filename = f"{base_name}.json"
        flow_path = os.path.join("static", "output", "flows", flow_filename)

        with open(flow_path, "w") as f:
            json.dump(flow_data, f, indent=2)

        # Always return just the main flow file
        print(f"JSON file generated successfully: {flow_path}")
        return jsonify({"success": True, "filename": f"flows/{flow_filename}"})

    except Exception as e:
        error_detail = traceback.format_exc()
        print("Error generating JSON:", error_detail)
        return jsonify({"success": False, "error": str(e), "detail": error_detail})


@app.route("/download/<path:filename>", methods=["GET"])
def download(filename):
    # Handle the new file structure with subdirectories
    return send_file(os.path.join("static", "output", filename), as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True, port=5001)
