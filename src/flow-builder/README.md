# Flow Builder Application - Updated Directory Structure

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
   - Put `script.js` in the static/js directory

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

## Usage Guide for the Updated Flow Builder

1. **Basic Information:**
   - Enter the flow name and description
   
2. **Role Message:**
   - Define the system role message for the entire conversation
   - This will be applied to the initial node

3. **Session Variables:**
   - **Task Variables:** Add variables that will be used throughout the conversation
     - Set name, data type, and value for each variable
   - **Session Info:** Add state fields that will be updated during the conversation
     - Set name, data type, and description for each field
     - These will be initialized to empty/false values

4. **Nodes Configuration:**
   - Add nodes in the sequence they'll be processed
   - Drag and drop to reorder nodes (the sequence determines the "next node")
   - For each node, configure:
     - **Node Name:** Unique identifier for the node
     - **Schema Description:** Description of what the schema checks
     - **Task Message:** System message for the current task
     - **Checklist:** Items that must be completed before advancing
       - Each item needs a name and description
     - **Info Fields:** Session info fields that will be updated in this node
       - Select from the dropdown of available fields
     - **Messages:** Complete/incomplete messages for the checklist

5. **File Management:**
   - **Load Config:** Upload an existing JSON configuration file for editing
   - **Generate JSON File:** Create or update the JSON file with current settings
   - When editing an existing file, changes will be saved back to the same file
   - New files get a timestamp-based filename

## Key Features of the Updated Design

1. **Improved Session Info Management:**
   - Structured approach to defining task variables and session info
   - Info fields are automatically added to node schemas

2. **Node Sequencing:**
   - Visual ordering of nodes with drag-and-drop functionality
   - Initial node highlighted in blue, final node in green

3. **Automatic Schema Generation:**
   - Schemas automatically created for each node
   - Properties derived from checklist items and info fields

4. **Enhanced UI:**
   - Tabbed interface for node configuration
   - Dynamic dropdown for info field selection
   - Improved form validation and error handling

5. **File Management:**
   - Load existing JSON configuration files
   - Edit and save back to the same file
   - Track current file being edited