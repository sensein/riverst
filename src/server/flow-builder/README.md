# Flow Builder Application

A web-based tool for creating and editing conversational flow configurations for AI interactions. This application allows you to define structured conversations with checkpoints, validation, and dynamic content retrieval.

## Overview

The Flow Builder helps you create JSON configuration files for AI-driven conversations. It allows you to:

- Define a sequence of conversation nodes with specific tasks
- Create checklists of items that must be completed before advancing
- Configure session variables that can be accessed during the conversation
- Add function handlers to retrieve context-specific information
- Generate properly formatted JSON configuration files

## Directory Structure

```
flow-builder/
│
├── app.py                 # Main Flask application
│
├── templates/
│   └── index.html         # Main HTML template
│
├── static/
│   ├── css/
│   │   └── style.css      # CSS styles
│   │
│   ├── js/
│   │   ├── script.js      # Frontend JavaScript
│   │   └── file-loader.js # File loading functionality
│   │
│   └── output/            # Directory for generated JSON files
│
└── README.md              # Application documentation
```

## Installation Instructions

1. **Create the directory structure:**

   ```bash
   mkdir -p flow-builder/templates flow-builder/static/css flow-builder/static/js flow-builder/static/output
   ```

2. **Place the files in their respective directories:**
   - Put `app.py` in the root directory
   - Put `index.html` in the templates directory
   - Put `style.css` in the static/css directory
   - Put `script.js` and `file-loader.js` in the static/js directory

3. **Install required packages:**

   ```bash
   pip install flask
   ```

4. **Run the application:**

   ```bash
   cd flow-builder
   python app.py
   ```

   The application will start on http://127.0.0.1:5002/

## Usage Guide

### Basic Information
- Enter the flow name and description in the first section
- Define the system role message for the entire conversation

### Session Variables
- **Task Variables:** Add variables that will be used throughout the conversation
  - Set name, data type, and value for each variable
- **Session Variables:** These are specifically formatted variables that can be retrieved by handler functions
- **Session Info:** Add state fields that will be updated during the conversation

### Nodes Configuration
- Add nodes in the sequence they'll be processed
- Drag and drop to reorder nodes (the sequence determines the "next node")
- Each node contains multiple configuration tabs:

#### 1. Checklist Tab
- Define items that must be completed before advancing
- Each item has a name and description

#### 2. Info Fields Tab
- Select session info fields that will be updated in this node

#### 3. Functions Tab
- Add functions to retrieve session variables
- Choose from available session variables
- The function name is automatically generated as `get_[variable_name]`
- Customize the function description if needed

#### 4. Messages Tab
- Define messages for completed/incomplete checklists

### File Management
- **Load Config:** Upload an existing JSON configuration file for editing
- **Generate JSON File:** Create or update the JSON file with current settings
- When editing an existing file, changes will be saved back to the same file
- New files get a timestamp-based filename

## Key Features

1. **Node Sequencing:**
   - Visual ordering of nodes with drag-and-drop functionality
   - Initial node highlighted in blue, final node in green

2. **Session Variable Support:**
   - Configure task variables for internal logic
   - Define session variables that can be accessed via handler functions

3. **Function Configuration:**
   - Add `get_session_variable_handler` functions to nodes
   - Retrieve specific session variables during the conversation
   - Automatically generate properly formatted function JSON

4. **Checklist Management:**
   - Define items that must be completed before advancing
   - Custom messages for complete/incomplete states

5. **File Management:**
   - Load existing configuration files
   - Edit and save back to the same file
   - Track current file being edited

## Function Structure

Functions exist in two formats. Handlers and Transitions. Transition functions are generated
automatically, they use the transition_callback field. 

Handler functions allow the AI to access state information such as session variables, they use the
handler field. 

Here is an example of a generated handler function:

```json
{
  "type": "function",
  "function": {
    "name": "get_reading_context",
    "description": "Get the reading context for the vocabulary words",
    "parameters": {
      "type": "object",
      "properties": {
        "variable_name": {
          "type": "string",
          "description": "The name of the session variable to retrieve",
          "enum": [
            "reading_context"
          ]
        }
      },
      "required": [
        "variable_name"
      ]
    },
    "handler": "get_session_variable_handler"
  }
}
```

## Troubleshooting

If you encounter issues:

1. **Check the browser console** (F12) for JavaScript errors
2. **Look at the server terminal** for Python errors
3. **Verify template structure** in index.html has all required components
4. **Ensure directory permissions** allow writing to the output folder
5. **Clear browser cache** or try in incognito mode if files were recently updated

For persistent issues, check the debug log or add debug output to identify the specific problem.