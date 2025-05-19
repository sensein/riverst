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
│       └── session_variables/ # Session variables JSON files
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

The application now uses a split file architecture:

### Advantages of the split file architecture:
- We want to clearly separate flow logic, whcih should persist for a given task, and session variables which can be updated for each new session.

### Runtime Access:
At runtime, the AI system uses the separated files. The flow configuration defines the structure and behavior, while the session variables file contains the actual content and data to be accessed during the conversation.


## Usage Guide

### Basic Information
- Enter the flow name and description in the first section
- Define the system role message for the entire conversation

### Session Variables
- **Session Variables:** These are variables that can be retrieved by handler functions
  - Add variables with their data types and structures
  - The actual content will be stored in separate files
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
- **Generate JSON Files:** Creates two separate JSON files:
  - Flow configuration file in `flows/[name].json`
  - Session variables data in `session_variables/[name].json`
- When editing an existing file, changes will be saved back to the same filenames
- New files get a timestamp-based filename

## Key Features

1. **Split File Architecture:**
   - Flow configuration and session variables stored in separate files
   - Better organization and data separation

2. **Node Sequencing:**
   - Visual ordering of nodes with drag-and-drop functionality
   - Initial node highlighted in blue, final node in green

3. **Session Variable Support:**
   - Define session variables that can be accessed via handler functions
   - Store actual content in separate files for better management

4. **Function Configuration:**
   - Add `get_session_variable_handler` functions to nodes
   - Retrieve specific session variables during the conversation
   - Automatically generate properly formatted function JSON

5. **Checklist Management:**
   - Define items that must be completed before advancing
   - Custom messages for complete/incomplete states

## Function Structure

Functions exist in two formats: Handlers and Transitions.

### Transition Functions
- Generated automatically
- Use the `transition_callback` field
- Used to check if requirements are met to progress to the next node
- Automatically created for each node based on checklist items

### Handler Functions
- Allow the AI to access state information such as session variables
- Use the `handler` field
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
    "nodes": { ... }
  }
}
```

### Session Variables Content (session_variables/[name].json)

```json
{
  "vocab_words": [
    "accomplish",
    "anxious",
    "approve",
    "arrange",
    "bizarre",
    "brief",
    "cautious",
    "cherish"
  ],
  "reading_context": {
    "book_title": "The Tale of Peter Rabbit",
    "book_author": "Beatrix Potter",
    "book_text": "Once upon a time there were four little Rabbits..."
  }
}
```

## Troubleshooting

If you encounter issues:

1. **Check the browser console** (F12) for JavaScript errors
2. **Look at the server terminal** for Python errors
3. **Verify template structure** in index.html has all required components
4. **Ensure directory permissions** allow writing to the output folders
5. **Clear browser cache** or try in incognito mode if files were recently updated

For persistent issues, check the debug log or add debug output to identify the specific problem.