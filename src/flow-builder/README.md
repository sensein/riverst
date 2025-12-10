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
│   └── output/            # Output directory for generated files
│       ├── flows/         # JSON flow configuration files
│       └── session_variables/ # Session variables JSON files (optional)
│
└── README.md              # Application documentation
```

## Installation Instructions

1. **Create the directory structure:**

   ```bash
   mkdir -p flow-builder/templates flow-builder/static/css flow-builder/static/js \
     flow-builder/static/output/flows flow-builder/static/output/session_variables
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

   The application will start on http://127.0.0.1:5000/

## Split File Architecture

The application uses a split file architecture where session variables can be embedded in the main flow configuration file.

### Advantages of the architecture:
- Clear separation of flow logic, which should persist for a given task, from session variables
- Session variables are embedded in the main configuration by default
- Option to save session variables separately if needed

### Runtime Access:
At runtime, the AI system uses the configuration file with embedded session variables. The flow configuration defines the structure and behavior, while the session variables contain the actual content and data to be accessed during the conversation.

## Usage Guide

### Basic Information
- Enter the flow name and description in the first section
- Define the system role message for the entire conversation

### Session Variables
- **Session Variables:** These are variables that can be retrieved by handler functions during the conversation
  - Add variables with their data types and values
  - The content is embedded in the main configuration file
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
- **Open File:** Open an existing JSON configuration file for editing
  - Uses File System Access API in supporting browsers for direct file access
- **Generate JSON:** Creates and saves the flow configuration file
  - In browsers with File System Access API, saves directly back to the opened file
  - In other browsers, provides download links for the generated files
- **Keyboard Shortcut:** Use Ctrl+S (or Cmd+S on Mac) to quickly save changes
- When editing an existing file, changes will be saved back to the same file
- New files get a timestamp-based filename by default

## Key Features

1. **Direct File Saving:**
   - Instant saving back to the original file in supported browsers
   - No need to download and replace files manually
   - Keyboard shortcut (Ctrl+S/Cmd+S) for quick saving

2. **Integrated Session Variables:**
   - Session variables embedded directly in the flow configuration
   - Better integration and simpler file management

3. **Node Sequencing:**
   - Visual ordering of nodes with drag-and-drop functionality
   - Initial node highlighted in blue, final node in green

4. **Session Variable Support:**
   - Define session variables that can be accessed via handler functions
   - Store content directly in the configuration for easier management

5. **Function Configuration:**
   - Add `get_session_variable_handler` functions to nodes
   - Retrieve specific session variables during the conversation
   - Handler field at the same level as other function properties

6. **Checklist Management:**
   - Define items that must be completed before advancing
   - Custom messages for complete/incomplete states

## Function Structure

Functions exist in two formats: Handlers and Transitions.

### Transition Functions
- Generated automatically
- Use the `handler` field with value `general_transition_callback`
- Used to check if requirements are met to progress to the next node
- Automatically created for each node based on checklist items

### Handler Functions
- Allow the AI to access state information such as session variables
- Use the `handler` field with appropriate handler names
- Added through the Functions tab in node configuration
- Enable retrieval of session variables during conversation

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

## Output File Structure

### Flow Configuration (flows/[name].json)

```json
{
  "name": "vocab-tutoring",
  "description": "A flow for AI vocabulary tutoring",
  "state_config": {
    "stages": { ... },
    "info": { ... },
    "session_variables": {
      "vocab_words": [],
      "reading_context": {
        "book_title": "",
        "book_author": "",
        "book_text": ""
      }
    }
  },
  "flow_config": {
    "initial_node": "warm_up",
    "nodes": {
      "warm_up": {
        "task_messages": [ ... ],
        "functions": [
          {
            "type": "function",
            "function": {
              "name": "check_warm_up_progress",
              "description": "Check progress for warm_up stage",
              "parameters": { ... },
              "handler": "general_transition_callback"
            }
          }
        ]
      },
      "end": {
        "task_messages": [ ... ],
        "functions": []
      }
    }
  }
}
```

Note: Session variables are embedded in the main configuration file by default. The handler field is now at the same level as name, description, and parameters within the function object.

## Troubleshooting

If you encounter issues:

1. **Check the browser console** (F12) for JavaScript errors
2. **Look at the server terminal** for Python errors
3. **Verify template structure** in index.html has all required components
4. **Ensure directory permissions** allow writing to the output folders
5. **Clear browser cache** or try in incognito mode if files were recently updated

For persistent issues, check the debug log or add debug output to identify the specific problem.
