from flask import Flask, render_template, request, jsonify, send_file
import json
import os
from datetime import datetime

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate_json', methods=['POST'])
def generate_json():
    try:
        data = request.json
        
        # Check if we're saving to an existing file
        original_filename = data.get("filename", "")

        # Add default avatar configuration for the activity
        # Format the received data into the new JSON structure with avatar_configuration and flows_configuration
        flow_data = {
            "avatar_configuration": {
                "title": "Basic Avatar Interaction Configuration",
                "description": "Schema for configuring a basic avatar interaction activity.",
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "const": "basic-avatar-interaction"
                    },
                    "description": {
                        "type": "string",
                        "const": "Basic avatar interaction activity."
                    },
                    "options": {
                        "type": "object",
                        "properties": {
                            "advanced_flows": {
                                "type": "boolean",
                                "default": true,
                                "description": "Set to true to enable advanced flows for this activity."
                            },
                            "advanced_flows_config_path": {
                                "type": "string",
                                "description": "Path to the advanced flows configuration file.",
                                "examples": ["./src/server/assets/activities/settings/vocab-avatar.json"]
                            },
                            "pipeline_modality": {
                                "type": "string",
                                "enum": ["classic", "e2e"],
                                "default": "classic",
                                "description": "The modality of the pipeline."
                            },
                            "camera_settings": {
                                "type": "string",
                                "enum": ["half_body", "headshot", "full_body"],
                                "default": "half_body",
                                "description": "Camera framing for the avatar."
                            },
                            "avatar_system_prompt": {
                                "type": "string",
                                "maxLength": 500,
                                "default": "You are an interactive robot. Keep your responses brief.",
                                "description": "Instructions for the avatar's behavior."
                            },
                            "avatar_personality_description": {
                                "type": "string",
                                "maxLength": 500,
                                "default": "You are the Riverst avatar, a friendly, helpful robot.",
                                "description": "Avatar's personality description."
                            },
                            "task_description": {
                                "type": "string",
                                "maxLength": 500,
                                "default": "Demonstrate how you can interact with the user.",
                                "description": "Description of the task or goal."
                            }
                        },
                        "required": [
                            "advanced_flows",
                            "advanced_flows_config_path"
                        ]
                    }
                },
                "required": ["name", "description", "options"]
            },
            "flows_configuration": {
                "name": data.get("name", ""),
                "description": data.get("description", ""),
                
                "state_config": {
                    "stages": {},
                    "info": data.get("info", {}),
                    "task_variables": data.get("task_variables", {})
                },
                
                "node_config": {
                    "initial_node": data.get("nodes", [])[0]["node_name"] if data.get("nodes") else "",
                    "nodes": {}
                },
                
                "schemas": {}
            }
        }
        
        # Process nodes for node_config and stages
        nodes = data.get("nodes", [])
        for i, node in enumerate(nodes):
            node_name = node.get("node_name", "")
            
            # Create node entry
            node_data = {
                "task_messages": [
                    {
                        "role": "system",
                        "content": node.get("task_message", "")
                    }
                ],
                "functions": [f"{node_name}_schema"],
            }
                
            # Add role_message to the initial node only
            if i == 0 and data.get("role_message"):
                node_data["role_messages"] = [
                    {
                        "role": "system",
                        "content": data.get("role_message", "")
                    }
                ]
            
            # Create post_actions for the last node
            if i == len(nodes) - 1:
                node_data["post_actions"] = [{"type": "end_conversation"}]
                
            flow_data["flows_configuration"]["node_config"]["nodes"][node_name] = node_data
            
            # Create stage entry with checklist
            checklist = {}
            for checklist_item in node.get("checklist_items", []):
                checklist[checklist_item] = False
                
            # Create stage with checklist and messages
            stage_data = {
                "checklist": checklist,
                "checklist_incomplete_message": node.get("checklist_incomplete_message", f"Please complete the following {node_name} items: {{}}"),
                "checklist_complete_message": node.get("checklist_complete_message", "Great job! Moving on to the next stage.")
            }
            
            # Add next_stage if not the last node (now in state_config stages)
            if i < len(nodes) - 1:
                stage_data["next_stage"] = nodes[i + 1]["node_name"]
            else:
                stage_data["next_stage"] = "end"
                
            flow_data["flows_configuration"]["state_config"]["stages"][node_name] = stage_data
            
            # Create schema for the node
            schema = {
                "name": f"check_{node_name}_progress",
                "description": node.get("schema_description", f"Check progress for {node_name} stage"),
                "properties": {},
                "required": [],
                "transition_callback": "general_transition_callback"
            }
            
            # Add checklist items to properties
            for checklist_item in node.get("checklist_items", []):
                if checklist_item in node.get("checklist_descriptions", {}):
                    schema["properties"][checklist_item] = {
                        "type": "boolean",
                        "description": node["checklist_descriptions"][checklist_item]
                    }
                    schema["required"].append(checklist_item)
                
            # Add info fields to properties
            for info_field in node.get("info_fields", []):
                if info_field in data.get("info_descriptions", {}):
                    field_type = data.get("info_types", {}).get(info_field, "boolean")
                    
                    # Create property based on field type
                    if field_type == 'array' or field_type == 'number_array':
                        # Handle array types
                        schema["properties"][info_field] = {
                            "type": "array",
                            "items": {
                                "type": "string" if field_type == 'array' else "number"
                            },
                            "description": data["info_descriptions"][info_field]
                        }
                    else:
                        schema["properties"][info_field] = {
                            "type": field_type,
                            "description": data["info_descriptions"][info_field]
                        }
                    
                    schema["required"].append(info_field)
            
            # Special case for review_schema: add current_word_number if node name contains 'review'
            if 'review' in node_name.lower():
                if 'current_word_number' not in schema["properties"]:
                    schema["properties"]["current_word_number"] = {
                        "type": "integer",
                        "enum": [1, 2],
                        "description": "Which vocabulary word is currently being reviewed (1 or 2)"
                    }
                
                if 'current_word_number' not in schema["required"]:
                    schema["required"].append("current_word_number")
            
            # Add schema to schemas section
            flow_data["flows_configuration"]["schemas"][f"{node_name}_schema"] = schema
        
        # Add end node if needed
        if nodes:
            flow_data["flows_configuration"]["node_config"]["nodes"]["end"] = {
                "task_messages": [
                    {
                        "role": "system",
                        "content": "The session is now complete. Say goodbye in a friendly and encouraging way."
                    }
                ],
                "post_actions": [
                    {
                        "type": "end_conversation"
                    }
                ]
            }
        
        # Determine filename
        if original_filename and original_filename.endswith('.json'):
            # Use the original filename
            filename = original_filename
        else:
            # Generate new filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"flow_{timestamp}.json"
        
        # Ensure output directory exists
        os.makedirs(os.path.join("static", "output"), exist_ok=True)
        
        # Save the JSON file
        with open(os.path.join("static", "output", filename), 'w') as f:
            json.dump(flow_data, f, indent=2)
        
        return jsonify({"success": True, "filename": filename})
    
    except Exception as e:
        import traceback
        print("Error generating JSON:", traceback.format_exc())
        return jsonify({"success": False, "error": str(e)})

@app.route('/download/<filename>', methods=['GET'])
def download(filename):
    return send_file(os.path.join("static", "output", filename), as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)