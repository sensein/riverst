// Create a completely new script file with just the essential loading functionality
// This will be included alongside the main script.js

window.loadConfigFromFile = function(file) {
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
    
    const reader = new FileReader();
    
    reader.onload = function(e) {
        try {
            console.log("File content loaded, parsing JSON");
            const config = JSON.parse(e.target.result);
            console.log("JSON parsed successfully", config);
            
            // Show full config in debug output
            console.log("Full config:", config);
            
            // Basic validation for the new structure with flow_config
            if (!config.flow_config) {
                // Check if it's the old format
                if (config.name && config.flow_config && config.state_config && config.schemas) {
                    console.log("Detected old format configuration, converting to new format");
                    // Convert old format to new format structure
                    config = {
                        avatar_configuration: {
                            title: "Basic Avatar Interaction Configuration",
                            description: "Schema for configuring a basic avatar interaction activity.",
                            type: "object",
                            properties: {
                                name: {
                                    type: "string",
                                },
                                description: {
                                    type: "string",
                                },
                                options: {
                                    type: "object",
                                    properties: {
                                        advanced_flows: {
                                            type: "boolean",
                                            default: true
                                        },
                                        advanced_flows_config_path: {
                                            type: "string"
                                        }
                                    },
                                    required: ["advanced_flows", "advanced_flows_config_path"]
                                }
                            },
                            required: ["name", "description", "options"]
                        },
                        flow_config: {
                            name: config.name,
                            description: config.description,
                            state_config: config.state_config,
                            node_config: config.flow_config,
                            schemas: config.schemas
                        }
                    };
                } else {
                    throw new Error("Invalid configuration structure. File must contain flow_config section.");
                }
            }
            
            // Start loading the configuration
            loadBasicInfo(config);
            loadTaskVariables(config);
            loadNodes(config);
            
            // Update UI
            updateOrderAndDropdowns();
            
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
            console.error("Error loading file:", error);
            resultContainer.innerHTML = `
                <div class="alert alert-danger">
                    <h4>Error Loading Configuration</h4>
                    <p>${error.message}</p>
                    <p class="small">Check browser console (F12) for more details.</p>
                </div>
            `;
        }
    };
    
    reader.onerror = function(e) {
        console.error("FileReader error:", e);
        resultContainer.innerHTML = `
            <div class="alert alert-danger">
                <h4>Error Reading File</h4>
                <p>There was a problem reading the file. Please try again.</p>
            </div>
        `;
    };
    
    reader.readAsText(file);
};

// Helper functions for loading
function loadBasicInfo(config) {
    // Extract flow_config
    const flowsConfig = config.flow_config;
    
    // Store the name
    document.getElementById('currentFilename').value = flowsConfig.name + ".json";
    
    // Reset form
    document.getElementById('nodesContainer').innerHTML = '';
    document.getElementById('taskVariablesContainer').innerHTML = '';
    document.getElementById('sessionInfoContainer').innerHTML = '';
    
    // Load basic info
    document.getElementById('flowName').value = flowsConfig.name || "";
    document.getElementById('flowDescription').value = flowsConfig.description || "";
    
    // Load role message
    const initialNodeName = flowsConfig.node_config?.initial_node || "";
    const initialNode = flowsConfig.node_config?.nodes?.[initialNodeName] || {};
    const roleMessages = initialNode.role_messages || [];
    
    if (roleMessages.length > 0) {
        document.getElementById('roleMessage').value = roleMessages[0].content || "";
    }
}

function loadTaskVariables(config) {
    // Extract flow_config
    const flowsConfig = config.flow_config;
    
    const taskVars = flowsConfig.state_config?.task_variables || {};
    const infoFields = flowsConfig.state_config?.info || {};
    
    // Load task variables
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
        
        // Find description in schemas
        let description = `Info field for ${name}`;
        for (const schemaId in flowsConfig.schemas) {
            const schema = flowsConfig.schemas[schemaId];
            if (schema.properties && schema.properties[name]) {
                description = schema.properties[name].description || description;
                break;
            }
        }
        
        infoEl.querySelector('.session-info-description').value = description;
        
        // Add event listeners
        infoEl.querySelector('.remove-session-info-btn').addEventListener('click', function() {
            if (confirm('Remove this info field?')) {
                this.closest('.session-info-card').remove();
            }
        });
        
        container.appendChild(infoEl);
    }
}

function loadNodes(config) {
    // Extract flow_config
    const flowsConfig = config.flow_config;
    
    const nodes = flowsConfig.node_config?.nodes || {};
    const stages = flowsConfig.state_config?.stages || {};
    const initialNodeName = flowsConfig.node_config?.initial_node || "";
    
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
    const sequence = [];
    let currentNode = initialNodeName;
    
    // In the new structure, next_stage is in the stage data, not in node
    // Start by adding initial node
    if (currentNode) {
        sequence.push(currentNode);
    }
    
    // Follow the chain of next_stage in stages
    while (currentNode && currentNode !== 'end' && !sequence.includes(currentNode)) {
        const stageName = stageMapping[currentNode] || currentNode;
        const stage = stages[stageName] || {};
        currentNode = stage?.next_stage || null;
        
        if (currentNode && currentNode !== 'end' && !sequence.includes(currentNode)) {
            sequence.push(currentNode);
        }
        
        // Safety check
        if (sequence.length > 20) break;
    }
    
    // If sequence is empty, use all non-end nodes
    if (sequence.length === 0) {
        for (const nodeName in nodes) {
            if (nodeName !== 'end') sequence.push(nodeName);
        }
    }
    
    console.log("Node sequence:", sequence);
    
    // Create nodes
    for (const nodeName of sequence) {
        const node = nodes[nodeName];
        const stageName = stageMapping[nodeName] || nodeName;
        const stage = stages[stageName] || {};
        
        console.log(`Processing node: ${nodeName}, stage: ${stageName}`);
        
        createNodeFromConfig(nodeName, node, stage, flowsConfig);
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
        nodeEl.querySelector('.node-task-message').value = taskMessages[0].content || "";
    }
    
    // Find schema description
    let schemaDesc = "";
    for (const schemaId in config.schemas) {
        if (schemaId.includes(nodeName) || nodeName.includes(schemaId.replace('_schema', ''))) {
            schemaDesc = config.schemas[schemaId].description || "";
            break;
        }
    }
    nodeEl.querySelector('.schema-description').value = schemaDesc;
    
    // Set messages
    nodeEl.querySelector('.node-incomplete-message').value = stage.checklist_incomplete_message || `Please complete the following ${nodeName} items: {}`;
    nodeEl.querySelector('.node-complete-message').value = stage.checklist_complete_message || "Great job! Moving on to the next stage.";
    
    // Add checklist items
    const checklistContainer = nodeEl.querySelector('.checklist-container');
    checklistContainer.innerHTML = ''; // Clear defaults
    
    // Get schema for descriptions
    let schema = null;
    for (const schemaId in config.schemas) {
        if (schemaId.includes(nodeName) || nodeName.includes(schemaId.replace('_schema', ''))) {
            schema = config.schemas[schemaId];
            break;
        }
    }
    
    const properties = schema?.properties || {};
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
    
    // Add info fields
    const infoFieldsContainer = nodeEl.querySelector('.info-fields-container');
    
    // Find info fields for this node from schema
    if (schema && schema.properties) {
        for (const propName in schema.properties) {
            // Check if it's a state info field
            if (config.state_config?.info && propName in config.state_config.info) {
                const type = schema.properties[propName].type || 'boolean';
                
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
            }
        }
    }
    
    container.appendChild(nodeEl);
}

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