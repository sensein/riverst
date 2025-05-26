// ============== Debugging Functionality ==============
// Wrap console.log to also output to debug panel
const originalConsoleLog = console.log;
const originalConsoleWarn = console.warn;
const originalConsoleError = console.error;

// Setup console logging without debug panel
function setupConsoleLogging() {
    // Keep original console methods
    console.log = originalConsoleLog;
    console.warn = originalConsoleWarn;
    console.error = originalConsoleError;
}

function addToDebugOutput(type, args) {
    const debugOutput = document.getElementById('debugOutput');
    if (!debugOutput) return;

    const timestamp = new Date().toISOString().split('T')[1].replace('Z', '');

    let message = '';
    for (let i = 0; i < args.length; i++) {
        const arg = args[i];
        if (typeof arg === 'object') {
            try {
                message += JSON.stringify(arg, null, 2) + ' ';
            } catch (e) {
                message += arg + ' ';
            }
        } else {
            message += arg + ' ';
        }
    }

    const logEntry = document.createElement('div');
    logEntry.className = `log-entry log-${type}`;
    logEntry.innerHTML = `<span class="log-time">[${timestamp}]</span> <span class="log-type">${type.toUpperCase()}</span>: ${message}`;

    // Apply colors based on log type
    if (type === 'warn') {
        logEntry.style.color = '#856404';
        logEntry.style.backgroundColor = '#fff3cd';
        logEntry.style.padding = '2px 5px';
        logEntry.style.marginBottom = '2px';
    } else if (type === 'error') {
        logEntry.style.color = '#721c24';
        logEntry.style.backgroundColor = '#f8d7da';
        logEntry.style.padding = '2px 5px';
        logEntry.style.marginBottom = '2px';
    }

    debugOutput.appendChild(logEntry);
    debugOutput.scrollTop = debugOutput.scrollHeight;
}

document.addEventListener('DOMContentLoaded', function () {
    // Set up console logging
    setupConsoleLogging();
    
    // Add keyboard shortcut for saving (Ctrl+S or Cmd+S)
    document.addEventListener('keydown', function(e) {
        if ((e.ctrlKey || e.metaKey) && e.key === 's') {
            e.preventDefault(); // Prevent the browser's save dialog
            const generateBtn = document.getElementById('generateBtn');
            if (generateBtn) {
                generateBtn.click();
            }
        }
    });

    // Helper function to create a DOM element from a template
    function createFromTemplate(templateId) {
        const template = document.getElementById(templateId);
        return document.importNode(template.content, true);
    }

    // Initialize UI components
    initTaskVariables();
    initSessionInfo();
    initNodes();
    initButtons();

    // Initialize sortable for node reordering
    const nodesContainer = document.getElementById('nodesContainer');
    new Sortable(nodesContainer, {
        animation: 150,
        handle: '.handle',
        ghostClass: 'sortable-ghost',
        onEnd: function () {
            updateNodeOrder();
        }
    });

    // Add initial node if none exists
    if (nodesContainer.children.length === 0) {
        addNode();
    }

    // Function to update node order display
    function updateNodeOrder() {
        const nodes = document.querySelectorAll('.node-card');
        nodes.forEach((node, index) => {
            const nodeHeader = node.querySelector('.node-header');
            nodeHeader.classList.remove('bg-primary', 'bg-success', 'bg-secondary');

            if (index === 0) {
                nodeHeader.classList.add('bg-primary', 'text-white');
            } else if (index === nodes.length - 1) {
                nodeHeader.classList.add('bg-success', 'text-white');
            }
        });
    }

    // ============== Task Variables Management ==============
    function initTaskVariables() {
        const addTaskVarBtn = document.getElementById('addTaskVarBtn');
        addTaskVarBtn.addEventListener('click', addTaskVariable);
    }

    function addTaskVariable() {
        const container = document.getElementById('taskVariablesContainer');
        const varElement = createFromTemplate('taskVarTemplate');

        // Set up event handlers
        const typeSelect = varElement.querySelector('.task-var-type');
        const valueContainer = varElement.querySelector('.task-var-value-container');

        // Validate name input - prevent spaces
        const nameInput = varElement.querySelector('.task-var-name');
        nameInput.addEventListener('input', function () {
            this.value = this.value.replace(/\s+/g, '_');
            // Mark as a session variable by default for backward compatibility
            this.dataset.varType = 'session';
            updateAllSessionVariableDropdowns(); // Update function dropdowns when name changes
        });

        // Mark as a session variable by default for backward compatibility
        nameInput.dataset.varType = 'session';

        // Set up remove button
        varElement.querySelector('.remove-task-var-btn').addEventListener('click', function () {
            this.closest('.task-var-card').remove();
            updateAllSessionVariableDropdowns(); // Update function dropdowns when variable removed
        });

        // Add change handler for type select
        typeSelect.addEventListener('change', function () {
            updateValueInput(this.value, valueContainer);
        });

        // Initial value input
        updateValueInput(typeSelect.value, valueContainer);

        container.appendChild(varElement);
        return varElement;
    }

    function updateValueInput(type, container) {
        container.innerHTML = '';

        switch (type) {
            case 'string':
                container.innerHTML = `<input type="text" class="form-control form-control-sm task-var-value" placeholder="Value">`;
                break;
            case 'number':
                container.innerHTML = `<input type="number" class="form-control form-control-sm task-var-value" placeholder="Value">`;
                break;
            case 'boolean':
                container.innerHTML = `
                    <div class="form-check">
                        <input class="form-check-input task-var-value" type="checkbox" value="true">
                        <label class="form-check-label">True</label>
                    </div>`;
                break;
            case 'array':
                container.innerHTML = `<input type="text" class="form-control form-control-sm task-var-value" placeholder="Comma-separated values">`;
                break;
            case 'number_array':
                container.innerHTML = `<input type="text" class="form-control form-control-sm task-var-value" placeholder="Comma-separated numbers">`;
                break;
            case 'object':
                container.innerHTML = `<textarea class="form-control form-control-sm task-var-value" rows="2" placeholder='{"key": "value"}'></textarea>`;
                break;
        }
    }

    // ============== Session Info Management ==============
    function initSessionInfo() {
        const addSessionInfoBtn = document.getElementById('addSessionInfoBtn');
        addSessionInfoBtn.addEventListener('click', addSessionInfo);
    }

    function addSessionInfo() {
        const container = document.getElementById('sessionInfoContainer');
        const infoElement = createFromTemplate('sessionInfoTemplate');

        // Validate name input - prevent spaces
        const nameInput = infoElement.querySelector('.session-info-name');
        nameInput.addEventListener('input', function () {
            this.value = this.value.replace(/\s+/g, '_');
            updateInfoFieldDropdowns();
        });

        // Set up remove button
        infoElement.querySelector('.remove-session-info-btn').addEventListener('click', function () {
            if (confirm('Removing this info field will also remove it from any nodes that use it. Continue?')) {
                const infoName = this.closest('.session-info-card').querySelector('.session-info-name').value;

                // Remove corresponding info fields from nodes
                if (infoName) {
                    document.querySelectorAll('.info-field-item-card').forEach(field => {
                        if (field.querySelector('.info-field-name').textContent === infoName) {
                            field.remove();
                        }
                    });
                }

                this.closest('.session-info-card').remove();
                updateInfoFieldDropdowns();
            }
        });

        // Add change handler for name to update dropdowns
        infoElement.querySelector('.session-info-name').addEventListener('input', function () {
            updateInfoFieldDropdowns();
        });

        container.appendChild(infoElement);
        updateInfoFieldDropdowns();
        return infoElement;
    }

    // Update all "Add Info Field" dropdowns in nodes with current session info fields
    function updateInfoFieldDropdowns() {
        const sessionInfoFields = Array.from(document.querySelectorAll('.session-info-name')).map(
            input => ({
                name: input.value,
                type: input.closest('.session-info-card').querySelector('.session-info-type').value
            })
        ).filter(field => field.name.trim() !== '');

        // Update each node's info field dropdown
        document.querySelectorAll('.add-info-field-container').forEach(container => {
            container.innerHTML = '';

            if (sessionInfoFields.length > 0) {
                // Create a select with available fields
                const selectGroup = document.createElement('div');
                selectGroup.className = 'input-group mb-2';

                const select = document.createElement('select');
                select.className = 'form-select info-field-select';

                // Add option for each field
                const defaultOption = document.createElement('option');
                defaultOption.text = 'Select an info field...';
                defaultOption.value = '';
                select.appendChild(defaultOption);

                sessionInfoFields.forEach(field => {
                    const option = document.createElement('option');
                    option.value = field.name;
                    option.text = `${field.name} (${field.type})`;
                    option.dataset.type = field.type;
                    select.appendChild(option);
                });

                const button = document.createElement('button');
                button.className = 'btn btn-outline-primary add-info-field-btn';
                button.type = 'button';
                button.innerHTML = 'Add';

                // Add event listener to button
                button.addEventListener('click', function () {
                    const select = this.closest('.input-group').querySelector('select');
                    const selectedOption = select.options[select.selectedIndex];

                    if (select.value) {
                        addInfoFieldToNode(
                            this.closest('.node-card'),
                            select.value,
                            selectedOption.dataset.type
                        );
                        select.value = '';
                    }
                });

                selectGroup.appendChild(select);
                selectGroup.appendChild(button);
                container.appendChild(selectGroup);
            } else {
                // No fields available message
                const message = document.createElement('div');
                message.className = 'alert alert-info py-2 small';
                message.textContent = 'Add session info fields first to make them available here.';
                container.appendChild(message);
            }
        });
    }

    function addInfoFieldToNode(nodeCard, fieldName, fieldType) {
        const container = nodeCard.querySelector('.info-fields-container');

        // Check if this field is already added
        const existingFields = Array.from(container.querySelectorAll('.info-field-name')).map(
            span => span.textContent
        );

        if (existingFields.includes(fieldName)) {
            alert('This info field is already added to this node.');
            return;
        }

        const fieldElement = createFromTemplate('infoFieldItemTemplate');

        // Set field name and type
        fieldElement.querySelector('.info-field-name').textContent = fieldName;
        fieldElement.querySelector('.info-field-type').textContent = fieldType;

        // Set up remove button
        fieldElement.querySelector('.remove-info-field-btn').addEventListener('click', function () {
            this.closest('.info-field-item-card').remove();
        });

        // Automatically create a function to get this info field
        const description = `Get the ${fieldName} info variable`;
        addNodeFunction(nodeCard, fieldName, description, true);
        
        container.appendChild(fieldElement);
    }

    // ============== Node Functions Management ==============
    // Updated function for adding functions to a node
    function addNodeFunction(nodeCard, sessionVar = "", description = "", isInfoVariable = false) {
        const container = nodeCard.querySelector('.functions-container');

        // Create element from template
        const functionElement = createFromTemplate('functionItemTemplate');

        // Set description if provided
        if (description) {
            functionElement.querySelector('.function-description').value = description;
        }

        // Get the dropdown
        const varSelect = functionElement.querySelector('.session-variable-select');
        
        // Mark as info variable if needed
        if (isInfoVariable || (sessionVar && Array.from(document.querySelectorAll('.session-info-name')).map(input => input.value).includes(sessionVar))) {
            varSelect.classList.add('info-variable-select');
        }

        // Update variable dropdown
        updateSessionVariableDropdown(varSelect);

        // Set selected variable if provided
        if (sessionVar) {
            varSelect.value = sessionVar;
        }

        // Set up remove button
        functionElement.querySelector('.remove-function-btn').addEventListener('click', function () {
            this.closest('.function-item-card').remove();
        });

        // Add auto-generate description listener
        varSelect.addEventListener('change', function () {
            const descInput = this.closest('.function-item-card').querySelector('.function-description');
            const varName = this.value;
            const isInfo = this.classList.contains('info-variable-select');

            if (!descInput.value && varName) {
                descInput.value = isInfo 
                    ? `Get the ${varName} info variable` 
                    : `Get the ${varName} for the session`;
            }
        });

        // Add element to container
        container.appendChild(functionElement);
        return functionElement;
    }

    // Function to update session variable dropdown
    function updateSessionVariableDropdown(select) {
        // Get all session variables
        const sessionVars = [];
        
        // Get info variables if this select has the info-variable-select class
        const isInfoSelect = select.classList.contains('info-variable-select');
        
        if (isInfoSelect) {
            // Get info variables
            document.querySelectorAll('.session-info-name').forEach(input => {
                const name = input.value.trim();
                if (name) sessionVars.push(name);
            });
        } else {
            // Get from task variables that are marked as session
            document.querySelectorAll('.task-var-name[data-var-type="session"]').forEach(input => {
                const name = input.value.trim();
                if (name) sessionVars.push(name);
            });

            // If no explicitly marked session variables, get all task variables as fallback
            if (sessionVars.length === 0) {
                document.querySelectorAll('.task-var-name').forEach(input => {
                    const name = input.value.trim();
                    if (name) sessionVars.push(name);
                });
            }
        }

        // Save current selection
        const currentValue = select.value;

        // Clear current options
        select.innerHTML = '<option value="">Select a value...</option>';

        // Add options for each session variable
        sessionVars.forEach(name => {
            const option = document.createElement('option');
            option.value = name;
            option.text = name;
            select.appendChild(option);
        });

        // Restore selection if possible
        if (currentValue && sessionVars.includes(currentValue)) {
            select.value = currentValue;
        }
    }

    // Update all session variable dropdowns
    function updateAllSessionVariableDropdowns() {
        document.querySelectorAll('.session-variable-select').forEach(updateSessionVariableDropdown);
    }

    // Helper function to load functions for a node
    function loadNodeFunctions(nodeEl, nodeName, node) {
        const functionsContainer = nodeEl.querySelector('.functions-container');
        if (!functionsContainer) return;

        functionsContainer.innerHTML = ''; // Clear container

        // Get node functions from config
        const nodeFunctions = node.functions || [];

        // Process each function in the node
        nodeFunctions.forEach(funcData => {
            // Skip the check_progress function which is automatically added
            if (funcData.function && funcData.function.transition_callback === "general_transition_callback") return;

            if (funcData.function && (funcData.function.handler === "get_session_variable_handler" ||
                funcData.function.handler === "get_info_variable_handler")) {
                // Extract variable name
                const varEnum = funcData.function.parameters?.properties?.variable_name?.enum;
                if (!varEnum || varEnum.length === 0) return;

                const varName = varEnum[0];
                const funcDescription = funcData.function.description || `Get the ${varName} for the session`;

                // Add function to node
                addNodeFunction(nodeEl, varName, funcDescription);
            }
        });
    }

    // ============== Nodes Management ==============
    function initNodes() {
        const addNodeBtn = document.getElementById('addNodeBtn');
        addNodeBtn.addEventListener('click', function () {
            addNode();
            updateNodeOrder();
        });
    }

    function addNode() {
        const container = document.getElementById('nodesContainer');
        const nodeElement = createFromTemplate('nodeTemplate');
        const nodeCounter = container.children.length + 1;

        // Set default node name
        const nodeName = `node_${nodeCounter}`;
        const nodeNameInput = nodeElement.querySelector('.node-name');
        const nodeNameDisplay = nodeElement.querySelector('.node-name-display');

        nodeNameInput.value = nodeName;
        nodeNameDisplay.textContent = nodeName;
        
        // Set up pre-action toggle
        const preActionToggle = nodeElement.querySelector('.pre-action-toggle');
        const preActionContainer = nodeElement.querySelector('.pre-action-container');
        
        preActionToggle.addEventListener('change', function() {
            preActionContainer.style.display = this.checked ? 'block' : 'none';
        });

        // Set default messages
        const incompleteMessage = nodeElement.querySelector('.node-incomplete-message');
        const completeMessage = nodeElement.querySelector('.node-complete-message');

        incompleteMessage.value = `Please complete the following ${nodeName} items: {}`;
        completeMessage.value = `Great job! Moving on to the next stage.`;

        // Prevent spaces in node name
        nodeNameInput.addEventListener('input', function () {
            // Replace spaces with underscores
            this.value = this.value.replace(/\s+/g, '_');
            nodeNameDisplay.textContent = this.value || 'unnamed';

            // Update the incomplete message when node name changes
            incompleteMessage.value = `Please complete the following ${this.value} items: {}`;
        });

        // Set up remove node button
        nodeElement.querySelector('.remove-node-btn').addEventListener('click', function () {
            if (document.querySelectorAll('.node-card').length <= 1) {
                alert('You must have at least one node.');
                return;
            }

            if (confirm('Are you sure you want to remove this node?')) {
                this.closest('.node-card').remove();
                updateNodeOrder();
            }
        });

        // Set up add checklist item button
        nodeElement.querySelector('.add-checklist-item-btn').addEventListener('click', function () {
            addChecklistItem(this.closest('.node-card'));
        });

        // Add a default checklist item
        addChecklistItem(nodeElement);

        // Make sure tab functionality works correctly
        const tabButtons = nodeElement.querySelectorAll('[data-bs-toggle="tab"]');
        tabButtons.forEach(button => {
            button.addEventListener('click', function (event) {
                event.preventDefault();

                // Hide all tab panes in this node
                const tabContentContainer = this.closest('.node-card').querySelector('.tab-content');
                tabContentContainer.querySelectorAll('.tab-pane').forEach(pane => {
                    pane.classList.remove('show', 'active');
                });

                // Show the selected pane
                const targetSelector = this.getAttribute('data-bs-target');
                const targetPane = this.closest('.node-card').querySelector(targetSelector);
                if (targetPane) {
                    targetPane.classList.add('show', 'active');
                }

                // Update active state on buttons
                this.closest('ul').querySelectorAll('.nav-link').forEach(link => {
                    link.classList.remove('active');
                });
                this.classList.add('active');
            });
        });

        // Set up dropdown function buttons
        const addSessionFunctionBtn = nodeElement.querySelector('.add-session-function');
        if (addSessionFunctionBtn) {
            addSessionFunctionBtn.addEventListener('click', function(e) {
                e.preventDefault();
                addNodeFunction(this.closest('.node-card'));
            });
        }
        
        const addInfoFunctionBtn = nodeElement.querySelector('.add-info-function');
        if (addInfoFunctionBtn) {
            addInfoFunctionBtn.addEventListener('click', function(e) {
                e.preventDefault();
                addNodeFunction(this.closest('.node-card'), "", "", true);
            });
        }

        // Update info field dropdown
        updateInfoFieldDropdowns();

        // Add the node to the container
        container.appendChild(nodeElement);
        return nodeElement;
    }

    function addChecklistItem(nodeElement) {
        const container = nodeElement.querySelector('.checklist-container');
        const itemElement = createFromTemplate('checklistItemTemplate');

        // Prevent spaces in checklist item name
        const nameInput = itemElement.querySelector('.checklist-item-name');
        nameInput.addEventListener('input', function () {
            this.value = this.value.replace(/\s+/g, '_');
        });

        // Set up remove button
        itemElement.querySelector('.remove-checklist-item-btn').addEventListener('click', function () {
            this.closest('.checklist-item-card').remove();
        });

        container.appendChild(itemElement);
    }

    // ============== Form Data Collection ==============
    function collectFormData() {
        // Helper function to clean string values
        function cleanString(str) {
            if (!str) return str;
            // Remove leading/trailing quotes
            str = str.trim();
            if ((str.startsWith('"') && str.endsWith('"')) ||
                (str.startsWith("'") && str.endsWith("'"))) {
                str = str.substring(1, str.length - 1);
            }
            return str;
        }

        // Helper function to clean array values
        function cleanArray(str) {
            if (!str) return [];
            str = str.trim();

            // Remove brackets if present
            if (str.startsWith('[') && str.endsWith(']')) {
                str = str.substring(1, str.length - 1);
            }

            // Split, trim and clean quotes from items
            return str.split(',')
                .map(item => {
                    item = item.trim();
                    if ((item.startsWith('"') && item.endsWith('"')) ||
                        (item.startsWith("'") && item.endsWith("'"))) {
                        item = item.substring(1, item.length - 1);
                    }
                    return item;
                })
                .filter(item => item !== '');
        }

        // Get filename from hidden input if we're editing an existing file
        const currentFilename = document.getElementById('currentFilename').value;

        const name = cleanString(document.getElementById('flowName').value);
        const description = cleanString(document.getElementById('flowDescription').value);
        const roleMessage = cleanString(document.getElementById('roleMessage').value);

        // Collect session variables (no task_variables)
        const sessionVariables = {};

        document.querySelectorAll('.task-var-card').forEach(card => {
            const varName = cleanString(card.querySelector('.task-var-name').value);
            if (!varName) return;

            const varType = card.querySelector('.task-var-type').value;
            const valueInput = card.querySelector('.task-var-value');

            let value;
            switch (varType) {
                case 'string':
                    value = cleanString(valueInput.value);
                    break;
                case 'number':
                    value = parseFloat(valueInput.value);
                    break;
                case 'boolean':
                    value = valueInput.checked;
                    break;
                case 'array':
                    value = cleanArray(valueInput.value);
                    break;
                case 'number_array':
                    value = cleanArray(valueInput.value).map(v => parseFloat(v)).filter(v => !isNaN(v));
                    break;
                case 'object':
                    try {
                        // We still parse as JSON but clean beforehand
                        const cleanedValue = cleanString(valueInput.value);
                        value = cleanedValue ? JSON.parse(cleanedValue) : {};
                    } catch (e) {
                        value = {};
                    }
                    break;
            }

            // Add to session variables
            sessionVariables[varName] = value;
        });

        // Collect session info
        const info = {};
        const infoTypes = {};
        const infoDescriptions = {};

        document.querySelectorAll('.session-info-card').forEach(card => {
            const infoName = cleanString(card.querySelector('.session-info-name').value);
            if (!infoName) return;

            const infoType = card.querySelector('.session-info-type').value;
            const infoDescription = cleanString(card.querySelector('.session-info-description').value);

            // Set default value based on type
            let defaultValue;
            switch (infoType) {
                case 'boolean':
                    defaultValue = false;
                    break;
                case 'string':
                    defaultValue = '';
                    break;
                case 'number':
                    defaultValue = 0;
                    break;
                case 'array':
                case 'number_array':
                    defaultValue = [];
                    break;
            }

            info[infoName] = defaultValue;
            infoTypes[infoName] = infoType;
            infoDescriptions[infoName] = infoDescription || `Info field for ${infoName}`;
        });

        // Collect nodes data
        const nodes = [];

        document.querySelectorAll('.node-card').forEach(nodeCard => {
            const nodeName = cleanString(nodeCard.querySelector('.node-name').value);
            if (!nodeName) return;

            const taskMessage = cleanString(nodeCard.querySelector('.node-task-message').value);
            const schemaDescription = cleanString(nodeCard.querySelector('.schema-description').value);
            const incompleteMessage = cleanString(nodeCard.querySelector('.node-incomplete-message').value);
            const completeMessage = cleanString(nodeCard.querySelector('.node-complete-message').value);

            // Collect checklist items
            const checklistItems = [];
            const checklistDescriptions = {};

            nodeCard.querySelectorAll('.checklist-item-card').forEach(item => {
                const itemName = cleanString(item.querySelector('.checklist-item-name').value);
                if (!itemName) return;

                const itemDescription = cleanString(item.querySelector('.checklist-item-description').value);

                checklistItems.push(itemName);
                checklistDescriptions[itemName] = itemDescription || `Check if ${itemName} is completed`;
            });

            // Collect info fields
            const infoFields = [];

            nodeCard.querySelectorAll('.info-field-item-card').forEach(field => {
                const fieldName = cleanString(field.querySelector('.info-field-name').textContent);
                if (fieldName) {
                    infoFields.push(fieldName);
                }
            });

            // Collect functions
            const functions = [];

            nodeCard.querySelectorAll('.function-item-card').forEach(funcCard => {
                const sessionVar = cleanString(funcCard.querySelector('.session-variable-select').value);
                const description = cleanString(funcCard.querySelector('.function-description').value);

                if (sessionVar) {
                    const funcName = `get_${sessionVar}`;

                    // Check if this is an info field by checking if it exists in the info fields list
                    const infoFields = Array.from(document.querySelectorAll('.session-info-name')).map(input => input.value);
                    const useInfoHandler = infoFields.includes(sessionVar);
                    
                    functions.push({
                        name: funcName,
                        variable: sessionVar,
                        description: description || `Get the ${sessionVar} for the session`,
                        handler: useInfoHandler ? "get_info_variable_handler" : "get_session_variable_handler"
                    });
                }
            });

            // Check if pre-action is enabled
            const preActionToggle = nodeCard.querySelector('.pre-action-toggle');
            const preActionText = nodeCard.querySelector('.pre-action-text');
            
            // Create node object
            const nodeData = {
                node_name: nodeName,
                task_message: taskMessage,
                schema_description: schemaDescription || `Check progress of checklist items, and update relevant info variables`,
                checklist_items: checklistItems,
                checklist_descriptions: checklistDescriptions,
                info_fields: infoFields,
                checklist_incomplete_message: incompleteMessage || `Please complete the following ${nodeName} items: {}`,
                checklist_complete_message: completeMessage || `Great job! Moving on to the next stage.`
            };
            
            // Add pre-action if toggled on
            if (preActionToggle && preActionToggle.checked && preActionText && preActionText.value.trim()) {
                nodeData.pre_action = {
                    text: cleanString(preActionText.value)
                };
            }

            // Add functions if there are any
            if (functions.length > 0) {
                nodeData.functions = functions;
            }

            nodes.push(nodeData);
        });

        // Return the complete data structure - no task_variables
        return {
            filename: currentFilename,
            name,
            description,
            role_message: roleMessage,
            session_variables: sessionVariables,
            info: info,
            info_types: infoTypes,
            info_descriptions: infoDescriptions,
            nodes
        };
    }

    // ============== Form Management ==============
    function initButtons() {
        const generateBtn = document.getElementById('generateBtn');
        const resetBtn = document.getElementById('resetBtn');
        const fileInput = document.getElementById('fileInput');

        // Generate JSON handler
        generateBtn.addEventListener('click', generateJson);

        // Reset form handler
        resetBtn.addEventListener('click', function () {
            if (confirm('Are you sure you want to reset the form? All your data will be lost.')) {
                resetForm();
            }
        });

        // File input change handler
        fileInput.addEventListener('change', function (event) {
            console.log("File selected:", event.target.files[0]?.name);
            const file = event.target.files[0];
            if (file) {
                loadConfigFromFile(file);
            }
        });
        
        // Add open file button that uses the File System Access API
        const openFileBtn = document.createElement('button');
        openFileBtn.type = 'button';
        openFileBtn.id = 'openFileBtn';
        openFileBtn.className = 'btn btn-outline-primary me-2';
        openFileBtn.innerHTML = '<i class="bi bi-folder2-open"></i> Open File';
        fileInput.parentNode.insertBefore(openFileBtn, fileInput.nextSibling);
        
        // Hide the file input since we're using the open file button
        fileInput.style.display = 'none';
        
        // Open file handler with File System Access API
        openFileBtn.addEventListener('click', async function() {
            try {
                // Check if the File System Access API is supported
                if ('showOpenFilePicker' in window) {
                    const options = {
                        types: [
                            {
                                description: 'JSON Files',
                                accept: {
                                    'application/json': ['.json']
                                }
                            }
                        ],
                        excludeAcceptAllOption: false,
                        multiple: false
                    };
                    
                    // Show file picker
                    const [fileHandle] = await window.showOpenFilePicker(options);
                    const file = await fileHandle.getFile();
                    
                    // Add the handle to the file object for later use
                    file.handle = fileHandle;
                    
                    // Load the file
                    await loadConfigFromFile(file);
                } else {
                    // Fallback for browsers that don't support the File System Access API
                    fileInput.click();
                }
            } catch (error) {
                console.error("Error opening file:", error);
                // The user cancelled the file picker, do nothing
            }
        });
    }

    function resetForm() {
        // Clear basic info
        document.getElementById('flowName').value = '';
        document.getElementById('flowDescription').value = '';
        document.getElementById('roleMessage').value = '';
        document.getElementById('currentFilename').value = '';

        // Clear task variables and session info
        document.getElementById('taskVariablesContainer').innerHTML = '';
        document.getElementById('sessionInfoContainer').innerHTML = '';

        // Clear nodes
        document.getElementById('nodesContainer').innerHTML = '';

        // Hide result container
        document.getElementById('resultContainer').style.display = 'none';

        // Add initial node
        addNode();
    }

    // Collect form data without debugging
    function collectFormDataForGeneration() {
        return collectFormData();
    }

    async function generateJson() {
        try {
            // Get form data
            const formData = collectFormDataForGeneration();

            // Basic validation
            if (!formData.name) {
                alert('Flow name is required!');
                return;
            }

            if (formData.nodes.length === 0) {
                alert('At least one node is required!');
                return;
            }

            // Show sending notification
            const resultContainer = document.getElementById('resultContainer');
            resultContainer.style.display = 'block';
            resultContainer.innerHTML = `
            <div class="alert alert-info">
                <h4>Generating JSON...</h4>
                <p>Please wait while we process your configuration.</p>
            </div>
        `;

            // Always try to save directly if we have a file handle
            if (window.currentFileHandle && 'showSaveFilePicker' in window) {
                try {
                    // Check if we have write permission
                    const options = {
                        mode: 'readwrite'
                    };
                    
                    // Request permission if needed
                    if ((await window.currentFileHandle.queryPermission(options)) !== 'granted') {
                        if ((await window.currentFileHandle.requestPermission(options)) !== 'granted') {
                            throw new Error("Permission to write to the file was denied");
                        }
                    }
                    
                    // Send data to server to generate the JSON structure
                    const response = await fetch('/generate_json', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify(formData)
                    });
                    
                    const data = await response.json();
                    
                    if (data.success) {
                        // Fetch the generated file content from the server
                        const flowFileResponse = await fetch(`/download/${data.filename}`);
                        const flowContent = await flowFileResponse.text();
                        
                        try {
                            // Create a writable stream and write to the file
                            const writable = await window.currentFileHandle.createWritable();
                            await writable.write(flowContent);
                            await writable.close();
                            
                            // Show success message
                            resultContainer.innerHTML = `
                            <div class="alert alert-success">
                                <h4>Configuration Saved!</h4>
                                <p>Your conversation flow has been saved successfully to the original file.</p>
                            </div>`;
                            
                            // Hide success message after 3 seconds
                            setTimeout(() => {
                                resultContainer.style.display = 'none';
                            }, 3000);
                        } catch (error) {
                            console.error("Error writing to original file:", error);
                            resultContainer.innerHTML = `
                            <div class="alert alert-danger">
                                <h4>Error Saving File</h4>
                                <p>${error.message || "There was a problem writing to the original file."}</p>
                            </div>`;
                            throw error; // Rethrow to trigger the fallback methods
                        }
                        
                        return;
                    }
                } catch (error) {
                    console.error("Error saving directly to file:", error);
                    alert("Error saving to the original file. Please use the File System Access API to save to a specific location.");
                }
            } else {
                // If we don't have a file handle, prompt to save with File System Access API
                try {
                    if ('showSaveFilePicker' in window) {
                        const options = {
                            types: [
                                {
                                    description: 'JSON Files',
                                    accept: {
                                        'application/json': ['.json']
                                    }
                                }
                            ],
                            suggestedName: formData.name + '.json'
                        };
                        
                        const fileHandle = await window.showSaveFilePicker(options);
                        window.currentFileHandle = fileHandle;
                        
                        // Send data to server to generate the JSON structure
                        const response = await fetch('/generate_json', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify(formData)
                        });
                        
                        const data = await response.json();
                        
                        if (data.success) {
                            // Fetch the generated file content from the server
                            const flowFileResponse = await fetch(`/download/${data.filename}`);
                            const flowContent = await flowFileResponse.text();
                            
                            try {
                            // Create a writable stream and write to the file
                            const writable = await fileHandle.createWritable();
                            await writable.write(flowContent);
                            await writable.close();
                            
                            // Show success message
                            resultContainer.innerHTML = `
                            <div class="alert alert-success">
                                <h4>Configuration Saved!</h4>
                                <p>Your conversation flow has been saved successfully.</p>
                            </div>`;
                            
                            // Hide success message after 3 seconds
                            setTimeout(() => {
                                resultContainer.style.display = 'none';
                            }, 3000);
                        } catch (error) {
                            console.error("Error writing to file:", error);
                            resultContainer.innerHTML = `
                            <div class="alert alert-danger">
                                <h4>Error Saving File</h4>
                                <p>${error.message || "There was a problem writing to the file."}</p>
                            </div>`;
                        }
                            
                            return;
                        }
                    } else {
                        throw new Error("File System Access API not supported by your browser.");
                    }
                } catch (error) {
                    console.error("Error saving file with picker:", error);
                    // Fall back to the server-side method if File System Access API fails
                }
            }
            
            // If both direct save methods failed, offer download option
            const response = await fetch('/generate_json', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(formData)
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Create download link
                const downloadUrl = `/download/${data.filename}`;
                resultContainer.innerHTML = `
                <div class="alert alert-warning">
                    <h4>File System Access Failed</h4>
                    <p>Your browser couldn't save the file directly, but you can download it instead:</p>
                    <a href="${downloadUrl}" class="btn btn-primary" download>Download JSON File</a>
                </div>`;
            } else {
                resultContainer.innerHTML = `
                <div class="alert alert-danger">
                    <h4>Error Saving File</h4>
                    <p>There was a problem generating your file. Please try again or use a different browser.</p>
                </div>`;
            }

            // Scroll to result container
            resultContainer.scrollIntoView({ behavior: 'smooth' });
        } catch (error) {
            console.error("Error generating JSON:", error);
            
            const resultContainer = document.getElementById('resultContainer');
            resultContainer.style.display = 'block';
            resultContainer.innerHTML = `
            <div class="alert alert-danger">
                <h4>Error Generating JSON</h4>
                <p>${error.message || "Unknown error"}</p>
            </div>`;
            
            resultContainer.scrollIntoView({ behavior: 'smooth' });
        }
    }

    // Make these functions globally available
    window.addTaskVariable = addTaskVariable;
    window.addNode = addNode;
    window.addNodeFunction = addNodeFunction;
    window.updateSessionVariableDropdown = updateSessionVariableDropdown;
    window.updateAllSessionVariableDropdowns = updateAllSessionVariableDropdowns;
    window.collectFormData = collectFormData;
    window.loadNodeFunctions = loadNodeFunctions;
});