// file-loader.js - Handles loading and parsing configuration files


window.loadConfigFromFile = async function(file) {
    console.log("Starting to load file:", file.name);
    
    // Show a loading message to the user
    const resultContainer = document.getElementById('resultContainer');
    resultContainer.style.display = 'block';
    resultContainer.innerHTML = `
        <div class="alert alert-info">
            <h4>Loading Config File...</h4>
            <p>Please wait while we process your configuration file.</p>
        </div>
    `;
    
    // Read the file
    try {
        
        const reader = new FileReader();
        
        reader.onload = function(e) {
            try {
                console.log("File content loaded, parsing JSON");
                let config = JSON.parse(e.target.result);
                console.log("JSON parsed successfully", config);
                
                // Show full config in debug output
                console.log("Full config:", config);
                
                // Basic validation for the structure
                if (!config.name || (!config.flow_config && !config.flows_configuration)) {
                    throw new Error("Invalid configuration structure. File must contain name and flow_config sections.");
                }
                
                // Normalize to use flow_config for simplicity
                if (config.flows_configuration) {
                    console.log("Converting from flows_configuration to flow_config format");
                    config = {
                        name: config.flows_configuration.name,
                        description: config.flows_configuration.description,
                        state_config: config.flows_configuration.state_config,
                        flow_config: config.flows_configuration.node_config
                    };
                }
                
                // Start loading the configuration
                loadBasicInfo(config);
                loadTaskVariables(config);
                loadNodes(config);
                
                // Update UI
                updateOrderAndDropdowns();
                updateAllSessionVariableDropdowns();
                
                // Show success message
                resultContainer.innerHTML = `
                    <div class="alert alert-success">
                        <h4>Configuration Loaded!</h4>
                        <p>File "${file.name}" loaded successfully.</p>
                    </div>
                `;
                
                // Hide success message after 3 seconds
                setTimeout(() => {
                    resultContainer.style.display = 'none';
                }, 3000);
                
            } catch (error) {
                console.error("Error parsing file:", error);
                resultContainer.innerHTML = `
                    <div class="alert alert-danger">
                        <h4>Error Loading Configuration</h4>
                        <p>${error.message}</p>
                        <p class="small">The file may not be a valid JSON flow configuration. Check browser console (F12) for details.</p>
                    </div>
                `;
            }
        };
        
        reader.onerror = function(e) {
            console.error("FileReader error:", e);
            resultContainer.innerHTML = `
                <div class="alert alert-danger">
                    <h4>Error Reading File</h4>
                    <p>There was a problem reading the file. Please try again or try a different file.</p>
                </div>
            `;
        };
        
        // Read the file content
        reader.readAsText(file);
        
    } catch (error) {
        console.error("Error accessing file:", error);
        resultContainer.innerHTML = `
            <div class="alert alert-danger">
                <h4>Error Accessing File</h4>
                <p>${error.message || "There was a problem accessing the file. Please try again or use a different browser."}</p>
            </div>
        `;
    }
};

// Helper functions for loading
function loadBasicInfo(config) {
    // Store the original filename if we're loading an existing file
    const fileInput = document.getElementById('fileInput');
    if (fileInput && fileInput.files && fileInput.files[0]) {
        document.getElementById('currentFilename').value = fileInput.files[0].name;
    } else if (config.name) {
        document.getElementById('currentFilename').value = config.name + ".json";
    }
    
    // Reset form
    document.getElementById('nodesContainer').innerHTML = '';
    document.getElementById('taskVariablesContainer').innerHTML = '';
    document.getElementById('sessionInfoContainer').innerHTML = '';
    
    // Load basic info
    document.getElementById('flowName').value = config.name || "";
    document.getElementById('flowDescription').value = config.description || "";
    
    // Load role message
    const initialNodeName = config.flow_config?.initial_node || "";
    const initialNode = config.flow_config?.nodes?.[initialNodeName] || {};
    const roleMessages = initialNode.role_messages || [];
    
    if (roleMessages.length > 0) {
        document.getElementById('roleMessage').value = roleMessages[0].content || "";
    }
}

function loadTaskVariables(config) {
    // We don't use task_variables anymore, but handle them if present in older files
    const taskVars = config.state_config?.task_variables || {};
    const sessionVars = config.state_config?.session_variables || {};
    const infoFields = config.state_config?.info || {};
    
    // Load task variables (for backward compatibility)
    for (const [name, value] of Object.entries(taskVars)) {
        const container = document.getElementById('taskVariablesContainer');
        const varEl = document.getElementById('taskVarTemplate').content.cloneNode(true);
        
        // Set name
        varEl.querySelector('.task-var-name').value = name;
        
        // Set type and value
        const typeSelect = varEl.querySelector('.task-var-type');
        const valueContainer = varEl.querySelector('.task-var-value-container');
        
        // Determine type
        let type = 'string';
        if (typeof value === 'boolean') type = 'boolean';
        else if (typeof value === 'number') type = 'number';
        else if (Array.isArray(value)) {
            if (value.length > 0 && typeof value[0] === 'number') type = 'number_array';
            else type = 'array';
        }
        else if (typeof value === 'object' && value !== null) type = 'object';
        
        typeSelect.value = type;
        
        // Set value container
        if (type === 'boolean') {
            valueContainer.innerHTML = `
                <div class="form-check">
                    <input class="form-check-input task-var-value" type="checkbox" ${value ? 'checked' : ''}>
                    <label class="form-check-label">True</label>
                </div>`;
        } else if (type === 'array' || type === 'number_array') {
            valueContainer.innerHTML = `<input type="text" class="form-control form-control-sm task-var-value" value="${value.join(', ')}">`;
        } else if (type === 'object') {
            valueContainer.innerHTML = `<textarea class="form-control form-control-sm task-var-value" rows="2">${JSON.stringify(value, null, 2)}</textarea>`;
        } else {
            valueContainer.innerHTML = `<input type="${type === 'number' ? 'number' : 'text'}" class="form-control form-control-sm task-var-value" value="${value}">`;
        }
        
        // Add event listeners
        varEl.querySelector('.remove-task-var-btn').addEventListener('click', function() {
            this.closest('.task-var-card').remove();
            updateAllSessionVariableDropdowns();
        });
        
        // Add input event listener to update function dropdowns
        varEl.querySelector('.task-var-name').addEventListener('input', function() {
            updateAllSessionVariableDropdowns();
        });
        
        container.appendChild(varEl);
    }
    
    // Also load session variables
    for (const [name, value] of Object.entries(sessionVars)) {
        const container = document.getElementById('taskVariablesContainer');
        const varEl = document.getElementById('taskVarTemplate').content.cloneNode(true);
        
        // Set name
        varEl.querySelector('.task-var-name').value = name;
        varEl.querySelector('.task-var-name').dataset.varType = 'session';
        
        // Set type and value
        const typeSelect = varEl.querySelector('.task-var-type');
        const valueContainer = varEl.querySelector('.task-var-value-container');
        
        // Determine type
        let type = 'string';
        if (typeof value === 'boolean') type = 'boolean';
        else if (typeof value === 'number') type = 'number';
        else if (Array.isArray(value)) {
            if (value.length > 0 && typeof value[0] === 'number') type = 'number_array';
            else type = 'array';
        }
        else if (typeof value === 'object' && value !== null) type = 'object';
        
        typeSelect.value = type;
        
        // Set value container
        if (type === 'boolean') {
            valueContainer.innerHTML = `
                <div class="form-check">
                    <input class="form-check-input task-var-value" type="checkbox" ${value ? 'checked' : ''}>
                    <label class="form-check-label">True</label>
                </div>`;
        } else if (type === 'array' || type === 'number_array') {
            valueContainer.innerHTML = `<input type="text" class="form-control form-control-sm task-var-value" value="${value.join(', ')}">`;
        } else if (type === 'object') {
            valueContainer.innerHTML = `<textarea class="form-control form-control-sm task-var-value" rows="2">${JSON.stringify(value, null, 2)}</textarea>`;
        } else {
            valueContainer.innerHTML = `<input type="${type === 'number' ? 'number' : 'text'}" class="form-control form-control-sm task-var-value" value="${value}">`;
        }
        
        // Add event listeners
        varEl.querySelector('.remove-task-var-btn').addEventListener('click', function() {
            this.closest('.task-var-card').remove();
            updateAllSessionVariableDropdowns();
        });
        
        // Add input event listener to update function dropdowns
        varEl.querySelector('.task-var-name').addEventListener('input', function() {
            updateAllSessionVariableDropdowns();
        });
        
        container.appendChild(varEl);
    }
    
    // Load info fields
    for (const [name, value] of Object.entries(infoFields)) {
        const container = document.getElementById('sessionInfoContainer');
        const infoEl = document.getElementById('sessionInfoTemplate').content.cloneNode(true);
        
        // Set name and type
        infoEl.querySelector('.session-info-name').value = name;
        
        // Determine type
        let type = 'boolean';
        if (typeof value === 'string') type = 'string';
        else if (typeof value === 'number') type = 'number';
        else if (Array.isArray(value)) {
            if (value.length > 0 && typeof value[0] === 'number') type = 'number_array';
            else type = 'array';
        }
        
        infoEl.querySelector('.session-info-type').value = type;
        
        // Find description in function parameters
        let description = `Info field for ${name}`;
        
        // Look through all nodes for functions that might have this parameter
        for (const nodeName in config.flow_config.nodes) {
            const node = config.flow_config.nodes[nodeName];
            if (!node.functions) continue;
            
            for (const funcData of node.functions) {
                if (!funcData.function || !funcData.function.parameters) continue;
                
                const props = funcData.function.parameters.properties || {};
                if (props[name] && props[name].description) {
                    description = props[name].description;
                    break;
                }
            }
        }
        
        infoEl.querySelector('.session-info-description').value = description;
        
        // Add event listeners
        infoEl.querySelector('.remove-session-info-btn').addEventListener('click', function() {
            if (confirm('Remove this info field?')) {
                this.closest('.session-info-card').remove();
                updateAllSessionVariableDropdowns();
            }
        });
        
        // Add input event listener to update function dropdowns
        infoEl.querySelector('.session-info-name').addEventListener('input', function() {
            updateAllSessionVariableDropdowns();
        });
        
        container.appendChild(infoEl);
    }
}
            

function loadNodes(config) {
    const nodes = config.flow_config?.nodes || {};
    const stages = config.state_config?.stages || {};
    const initialNodeName = config.flow_config?.initial_node || "";
    
    // Create stage mapping
    const stageMapping = {};
    for (const nodeName in nodes) {
        if (nodeName === 'end') continue;
        
        // Try exact match first
        if (stages[nodeName]) {
            stageMapping[nodeName] = nodeName;
        } else {
            // Try similar names
            for (const stageName in stages) {
                if (nodeName.includes(stageName) || 
                    stageName.includes(nodeName) ||
                    (nodeName.includes('word') && stageName.includes('word'))) {
                    stageMapping[nodeName] = stageName;
                    break;
                }
            }
        }
    }
    
    console.log("Stage mapping:", stageMapping);
    
    // Build sequence
    let sequence = [];
    let currentNode = initialNodeName;
    
    // With dynamic transitions, we need to handle transition_logic
    // Start by adding initial node
    if (currentNode) {
        sequence.push(currentNode);
    }
    
    // Follow the chain using transition_logic
    while (currentNode && currentNode !== 'end' && !sequence.includes(currentNode)) {
        const stageName = stageMapping[currentNode] || currentNode;
        const stage = stages[stageName] || {};
        
        // Get the default target from transition_logic
        if (stage.transition_logic && stage.transition_logic.default_target_node) {
            currentNode = stage.transition_logic.default_target_node;
        } else {
            // If no transition_logic, we can't determine the next node
            break;
        }
        
        if (currentNode && currentNode !== 'end' && !sequence.includes(currentNode)) {
            sequence.push(currentNode);
        }
        
        // Safety check
        if (sequence.length > 20) break;
    }
    
    // If sequence is empty or incomplete, use all non-end nodes
    if (sequence.length === 0 || sequence.length < Object.keys(nodes).filter(n => n !== 'end').length) {
        sequence = Object.keys(nodes).filter(n => n !== 'end');
    }
    
    console.log("Node sequence:", sequence);
    
    // Create nodes
    for (const nodeName of sequence) {
        const node = nodes[nodeName];
        const stageName = stageMapping[nodeName] || nodeName;
        const stage = stages[stageName] || {};
        
        console.log(`Processing node: ${nodeName}, stage: ${stageName}`);
        
        createNodeFromConfig(nodeName, node, stage, config);
    }
}

function createNodeFromConfig(nodeName, node, stage, config) {
    const container = document.getElementById('nodesContainer');
    const nodeEl = document.getElementById('nodeTemplate').content.cloneNode(true);
    
    // Set node name
    const nameInput = nodeEl.querySelector('.node-name');
    const nameDisplay = nodeEl.querySelector('.node-name-display');
    nameInput.value = nodeName;
    nameDisplay.textContent = nodeName;
    
    // Set node task message
    const taskMessages = node.task_messages || [];
    if (taskMessages.length > 0) {
        let taskMessage = taskMessages[0].content || "";
        // If task message doesn't already have the prepended text, add it
        if (!taskMessage.startsWith('TOOLS:')) {
            taskMessage = `TOOLS: \nYou may silently call the check_${nodeName}_progress() function only after all ${nodeName} conversation steps have been completed. Do not mention you are doing this. Look at the other tools you have available, and if you need a certain piece of information that they provide, you may call them (silently, do not mention you are doing so!)\n\n${taskMessage}`;
        }
        nodeEl.querySelector('.node-task-message').value = taskMessage;
    }
    
    // Handle pre-actions if present
    if (node.pre_actions && node.pre_actions.length > 0) {
        // Look for tts_say actions
        const ttsAction = node.pre_actions.find(action => action.type === 'tts_say');
        if (ttsAction && ttsAction.text) {
            const preActionText = nodeEl.querySelector('.pre-action-text');
            if (preActionText) {
                preActionText.value = ttsAction.text;
            }
        }
        
        // Look for function pre-actions
        node.pre_actions.forEach(action => {
            if (action.type === 'function') {
                const handler = action.handler;
                
                // Handle all variable getters: we'll transform these to get_variable_action_handler
                if (handler === 'get_session_variable_handler' || 
                    handler === 'get_info_variable_handler' || 
                    handler === 'get_variable_action_handler') {
                    
                    // For simplified format, variable_name is directly on the action
                    let varName = action.variable_name;
                    
                    // Determine the source based on handler type or explicit source
                    let source = action.source || 
                                (handler === 'get_info_variable_handler' ? 'info' : 'session_variables');
                    
                    if (!varName) {
                        // Try to extract from the old format if needed
                        const funcDef = action.function;
                        if (funcDef && funcDef.parameters) {
                            const varEnum = funcDef.parameters?.properties?.variable_name?.enum;
                            if (varEnum && varEnum.length > 0) {
                                varName = varEnum[0];
                            } else {
                                return;
                            }
                        } else {
                            return;
                        }
                    }
                    
                    const isInfoVar = source === 'info';
                    const funcDescription = `Get the ${varName} for the session`;
                    
                    // Add as a pre-action function directly to the pre-actions tab
                    // This keeps the UI representation the same even though we'll convert
                    // these to post-actions when generating the JSON
                    addPreActionFunction(nodeEl, varName, funcDescription, isInfoVar);
                }
            }
        });
    }
    
    // Find schema description
    let schemaDesc = "";
    // Look through functions for the one with the general_handler
    if (node.functions) {
        for (const funcData of node.functions) {
            if (funcData.function && funcData.function.handler === "general_handler") {
                schemaDesc = funcData.function.description || "";
                break;
            }
        }
    }
    
    nodeEl.querySelector('.schema-description').value = "From the non-summarizing elements of the conversation, return whether each task has been accomplished, and for info fields, return an accurate and precise answer.";
    
    // Set incomplete message if element exists
    const incompleteMessageEl = nodeEl.querySelector('.node-incomplete-message');
    if (incompleteMessageEl) {
        incompleteMessageEl.value = stage.checklist_incomplete_message || `Please complete the following ${nodeName} items: {}`;
    }
    
    // Set up transitions
    const transitionLogic = stage.transition_logic || {};
    const defaultTarget = transitionLogic.default_target_node || "end";
    
    // Set default target node if present
    const defaultTargetSelect = nodeEl.querySelector('.default-target-node');
    if (defaultTargetSelect) {
        // Populate the dropdown first
        const nodes = Object.keys(config.flow_config.nodes);
        nodes.forEach(nodeName => {
            if (nodeName !== 'end') {
                const option = document.createElement('option');
                option.value = nodeName;
                option.text = nodeName;
                defaultTargetSelect.appendChild(option);
            }
        });
        
        // Add end node
        const endOption = document.createElement('option');
        endOption.value = 'end';
        endOption.text = 'end';
        defaultTargetSelect.appendChild(endOption);
        
        // Set selected value
        defaultTargetSelect.value = defaultTarget;
    }
    
    // Add transition conditions
    const transitionsContainer = nodeEl.querySelector('.transition-conditions-container');
    if (transitionsContainer && transitionLogic.conditions) {
        transitionLogic.conditions.forEach(condition => {
            const conditionEl = document.getElementById('transitionConditionTemplate').content.cloneNode(true);
            
            // Set variable
            const variableSelect = conditionEl.querySelector('.condition-variable');
            const infoFields = Object.keys(config.state_config.info || {});
            infoFields.forEach(field => {
                const option = document.createElement('option');
                option.value = field;
                option.text = field;
                variableSelect.appendChild(option);
            });
            
            if (condition.parameters && condition.parameters.variable_path) {
                variableSelect.value = condition.parameters.variable_path;
            }
            
            // Set operator
            const operatorSelect = conditionEl.querySelector('.condition-operator');
            if (condition.parameters && condition.parameters.operator) {
                operatorSelect.value = condition.parameters.operator;
            }
            
            // Set value
            const valueContainer = conditionEl.querySelector('.condition-value-container');
            const valueInput = conditionEl.querySelector('.condition-value');
            
            if (condition.parameters && condition.parameters.value !== undefined) {
                const value = condition.parameters.value;
                
                if (typeof value === 'boolean') {
                    // Replace input with select for boolean
                    valueContainer.innerHTML = `
                        <select class="form-select form-select-sm condition-value">
                            <option value="true">true</option>
                            <option value="false">false</option>
                        </select>
                    `;
                    valueContainer.querySelector('.condition-value').value = value ? 'true' : 'false';
                } else if (typeof value === 'number') {
                    // Number input
                    valueContainer.innerHTML = `<input type="number" class="form-control form-control-sm condition-value" value="${value}">`;
                } else if (Array.isArray(value)) {
                    // Array input
                    valueContainer.innerHTML = `<input type="text" class="form-control form-control-sm condition-value" value="${JSON.stringify(value)}">`;
                } else {
                    // String input
                    valueContainer.innerHTML = `<input type="text" class="form-control form-control-sm condition-value" value="${value}">`;
                }
            }
            
            // Set target node
            const targetSelect = conditionEl.querySelector('.condition-target-node');
            const nodes = Object.keys(config.flow_config.nodes);
            nodes.forEach(nodeName => {
                if (nodeName !== 'end') {
                    const option = document.createElement('option');
                    option.value = nodeName;
                    option.text = nodeName;
                    targetSelect.appendChild(option);
                }
            });
            
            // Add end node
            const endOption = document.createElement('option');
            endOption.value = 'end';
            endOption.text = 'end';
            targetSelect.appendChild(endOption);
            
            if (condition.target_node) {
                targetSelect.value = condition.target_node;
            }
            
            // Set up remove button
            conditionEl.querySelector('.remove-condition-btn').addEventListener('click', function() {
                this.closest('.transition-condition-card').remove();
            });
            
            transitionsContainer.appendChild(conditionEl);
        });
    }
    
    // Set up add condition button
    const addConditionBtn = nodeEl.querySelector('.add-condition-btn');
    if (addConditionBtn) {
        addConditionBtn.addEventListener('click', function() {
            const conditionEl = document.getElementById('transitionConditionTemplate').content.cloneNode(true);
            
            // Set up the condition variable dropdown
            const variableSelect = conditionEl.querySelector('.condition-variable');
            const infoFields = Object.keys(config.state_config.info || {});
            infoFields.forEach(field => {
                const option = document.createElement('option');
                option.value = field;
                option.text = field;
                variableSelect.appendChild(option);
            });
            
            // Set up the target node dropdown
            const targetSelect = conditionEl.querySelector('.condition-target-node');
            const nodes = Object.keys(config.flow_config.nodes);
            nodes.forEach(nodeName => {
                if (nodeName !== 'end') {
                    const option = document.createElement('option');
                    option.value = nodeName;
                    option.text = nodeName;
                    targetSelect.appendChild(option);
                }
            });
            
            // Add end node
            const endOption = document.createElement('option');
            endOption.value = 'end';
            endOption.text = 'end';
            targetSelect.appendChild(endOption);
            
            // Set up remove button
            conditionEl.querySelector('.remove-condition-btn').addEventListener('click', function() {
                this.closest('.transition-condition-card').remove();
            });
            
            transitionsContainer.appendChild(conditionEl);
        });
    }
    
    // Add checklist items
    const checklistContainer = nodeEl.querySelector('.checklist-container');
    checklistContainer.innerHTML = ''; // Clear defaults
    
    // Get checklist items and descriptions from the function with transition_callback
    let properties = {};
    
    if (node.functions) {
        for (const funcData of node.functions) {
            if (funcData.function && funcData.function.transition_callback === "general_transition_callback" && 
                funcData.function.handler === "general_handler") {
                properties = funcData.function.parameters?.properties || {};
                break;
            }
        }
    }
    
    const checklist = stage.checklist || {};
    
    for (const itemName in checklist) {
        // Skip fields that are in info
        if (config.state_config?.info && itemName in config.state_config.info) continue;
        
        const itemEl = document.getElementById('checklistItemTemplate').content.cloneNode(true);
        
        // Set name
        itemEl.querySelector('.checklist-item-name').value = itemName;
        
        // Get description
        let description = "";
        if (properties[itemName]) {
            description = properties[itemName].description || "";
        }
        itemEl.querySelector('.checklist-item-description').value = description;
        
        // Add event listener
        itemEl.querySelector('.remove-checklist-item-btn').addEventListener('click', function() {
            this.closest('.checklist-item-card').remove();
        });
        
        checklistContainer.appendChild(itemEl);
    }
    
    // Set up add checklist item button
    nodeEl.querySelector('.add-checklist-item-btn').addEventListener('click', function() {
        const itemEl = document.getElementById('checklistItemTemplate').content.cloneNode(true);
        itemEl.querySelector('.remove-checklist-item-btn').addEventListener('click', function() {
            this.closest('.checklist-item-card').remove();
        });
        checklistContainer.appendChild(itemEl);
    });
    
    // Load functions for this node
    loadNodeFunctions(nodeEl, nodeName, node);
    
    // Set up tabs
    nodeEl.querySelectorAll('[data-bs-toggle="tab"]').forEach(button => {
        button.addEventListener('click', function(event) {
            event.preventDefault();
            
            // Hide all tab panes
            const tabContent = this.closest('.node-card').querySelector('.tab-content');
            tabContent.querySelectorAll('.tab-pane').forEach(pane => {
                pane.classList.remove('show', 'active');
            });
            
            // Show target pane
            const targetSelector = this.getAttribute('data-bs-target');
            const targetPane = this.closest('.node-card').querySelector(targetSelector);
            if (targetPane) {
                targetPane.classList.add('show', 'active');
            }
            
            // Update buttons
            this.closest('ul').querySelectorAll('.nav-link').forEach(link => {
                link.classList.remove('active');
            });
            this.classList.add('active');
        });
    });
    
    // Set up remove button
    nodeEl.querySelector('.remove-node-btn').addEventListener('click', function() {
        if (document.querySelectorAll('.node-card').length <= 1) {
            alert('You must have at least one node.');
            return;
        }
        
        if (confirm('Remove this node?')) {
            this.closest('.node-card').remove();
            updateOrderAndDropdowns();
        }
    });
    
    // Set up dropdown function buttons
    // Dropdown buttons are set up via the event listeners in the template
    // No need to add additional buttons here
    const addSessionFunctionBtn = nodeEl.querySelector('.add-session-function');
    if (addSessionFunctionBtn) {
        addSessionFunctionBtn.addEventListener('click', function(e) {
            e.preventDefault();
            addNodeFunction(this.closest('.node-card'));
        });
    }
    
    const addInfoFunctionBtn = nodeEl.querySelector('.add-info-function');
    if (addInfoFunctionBtn) {
        addInfoFunctionBtn.addEventListener('click', function(e) {
            e.preventDefault();
            addNodeFunction(this.closest('.node-card'), "", "", true);
        });
    }
    
    // Add info fields
    const infoFieldsContainer = nodeEl.querySelector('.info-fields-container');
    
    // Find info fields for this node from function parameters
    let infoFieldsAdded = new Set();
    
    if (node.functions) {
        for (const funcData of node.functions) {
            if (!funcData.function || !funcData.function.parameters) continue;
            
            const props = funcData.function.parameters.properties || {};
            
            for (const propName in props) {
                // Check if it's a state info field and not already added
                if (config.state_config?.info && propName in config.state_config.info && !infoFieldsAdded.has(propName)) {
                    const type = props[propName].type || 'boolean';
                    
                    // Skip special fields
                    if (propName === 'current_word_number') continue;
                    
                    const fieldEl = document.getElementById('infoFieldItemTemplate').content.cloneNode(true);
                    
                    // Set field name and type
                    fieldEl.querySelector('.info-field-name').textContent = propName;
                    fieldEl.querySelector('.info-field-type').textContent = type;
                    
                    // Set up remove button
                    fieldEl.querySelector('.remove-info-field-btn').addEventListener('click', function() {
                        this.closest('.info-field-item-card').remove();
                    });
                    
                    infoFieldsContainer.appendChild(fieldEl);
                    infoFieldsAdded.add(propName);
                }
            }
        }
    }
    
    container.appendChild(nodeEl);
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
        
        if (funcData.function && (funcData.function.handler === "get_task_variable_handler" || 
                                 funcData.function.handler === "get_session_variable_handler" ||
                                 funcData.function.handler === "get_info_variable_handler")) {
            // Extract variable name
            const varEnum = funcData.function.parameters?.properties?.variable_name?.enum;
            if (!varEnum || varEnum.length === 0) return;
            
            const varName = varEnum[0];
            const funcName = funcData.function.name;
            const funcDescription = funcData.function.description || `Get the ${varName} for the session`;
            const handlerType = funcData.function.handler;
            
            // Add function to node - make sure we're passing parameters that match what addNodeFunction expects
            const funcElement = addNodeFunction(nodeEl, varName, funcDescription);
            
            // For info variables, update the dropdown class if needed
            if (handlerType === "get_info_variable_handler") {
                const select = funcElement.querySelector('.session-variable-select');
                if (select) {
                    select.classList.add('info-variable-select');
                    // Refresh the dropdown with info variables
                    updateSessionVariableDropdown(select);
                }
            }
        }
    });
}

// Update node order and dropdowns
function updateOrderAndDropdowns() {
    // Update node order highlighting
    const nodes = document.querySelectorAll('.node-card');
    nodes.forEach((node, index) => {
        const header = node.querySelector('.node-header');
        header.classList.remove('bg-primary', 'bg-success');
        
        if (index === 0) header.classList.add('bg-primary', 'text-white');
        else if (index === nodes.length - 1) header.classList.add('bg-success', 'text-white');
    });
    
    // Update info field dropdowns
    const infoFields = Array.from(document.querySelectorAll('.session-info-name')).map(
        input => ({
            name: input.value,
            type: input.closest('.session-info-card').querySelector('.session-info-type').value
        })
    ).filter(field => field.name.trim() !== '');
    
    // Update each node's info field dropdown
    document.querySelectorAll('.add-info-field-container').forEach(container => {
        container.innerHTML = '';
        
        if (infoFields.length > 0) {
            // Create select with options
            const selectGroup = document.createElement('div');
            selectGroup.className = 'input-group mb-2';
            
            const select = document.createElement('select');
            select.className = 'form-select info-field-select';
            
            // Default option
            const defaultOption = document.createElement('option');
            defaultOption.text = 'Select an info field...';
            defaultOption.value = '';
            select.appendChild(defaultOption);
            
            // Add options for each field
            infoFields.forEach(field => {
                const option = document.createElement('option');
                option.value = field.name;
                option.text = `${field.name} (${field.type})`;
                option.dataset.type = field.type;
                select.appendChild(option);
            });
            
            // Add button
            const button = document.createElement('button');
            button.className = 'btn btn-outline-primary add-info-field-btn';
            button.type = 'button';
            button.innerHTML = 'Add';
            
            // Add event listener
            button.addEventListener('click', function() {
                const select = this.closest('.input-group').querySelector('select');
                const selectedOption = select.options[select.selectedIndex];
                
                if (select.value) {
                    // Add the selected field
                    const nodeCard = this.closest('.node-card');
                    const container = nodeCard.querySelector('.info-fields-container');
                    const fieldEl = document.getElementById('infoFieldItemTemplate').content.cloneNode(true);
                    
                    fieldEl.querySelector('.info-field-name').textContent = select.value;
                    fieldEl.querySelector('.info-field-type').textContent = selectedOption.dataset.type;
                    
                    fieldEl.querySelector('.remove-info-field-btn').addEventListener('click', function() {
                        this.closest('.info-field-item-card').remove();
                    });
                    
                    container.appendChild(fieldEl);
                    select.value = '';
                }
            });
            
            selectGroup.appendChild(select);
            selectGroup.appendChild(button);
            container.appendChild(selectGroup);
        } else {
            // No fields message
            const message = document.createElement('div');
            message.className = 'alert alert-info py-2 small';
            message.textContent = 'Add session info fields first to make them available here.';
            container.appendChild(message);
        }
    });
}

// Make functions globally available
window.updateOrderAndDropdowns = updateOrderAndDropdowns;