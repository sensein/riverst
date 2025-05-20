from flask import Flask, render_template, request, jsonify, send_file
import json
import os
import traceback
from datetime import datetime

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate_json', methods=['POST'])
def generate_json():
    try:
        # Debug incoming data
        print("Received data:", json.dumps(request.json, indent=2))
        
        data = request.json
        
        # Check if we're saving to an existing file
        original_filename = data.get("filename", "")
        
        # Extract file name without extension
        if original_filename and original_filename.endswith('.json'):
            base_name = original_filename[:-5]
        else:
            # Generate new filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name = f"flow_{timestamp}"
        
        # Create the session variables content
        session_variables = data.get("session_variables", {})
        
        # Format the flow data, excluding session_variables
        flow_data = {
            "name": data.get("name", ""),
            "description": data.get("description", ""),
            
            "state_config": {
                "stages": {},
                "info": data.get("info", {}),
                "task_variables": data.get("task_variables", {})
                # Session variables will be referenced, not embedded
            },
            
            "flow_config": {
                "initial_node": data.get("nodes", [])[0]["node_name"] if data.get("nodes") else "",
                "nodes": {}
            }
        }
        
        # Process nodes for flow_config and stages
        nodes = data.get("nodes", [])
        for i, node in enumerate(nodes):
            node_name = node.get("node_name", "")
            print(f"Processing node {i+1}: {node_name}")
            
            # Create node entry
            node_data = {
                "task_messages": [
                    {
                        "role": "system",
                        "content": node.get("task_message", "")
                    }
                ],
                "functions": []
            }
            
            # Add the node schema function reference
            node_data["functions"].append({
                "type": "function",
                "function": {
                    "name": f"check_{node_name}_progress",
                    "description": node.get("schema_description", f"Check progress for {node_name} stage"),
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    },
                    "transition_callback": "general_transition_callback"
                }
            })
            
            # Add functions for session variables
            node_functions = node.get("functions", [])
            print(f"Node {node_name} has {len(node_functions)} functions")
            
            for func in node_functions:
                print(f"Processing function: {func}")
                func_name = func.get("name", "")
                variable = func.get("variable", "")
                description = func.get("description", f"Get the {variable} for the session")
                handler = func.get("handler", "get_session_variable_handler")
                
                if func_name and variable:
                    func_data = {
                        "type": "function",
                        "function": {
                            "name": func_name,
                            "description": description,
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "variable_name": {
                                        "type": "string",
                                        "description": "The name of the session variable to retrieve",
                                        "enum": [variable]
                                    },
                                    "current_index": {
                                        "type": "integer",
                                        "description": "The current index of the reading context"
                                    }
                                },
                                },
                                "required": ["variable_name"]
                            },
                            "handler": handler
                        }
                    }
                    node_data["functions"].append(func_data)
                else:
                    print(f"Warning: Skipping function with missing name or variable: {func}")
                
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
                
            flow_data["flow_config"]["nodes"][node_name] = node_data
            
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
            
            # Add next_stage if not the last node
            if i < len(nodes) - 1:
                stage_data["next_stage"] = nodes[i + 1]["node_name"]
            else:
                stage_data["next_stage"] = "end"
                
            flow_data["state_config"]["stages"][node_name] = stage_data
            
            # Add properties to the schema for this node
            schema = node_data["functions"][0]["function"]["parameters"]
            
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
            
        
        # Add end node if needed
        if nodes:
            flow_data["flow_config"]["nodes"]["end"] = {
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
        
        # Add the reference to session variables file
        flow_data["state_config"]["session_variables_file"] = f"session_variables/{base_name}.json"
        
        # Create necessary directories
        os.makedirs(os.path.join("static", "output", "flows"), exist_ok=True)
        os.makedirs(os.path.join("static", "output", "session_variables"), exist_ok=True)
        
        # Save the flow JSON file
        flow_filename = f"{base_name}.json"
        flow_path = os.path.join("static", "output", "flows", flow_filename)
        
        with open(flow_path, 'w') as f:
            json.dump(flow_data, f, indent=2)
        
        # Save the session variables to a separate file
        session_var_path = os.path.join("static", "output", "session_variables", flow_filename)
        with open(session_var_path, 'w') as f:
            json.dump(session_variables, f, indent=2)
        
        print(f"JSON files generated successfully: \n - Flow: {flow_path}\n - Session Variables: {session_var_path}")
        return jsonify({
            "success": True, 
            "filename": f"flows/{flow_filename}",
            "session_variables_file": f"session_variables/{flow_filename}"
        })
    
    except Exception as e:
        error_detail = traceback.format_exc()
        print("Error generating JSON:", error_detail)
        return jsonify({
            "success": False, 
            "error": str(e),
            "detail": error_detail
        })

@app.route('/download/<path:filename>', methods=['GET'])
def download(filename):
    # Handle the new file structure with subdirectories
    return send_file(os.path.join("static", "output", filename), as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)