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

    // Add a pre-action function
    function addPreActionFunction(nodeCard, sessionVar = "", description = "", isInfoVariable = false) {
        const container = nodeCard.querySelector('.function-pre-actions-container');

        // Create element from template
        const functionElement = createFromTemplate('preActionFunctionTemplate');

        // Set description if provided
        if (description) {
            functionElement.querySelector('.pre-action-function-description').value = description;
        }

        // Get the dropdown
        const varSelect = functionElement.querySelector('.pre-action-variable-select');

        // Mark as info variable if needed
        if (isInfoVariable || (sessionVar && Array.from(document.querySelectorAll('.session-info-name')).map(input => input.value).includes(sessionVar))) {
            varSelect.classList.add('info-variable-select');
        }

        // Update variable dropdown (reuse the same function but for pre-actions)
        updatePreActionVariableDropdown(varSelect);

        // Set selected variable if provided
        if (sessionVar) {
            varSelect.value = sessionVar;
        }

        // Set up remove button
        functionElement.querySelector('.remove-pre-action-function-btn').addEventListener('click', function () {
            this.closest('.pre-action-function-card').remove();
        });

        // Add auto-generate description listener
        varSelect.addEventListener('change', function () {
            const descInput = this.closest('.pre-action-function-card').querySelector('.pre-action-function-description');
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

    // Update pre-action variable dropdown
    function updatePreActionVariableDropdown(select) {
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
        document.querySelectorAll('.condition-variable').forEach(updateConditionVariableDropdown);
    }

    // Function to add a transition condition
    function addTransitionCondition(nodeCard) {
        const container = nodeCard.querySelector('.transition-conditions-container');
        const conditionElement = createFromTemplate('transitionConditionTemplate');

        // Set up the condition variable dropdown
        const variableSelect = conditionElement.querySelector('.condition-variable');
        updateConditionVariableDropdown(variableSelect);

        // Set up operator change handler
        const operatorSelect = conditionElement.querySelector('.condition-operator');
        const valueContainer = conditionElement.querySelector('.condition-value-container');

        operatorSelect.addEventListener('change', function() {
            updateConditionValueInput(variableSelect.value, this.value, valueContainer);
        });

        // Set up variable change handler
        variableSelect.addEventListener('change', function() {
            updateConditionValueInput(this.value, operatorSelect.value, valueContainer);
        });

        // Set up the target node dropdown
        const targetNodeSelect = conditionElement.querySelector('.condition-target-node');
        updateNodeTargetDropdown(targetNodeSelect);

        // Add verification for required fields
        variableSelect.addEventListener('change', function() {
            verifyConditionFields(conditionElement);
        });

        operatorSelect.addEventListener('change', function() {
            verifyConditionFields(conditionElement);
        });

        // Add input event listener for the value field - only if it exists
        const valueField = conditionElement.querySelector('.condition-value');
        if (valueField) {
            valueField.addEventListener('input', function() {
                verifyConditionFields(conditionElement);
            });
        }

        targetNodeSelect.addEventListener('change', function() {
            verifyConditionFields(conditionElement);
        });

        // Set up remove button
        conditionElement.querySelector('.remove-condition-btn').addEventListener('click', function() {
            this.closest('.transition-condition-card').remove();
        });

        container.appendChild(conditionElement);

        // Initial verification
        verifyConditionFields(conditionElement);

        return conditionElement;
    }

    // Update the condition variable dropdown with info fields
    function updateConditionVariableDropdown(select) {
        // Get all info fields
        const infoFields = Array.from(document.querySelectorAll('.session-info-name')).map(input => {
            return {
                name: input.value.trim(),
                type: input.closest('.session-info-card').querySelector('.session-info-type').value
            };
        }).filter(field => field.name !== '');

        // Save current selection
        const currentValue = select.value;

        // Clear current options
        select.innerHTML = '<option value="">Select variable...</option>';

        // Add options for each info field
        infoFields.forEach(field => {
            const option = document.createElement('option');
            option.value = field.name;
            option.text = field.name;
            option.dataset.type = field.type;
            select.appendChild(option);
        });

        // Restore selection if possible
        if (currentValue && infoFields.some(field => field.name === currentValue)) {
            select.value = currentValue;
        }
    }

    // Update the value input based on the selected variable and operator
    function updateConditionValueInput(variableName, operator, container) {
        // Find the variable type from info fields
        let variableType = 'string'; // Default type

        if (variableName) {
            const infoTypeSelect = document.querySelector(`.session-info-name[value="${variableName}"]`)?.closest('.session-info-card')?.querySelector('.session-info-type');
            if (infoTypeSelect) {
                variableType = infoTypeSelect.value;
            }
        }

        // Clear the container
        container.innerHTML = '';

        // Create the appropriate input based on type and operator
        if (operator === 'in' || operator === 'not_in') {
            // For "in" or "not in" operators, we need a string input
            container.innerHTML = `<input type="text" class="form-control form-control-sm condition-value" placeholder="Value">`;
        } else if (variableType === 'boolean') {
            // For boolean type, create a select with true/false options
            container.innerHTML = `
                <select class="form-select form-select-sm condition-value">
                    <option value="true">true</option>
                    <option value="false">false</option>
                </select>
            `;
        } else if (variableType === 'number') {
            // For number type, create a number input
            container.innerHTML = `<input type="number" class="form-control form-control-sm condition-value" placeholder="Value">`;
        } else if (variableType === 'array' || variableType === 'number_array') {
            // For array types and "in"/"not_in" operators
            if (operator === 'in' || operator === 'not_in') {
                container.innerHTML = `<input type="text" class="form-control form-control-sm condition-value" placeholder="Value">`;
            } else {
                container.innerHTML = `<input type="text" class="form-control form-control-sm condition-value" placeholder="[value1, value2, ...]">`;
            }
        } else {
            // Default to string input for any other type
            container.innerHTML = `<input type="text" class="form-control form-control-sm condition-value" placeholder="Value">`;
        }

        // Add event listener for input validation
        const valueInput = container.querySelector('.condition-value');
        if (valueInput) {
            valueInput.addEventListener('input', function() {
                // Remove validation classes when editing
                this.classList.remove('is-invalid', 'is-valid');
            });
        }
    }

    // Update a target node dropdown with all available nodes
    function updateNodeTargetDropdown(select) {
        const nodes = Array.from(document.querySelectorAll('.node-name')).map(input => input.value.trim()).filter(name => name !== '');

        // Add "end" node always
        if (!nodes.includes('end')) {
            nodes.push('end');
        }

        // Save current selection
        const currentValue = select.value;

        // Clear current options
        select.innerHTML = '<option value="">Select target...</option>';

        // Add options for each node
        nodes.forEach(nodeName => {
            const option = document.createElement('option');
            option.value = nodeName;
            option.text = nodeName;
            select.appendChild(option);
        });

        // Restore selection if possible
        if (currentValue && nodes.includes(currentValue)) {
            select.value = currentValue;
        }
    }

    // Update all node target dropdowns
    function updateAllNodeTargetDropdowns() {
        document.querySelectorAll('.condition-target-node, .default-target-node').forEach(updateNodeTargetDropdown);
    }

    // Verify all fields in a condition are properly filled
    function verifyConditionFields(conditionElement) {
        const variableSelect = conditionElement.querySelector('.condition-variable');
        const operatorSelect = conditionElement.querySelector('.condition-operator');
        const valueInput = conditionElement.querySelector('.condition-value');
        const targetNodeSelect = conditionElement.querySelector('.condition-target-node');

        let isValid = true;

        // Check variable field
        if (!variableSelect.value) {
            variableSelect.classList.add('is-invalid');
            isValid = false;
        } else {
            variableSelect.classList.remove('is-invalid');
            variableSelect.classList.add('is-valid');
        }

        // Check operator field
        if (!operatorSelect.value) {
            operatorSelect.classList.add('is-invalid');
            isValid = false;
        } else {
            operatorSelect.classList.remove('is-invalid');
            operatorSelect.classList.add('is-valid');
        }

        // Check value field
        if (!valueInput) {
            // If valueInput is null, we can't validate it
            console.error("Missing value input field in condition");
            isValid = false;
        } else if (valueInput.value === '') {
            valueInput.classList.add('is-invalid');
            isValid = false;
        } else {
            valueInput.classList.remove('is-invalid');
            valueInput.classList.add('is-valid');
        }

        // Check target node field
        if (!targetNodeSelect.value) {
            targetNodeSelect.classList.add('is-invalid');
            isValid = false;
        } else {
            targetNodeSelect.classList.remove('is-invalid');
            targetNodeSelect.classList.add('is-valid');
        }

        return isValid;
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
            if (funcData.function && funcData.function.handler === "general_handler") return;

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

        // Set default task message with prepended text
        const taskMessage = nodeElement.querySelector('.node-task-message');
        taskMessage.value = `TOOLS: \nYou may silently call the check_${nodeName}_progress() function only after all ${nodeName} conversation steps have been completed. Do not mention you are doing this. Look at the other tools you have available, and if you need a certain piece of information that they provide, you may call them (silently, do not mention you are doing so!)\n\n`;

        // Set default incomplete message with standardized format
        const incompleteMessage = nodeElement.querySelector('.node-incomplete-message');
        incompleteMessage.value = "Please complete the following items from the instruction, and only these items. Everything else is completed: {}";

        // Set default schema description
        const schemaDescription = nodeElement.querySelector('.schema-description');
        schemaDescription.value = "From the non-summarizing elements of the conversation, return whether each task has been accomplished, and for info fields, return an accurate and precise answer.";

        // Prevent spaces in node name and validate
        nodeNameInput.addEventListener('input', function () {
            // Replace spaces with underscores
            this.value = this.value.replace(/\s+/g, '_');
            nodeNameDisplay.textContent = this.value || 'unnamed';

            // No longer update the incomplete message when node name changes
            // incompleteMessage.value = `Please complete the following ${this.value} items: {}`;
            // Keep using the standardized message format

            // Update the task message preamble with new node name
            const currentValue = taskMessage.value;
            const nodeName = this.value || 'unnamed';
            taskMessage.value = `TOOLS: \nYou may silently call the check_${nodeName}_progress() function only after all ${nodeName} conversation steps have been completed. Do not mention you are doing this. Look at the other tools you have available, and if you need a certain piece of information that they provide, you may call them (silently, do not mention you are doing so!)\n\n` +
            currentValue.split('\n\n').slice(1).join('\n\n');

            // Validate node name
            validateNodeName(this);

            // Update node names in all target dropdowns
            updateAllNodeTargetDropdowns();
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
                updateAllNodeTargetDropdowns();
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

        // Set up transition conditions
        const addConditionBtn = nodeElement.querySelector('.add-condition-btn');
        if (addConditionBtn) {
            addConditionBtn.addEventListener('click', function() {
                addTransitionCondition(this.closest('.node-card'));
            });
        }

        // Set up pre-action functions
        const addPreActionSessionFunctionBtn = nodeElement.querySelector('.add-pre-action-session-function');
        if (addPreActionSessionFunctionBtn) {
            addPreActionSessionFunctionBtn.addEventListener('click', function(e) {
                e.preventDefault();
                addPreActionFunction(this.closest('.node-card'));
            });
        }

        const addPreActionInfoFunctionBtn = nodeElement.querySelector('.add-pre-action-info-function');
        if (addPreActionInfoFunctionBtn) {
            addPreActionInfoFunctionBtn.addEventListener('click', function(e) {
                e.preventDefault();
                addPreActionFunction(this.closest('.node-card'), "", "", true);
            });
        }

        // Initialize the default target node dropdown
        const defaultTargetSelect = nodeElement.querySelector('.default-target-node');
        if (defaultTargetSelect) {
            updateNodeTargetDropdown(defaultTargetSelect);

            // Add validation for default target
            defaultTargetSelect.addEventListener('change', function() {
                if (!this.value) {
                    this.classList.add('is-invalid');
                } else {
                    this.classList.remove('is-invalid');
                    this.classList.add('is-valid');
                }
            });
        }

        // Update info field dropdown
        updateInfoFieldDropdowns();

        // Add the node to the container
        container.appendChild(nodeElement);
        updateAllNodeTargetDropdowns();
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

            // We no longer use complete message, so we can skip this
            // const completeMessage = cleanString(nodeCard.querySelector('.node-complete-message')?.value || "");

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

            // Create node object
            // Collect transition conditions
            const transitionConditions = [];
            nodeCard.querySelectorAll('.transition-condition-card').forEach(conditionCard => {
                const variable = conditionCard.querySelector('.condition-variable').value;
                const operator = conditionCard.querySelector('.condition-operator').value;
                const targetNode = conditionCard.querySelector('.condition-target-node').value;
                const valueInput = conditionCard.querySelector('.condition-value');

                if (!variable || !operator || !targetNode) return;

                // Get the value based on the input type
                let value;
                if (valueInput.tagName === 'SELECT') {
                    value = valueInput.value === 'true';
                } else if (valueInput.type === 'number') {
                    value = parseFloat(valueInput.value);
                } else {
                    // For string or array input
                    const rawValue = cleanString(valueInput.value);

                    // Determine if this should be parsed as JSON (for arrays)
                    if (rawValue.startsWith('[') && rawValue.endsWith(']')) {
                        try {
                            value = JSON.parse(rawValue);
                        } catch (e) {
                            value = rawValue;
                        }
                    } else {
                        // Find the type of the variable
                        const varTypeSelect = document.querySelector(`.session-info-name[value="${variable}"]`)?.closest('.session-info-card')?.querySelector('.session-info-type');
                        const varType = varTypeSelect?.value || 'string';

                        if (varType === 'boolean') {
                            value = rawValue === 'true';
                        } else if (varType === 'number') {
                            value = parseFloat(rawValue);
                        } else {
                            value = rawValue;
                        }
                    }
                }

                transitionConditions.push({
                    parameters: {
                        variable_path: variable,
                        operator: operator,
                        value: value
                    },
                    target_node: targetNode
                });
            });

            // Get default target node
            const defaultTargetNode = nodeCard.querySelector('.default-target-node').value;

            const nodeData = {
                node_name: nodeName,
                task_message: taskMessage,
                schema_description: nodeCard.querySelector('.schema-description')?.value || "From the non-summarizing elements of the conversation, return whether each task has been accomplished, and for info fields, return an accurate and precise answer.",
                checklist_items: checklistItems,
                checklist_descriptions: checklistDescriptions,
                info_fields: infoFields,
                transition_conditions: transitionConditions,
                default_target_node: defaultTargetNode || 'end'
            };

            // Initialize pre-actions array
            const preActions = [];

            // Add text pre-action if provided
            const preActionText = nodeCard.querySelector('.pre-action-text');

            if (preActionText) {
                const preActionTextValue = cleanString(preActionText.value) || "";

                if (preActionTextValue.trim() !== "") {
                    preActions.push({
                        type: "tts_say",
                        text: preActionTextValue
                    });
                }
            }

            // Add function pre-actions from the pre-actions tab
            nodeCard.querySelectorAll('.pre-action-function-card').forEach(functionCard => {
                const sessionVar = cleanString(functionCard.querySelector('.pre-action-variable-select').value);
                const description = cleanString(functionCard.querySelector('.pre-action-function-description').value);

                if (sessionVar) {
                    const funcName = `get_${sessionVar}`;

                    // Check if this is an info field
                    const infoFields = Array.from(document.querySelectorAll('.session-info-name')).map(input => input.value);
                    const useInfoHandler = infoFields.includes(sessionVar);

                    // Create the function definition in the simplified format
                    const functionDef = {
                        type: "function",
                        handler: useInfoHandler ? "get_info_variable_handler" : "get_session_variable_handler",
                        variable_name: sessionVar
                    };

                    // No need to add current_index parameter in the simplified format

                    preActions.push(functionDef);
                }
            });

            // Add pre-actions to node data if any exist
            if (preActions.length > 0) {
                nodeData.pre_actions = preActions;
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

    // Validate node name uniqueness
    function validateNodeName(inputElement) {
        const name = inputElement.value.trim();

        // Check if empty
        if (!name) {
            inputElement.classList.add('is-invalid');
            inputElement.classList.remove('is-valid');
            return false;
        }

        // Check for uniqueness
        const allNodeNames = Array.from(document.querySelectorAll('.node-name'))
            .filter(input => input !== inputElement)
            .map(input => input.value.trim());

        if (allNodeNames.includes(name)) {
            inputElement.classList.add('is-invalid');
            inputElement.classList.remove('is-valid');
            return false;
        }

        // Valid name
        inputElement.classList.remove('is-invalid');
        inputElement.classList.add('is-valid');
        return true;
    }

    // Validate all required fields in the form
    function validateAllFields() {
        let isValid = true;
        let firstInvalidElement = null;

        // Validate flow name
        const flowName = document.getElementById('flowName');
        if (!flowName.value.trim()) {
            flowName.classList.add('is-invalid');
            isValid = false;
            firstInvalidElement = flowName;
        } else {
            flowName.classList.remove('is-invalid');
            flowName.classList.add('is-valid');
        }

        // Validate node names and task messages
        const nodeNames = new Set();
        const duplicateNodeNames = new Set();
        const emptyTaskMessages = [];

        document.querySelectorAll('.node-card').forEach(nodeCard => {
            // Validate node name
            const nodeNameInput = nodeCard.querySelector('.node-name');
            const name = nodeNameInput.value.trim();
            const nameDisplay = nodeCard.querySelector('.node-name-display').textContent;

            // Check if node name is empty
            if (!name) {
                nodeNameInput.classList.add('is-invalid');
                isValid = false;
                if (!firstInvalidElement) firstInvalidElement = nodeNameInput;
                return;
            }

            // Check for duplicate node names
            if (nodeNames.has(name)) {
                duplicateNodeNames.add(name);
                nodeNameInput.classList.add('is-invalid');
                isValid = false;
                if (!firstInvalidElement) firstInvalidElement = nodeNameInput;
            } else {
                nodeNames.add(name);
                nodeNameInput.classList.remove('is-invalid');
                nodeNameInput.classList.add('is-valid');
            }

            // Validate task message
            const taskMessage = nodeCard.querySelector('.node-task-message');
            if (!taskMessage.value.trim()) {
                taskMessage.classList.add('is-invalid');
                emptyTaskMessages.push(nameDisplay);
                isValid = false;
                if (!firstInvalidElement) firstInvalidElement = taskMessage;
            } else {
                taskMessage.classList.remove('is-invalid');
                taskMessage.classList.add('is-valid');
            }
        });

        // Show alerts for validation issues
        if (duplicateNodeNames.size > 0) {
            alert(`Duplicate node names found: ${Array.from(duplicateNodeNames).join(', ')}. Node names must be unique.`);
        }

        if (emptyTaskMessages.length > 0) {
            alert(`Task messages are missing for nodes: ${emptyTaskMessages.join(', ')}`);
        }

        // Validate transition conditions
        document.querySelectorAll('.transition-condition-card').forEach(conditionCard => {
            if (!verifyConditionFields(conditionCard)) {
                isValid = false;
                if (!firstInvalidElement) {
                    firstInvalidElement = conditionCard.querySelector('.is-invalid');
                }
            }
        });

        // Validate default target nodes
        document.querySelectorAll('.default-target-node').forEach(select => {
            if (!select.value) {
                select.classList.add('is-invalid');
                isValid = false;
                if (!firstInvalidElement) firstInvalidElement = select;
            } else {
                select.classList.remove('is-invalid');
                select.classList.add('is-valid');
            }
        });

        // Scroll to first invalid element if found
        if (firstInvalidElement) {
            firstInvalidElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
            firstInvalidElement.focus();
        }

        return isValid;
    }

    // Collect form data without debugging
    function collectFormDataForGeneration() {
        return collectFormData();
    }

    async function generateJson() {
        try {
            // Clear the console
            console.clear();

            // Advanced validation before collecting form data
            if (!validateAllFields()) {
                return;
            }

            // Get form data
            const formData = collectFormDataForGeneration();

            // Log the form data
            console.log("Form data to be sent:", formData);

            // Basic validation
            if (!formData.name) {
                alert('Flow name is required!');
                document.getElementById('flowName').classList.add('is-invalid');
                document.getElementById('flowName').focus();
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

            // Simplify to just use the standard download approach
            console.log("Sending request to /generate_json");

            // Send data to server to generate the JSON structure
            const response = await fetch('/generate_json', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(formData)
            });

            console.log("Response received:", response);
            const data = await response.json();
            console.log("Response data:", data);

            if (data.success) {
                // Create download link
                const downloadUrl = `/download/${data.filename}`;
                resultContainer.innerHTML = `
                <div class="alert alert-success">
                    <h4>JSON File Generated!</h4>
                    <p>Your conversation flow has been created successfully.</p>
                    <a href="${downloadUrl}" class="btn btn-primary" download>Download JSON File</a>
                </div>`;

                // Auto-download the file
                console.log("Downloading file:", downloadUrl);
                const downloadLink = document.createElement('a');
                downloadLink.href = downloadUrl;
                downloadLink.download = formData.name + '.json';
                document.body.appendChild(downloadLink);
                downloadLink.click();
                document.body.removeChild(downloadLink);

                return;
            } else {
                console.error("Error generating JSON:", data.error);
                resultContainer.innerHTML = `
                <div class="alert alert-danger">
                    <h4>Error Saving File</h4>
                    <p>${data.error || "There was a problem generating your file. Please try again."}</p>
                    <p class="small text-muted">Check browser console for details (F12).</p>
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
                <p class="small text-muted">Check browser console for details (F12).</p>
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
