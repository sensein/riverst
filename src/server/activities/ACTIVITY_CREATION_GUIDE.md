# Complete Guide to Creating Activities

This comprehensive guide provides in-depth documentation for creating sophisticated activities in the Riverst platform. It covers every component, configuration option, and best practice needed to build engaging, interactive learning experiences.

## Table of Contents

1. [Overview](#overview)
2. [Activity Structure](#activity-structure)
3. [Session Configuration (session_config.json)](#session-configuration)
4. [Flow Configuration (flow_config.json)](#flow-configuration)
5. [Step-by-Step Creation Process](#step-by-step-creation-process)
6. [Best Practices](#best-practices)
7. [Advanced Features](#advanced-features)
8. [Troubleshooting](#troubleshooting)

## Overview

Activities in Riverst are modular, self-contained units that define interactive experiences. Each activity can be either:

- **Simple Activities**: Basic configuration-driven activities using only `session_config.json`
- **Advanced Flow Activities**: Complex flow-driven activities with multiple conversational states use both `session_config.json` and `flow_config.json`

## Activity Structure

```
server/activities/
├── your-activity-name/
│   ├── session_config.json     # Required: Activity schema and configuration
│   ├── flow_config.json        # Optional: Conversation flow definition
│   ├── handlers.py            # Optional: Custom Python handlers
│   └── resources/             # Optional: Activity-specific assets
│       ├──resource_A.json...
```

## Session Configuration

The `session_config.json` file defines the activity's schema, available options, and metadata using JSON Schema format.

### Basic Structure

```json
{
  "title": "Activity Display Name",
  "description": "Schema description for your activity",
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "const": "your-activity-name"
    },
    "description": {
      "type": "string",
      "const": "Activity Display Name"
    },
    "options": {
      "type": "object",
      "properties": {
        // Activity-specific configuration options
      }
    }
  }
}
```

### Key Properties Explained

#### Required Properties

- **name**: Unique identifier for the activity (must match directory name)
- **description**: Human-readable activity name
- **options**: Container for all activity configuration options

#### Common Options

```json
"options": {
  "type": "object",
  "properties": {
    "advanced_flows": {
      "type": "boolean",
      "const": true,
      "default": true,
      "description": "Enable advanced conversation flows"
    },
    "tts_enabled": {
      "type": "boolean",
      "default": true,
      "description": "Enable text-to-speech output"
    },
    "stt_enabled": {
      "type": "boolean",
      "default": true,
      "description": "Enable speech-to-text input"
    },
    "llm_model": {
      "type": "string",
      "enum": ["gpt-4", "gpt-3.5-turbo", "claude-3"],
      "default": "gpt-4",
      "description": "Language model to use"
    },
    "difficulty_level": {
      "type": "string",
      "enum": ["beginner", "intermediate", "advanced"],
      "default": "beginner",
      "description": "Activity difficulty level"
    },
    "session_duration": {
      "type": "integer",
      "minimum": 5,
      "maximum": 60,
      "default": 15,
      "description": "Expected session duration in minutes"
    }
  }
}
```


## Flow Configuration

The `flow_config.json` file defines the conversation flow for advanced activities. This is where the real power of activity customization lies.

### Core Structure

```json
{
  "name": "activity-name",
  "description": "Flow description",
  "state_config": {
    "stages": { /* Stage definitions */ },
    "user": { /* User state variables */ },
    "activity": { /* Activity state variables */ },
    "session_variables": { /* Session-specific variables */ }
  },
  "flow_config": {
    "initial_node": "starting_stage",
    "nodes": { /* Node definitions */ }
  }
}
```

### State Configuration Deep Dive

#### Stages

Stages define the high-level progression of the activity with completion tracking:

```json
"stages": {
  "warm_up": {
    "checklist": {
      "friendly_greeting_done": false,
      "topic_introduced": false,
      "user_ready": false
    },
    "checklist_incomplete_message": "Please complete: {}",
    "checklist_complete_message": "Great! Moving to next stage.",
    "transition_logic": {
      "conditions": [
        {
          "parameters": {
            "variable_path": "user.confidence_level",
            "operator": ">=",
            "value": 3
          },
          "target_node": "advanced_content"
        }
      ],
      "default_target_node": "basic_content"
    }
  }
}
```

**Checklist Properties:**
- Keys represent completion criteria that must be verified
- Values start as `false` and are set to `true` via function calls
- Used to ensure all required elements are covered before progression

**Transition Logic:**
- **conditions**: Array of conditional branches
- **parameters**: Define the condition to evaluate
  - `variable_path`: Path to the variable to check
  - `operator`: Comparison operator (`==`, `!=`, `>=`, `<=`, `>`, `<`)
  - `value`: Value to compare against
- **target_node**: Which node to transition to if condition is met
- **default_target_node**: Fallback node if no conditions match

#### State Variables

```json
"user": {
  "confidence_level": 1,
  "topics_mastered": [],
  "current_progress": 0,
  "preferences": {
    "learning_style": "visual",
    "pace": "moderate"
  }
},
"activity": {
  "content_library": {
    "topics": ["topic1", "topic2"],
    "difficulty_levels": [1, 2, 3, 4, 5]
  },
  "current_content": null
},
```

### Flow Nodes

Nodes define the actual conversation interactions and behaviors:

role_messages carry across all nodes and must be present in the first node.
task_messages describe the task for that node in particular.

functions:
  Each node should have a function to check the completion of the node. Functions define what actions the AI can perform, such as checking progress, retrieving data, or executing custom business logic.

  **Built-in Handlers:**
  - `"handler": "general_handler"` - Progress tracking and state management
  - `"handler": "get_activity_handler"` - Activity-specific data retrieval
  - `"handler": "get_user_handler"` - User session variable access
  - `"handler": "get_variable_action_handler"` - Variable context management

  **Custom Handlers:**
  Create custom handlers in your activity's `handlers.py` file and reference them using the `"activity:"` prefix:
  ```json
  {
    "type": "function",
    "function": {
      "name": "my_custom_function",
      "handler": "activity:my_custom_handler"
    }
  }
  ```


pre-actions: execute functions automatically before the node transition process
  - `tts_say`: Speak text aloud before conversation begins
  - `get_variable`: Retrieve and prepare variables for the node
  - Custom actions using `"handler": "activity:my_handler"`

post-actions: execute functions automatically after the node transition process, use this for context adding functions
  - `get_variable`: Add variables to AI context after node completion
  - `end_conversation`: Terminate the conversation flow
  - Custom cleanup or state management actions

```json
"nodes": {
  "warm_up": {
    "name": "warm_up",
    "task_messages": [
      {
        "role": "system",
        "content": "Detailed instructions for the AI agent..."
      }
    ],
    "functions": [
      {
        "type": "function",
        "function": {
          "name": "check_progress",
          "description": "Check completion of warm-up tasks",
          "parameters": {
            "type": "object",
            "properties": {
              "greeting_completed": {
                "type": "boolean",
                "description": "Was the greeting completed?"
              }
            },
            "required": ["greeting_completed"]
          },
          "handler": "general_handler"
        }
      }
    ],
    "role_messages": [
      {
        "role": "system",
        "content": "You are a friendly tutor..."
      }
    ],
    "pre_actions": [
      {
        "type": "tts_say",
        "text": "Welcome! Let's begin."
      }
    ],
    "post_actions": [
      {
        "type": "get_variable",
        "variable_name": "user_progress",
        "handler": "get_variable_action_handler"
      }
    ]
  }
}
```

#### Node Components Explained

**task_messages**: System instructions for the AI agent
- Provide detailed, specific instructions for what the AI should do
- Include tool usage instructions
- Define the conversation flow and behavior

**functions**: Available function calls for the node
- **type**: Always "function" for custom functions
- **function**: Function definition object
  - **name**: Unique function identifier
  - **description**: What the function does
  - **parameters**: JSON Schema for function parameters
  - **handler**: Backend handler to process the function call

**role_messages**: Persistent system messages that define the AI's persona and behavior

**pre_actions**: Actions executed before the node conversation begins
- `tts_say`: Speak text aloud
- `get_variable`: Retrieve state variables
- `set_variable`: Set state variables
- Custom actions via handlers

**post_actions**: Actions executed after node completion
- Similar types as pre_actions
- Often used to save progress or prepare for next stage

### Function Handlers

Function handlers process the function calls made by the AI:

#### Built-in Handlers

1. **general_handler**: Processes checklist progress functions
   - Updates stage completion status
   - Manages state transitions
   - Handles user state updates

2. **get_variable_action_handler**: Retrieves variables from state
   - Accesses user, activity, or session variables
   - Provides data to the AI for decision making

3. **get_activity_handler**: Handles activity-specific data retrieval
   - Often used for content like reading contexts
   - Manages resource access

4. **get_session_variable_handler**: Specialized session variable access
   - Retrieves session-specific data
   - Manages temporary conversation state

#### Custom Handlers

You can create custom handlers in your activity's `handlers.py` file. Custom handlers are referenced using the `"activity:"` prefix.

**Creating Custom Handlers:**

1. **Create handlers.py in your activity directory:**
```python
# server/activities/my-activity/handlers.py

def custom_progress_handler(function_name, parameters, conversation_state):
    """Custom handler for specialized progress tracking."""
    # Process the function call
    result = process_custom_logic(parameters)

    # Update state if needed
    conversation_state.update_user_state(result)

    return {
        "status": "success",
        "data": result
    }

def custom_content_handler(function_name, parameters, conversation_state):
    """Custom handler for dynamic content generation."""
    user_level = parameters.get("user_level", 1)

    # Generate appropriate content based on user level
    content = generate_content_for_level(user_level)

    return {
        "status": "success",
        "content": content
    }
```

2. **Reference custom handlers in flow_config.json:**
```json
{
  "type": "function",
  "function": {
    "name": "check_custom_progress",
    "description": "Check progress using custom logic",
    "parameters": {
      "type": "object",
      "properties": {
        "task_completed": {
          "type": "boolean",
          "description": "Whether the task is completed"
        }
      },
      "required": ["task_completed"]
    },
    "handler": "activity:custom_progress_handler"
  }
}
```

**Handler Function Signature:**
All custom handlers must follow this signature:
```python
def handler_name(function_name: str, parameters: dict, conversation_state) -> dict:
    """
    Args:
        function_name: Name of the function being called
        parameters: Parameters passed from the AI function call
        conversation_state: Current conversation state object

    Returns:
        dict: Response data that will be returned to the AI
    """
    pass
```

**Built-in vs Custom Handler Reference:**
- Built-in handlers: `"handler": "general_handler"`
- Custom handlers: `"handler": "activity:my_custom_handler"`

**Error Handling:**
The system provides detailed error messages for custom handlers:
- Missing handlers.py file
- Handler function not found
- Handler is not callable
- Import/syntax errors in handlers.py

### Advanced Configuration Options

#### Conditional Content

```json
"functions": [
  {
    "type": "function",
    "function": {
      "name": "adaptive_content_selector",
      "description": "Select content based on user performance",
      "parameters": {
        "type": "object",
        "properties": {
          "performance_score": {
            "type": "number",
            "minimum": 0,
            "maximum": 100
          },
          "learning_style": {
            "type": "string",
            "enum": ["visual", "auditory", "kinesthetic"]
          }
        }
      },
      "handler": "adaptive_content_handler"
    }
  }
]
```

#### Multi-path Conversations

```json
"transition_logic": {
  "conditions": [
    {
      "parameters": {
        "variable_path": "user.age_group",
        "operator": "==",
        "value": "child"
      },
      "target_node": "child_friendly_content"
    },
    {
      "parameters": {
        "variable_path": "user.experience_level",
        "operator": ">=",
        "value": "advanced"
      },
      "target_node": "advanced_challenges"
    }
  ],
  "default_target_node": "standard_content"
}
```

## Step-by-Step Creation Process

### Step 1: Planning Your Activity

1. **Define the Purpose**
   - What learning objective does this activity serve?
   - Who is the target audience?
   - What outcomes should users achieve?

2. **Map the Flow**
   - Sketch out the conversation stages
   - Identify decision points and branches
   - Plan the progression logic

3. **Identify Resources**
   - What content/media assets are needed?
   - How will users interact with resources?
   - What data needs to be tracked?

### Step 2: Create Directory Structure

```bash
mkdir server/activities/your-activity-name
mkdir server/activities/your-activity-name/resources
```

### Step 3: Create session_config.json

Start with this template and customize:

```json
{
  "title": "Your Activity Name",
  "description": "Schema for configuring your activity",
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "const": "your-activity-name"
    },
    "description": {
      "type": "string",
      "const": "Your Activity Name"
    },
    "options": {
      "type": "object",
      "properties": {
        "advanced_flows": {
          "type": "boolean",
          "const": true,
          "default": true
        },
        "difficulty": {
          "type": "string",
          "enum": ["easy", "medium", "hard"],
          "default": "medium"
        }
      }
    }
  }
}
```

### Step 4: Create flow_config.json (if needed)

For advanced activities, create the flow configuration:

1. **Define State Structure**
   ```json
   "state_config": {
     "stages": {
       "introduction": { /* stage config */ },
       "main_content": { /* stage config */ },
       "conclusion": { /* stage config */ }
     },
     "user": { /* user state */ },
     "activity": { /* activity state */ }
   }
   ```

2. **Create Flow Nodes**
   ```json
   "flow_config": {
     "initial_node": "introduction",
     "nodes": {
       "introduction": { /* node config */ },
       "main_content": { /* node config */ },
       "conclusion": { /* node config */ }
     }
   }
   ```

3. **Add Functions and Handlers**
   - Define progress tracking functions using built-in handlers
   - Create custom handlers in `handlers.py` if needed
   - Set up state management and transitions

### Step 5: Add Custom Handlers (Optional)

If your activity needs custom business logic, create a `handlers.py` file:

```python
# server/activities/my-activity/handlers.py

def validate_user_input(function_name, parameters, conversation_state):
    """Custom validation for user responses."""
    user_input = parameters.get("user_input", "")

    # Custom validation logic
    is_valid = len(user_input) >= 3 and user_input.isalpha()

    if is_valid:
        # Update conversation state
        conversation_state.update_user_state({"last_valid_input": user_input})

    return {
        "status": "success",
        "is_valid": is_valid,
        "feedback": "Good input!" if is_valid else "Please provide at least 3 letters."
    }
```

### Step 6: Add Resources

Place any required assets in the `resources/` directory:
These should be json files containing activity-specific content and data.

### Step 7: Update Activity Registry

Add your activity to `assets/activity_groups.json`:

```json
{
  "groups": [
    {
      "name": "Your Group",
      "activities": [
        "your-activity-name"
      ]
    }
  ]
}
```

### Step 8: Test Your Activity

1. **Validate Configuration**
   - Check JSON syntax
   - Verify required fields
   - Test schema validation

2. **Test Flow Logic**
   - Walk through each conversation path
   - Verify state transitions
   - Check function calls

3. **Integration Testing**
   - Test with actual users
   - Monitor performance
   - Gather feedback

## Best Practices

### Configuration Design

1. **Keep It Simple**
   - Start with minimal configuration
   - Add complexity incrementally
   - Focus on core functionality first

2. **Use Descriptive Names**
   - Clear, meaningful function names
   - Descriptive variable names
   - Helpful descriptions for all properties

3. **Plan for Scalability**
   - Design flexible state structures
   - Use modular node organization
   - Plan for future enhancements

### Flow Design

1. **Clear Progression**
   - Logical stage transitions
   - Obvious completion criteria
   - Meaningful checkpoints

2. **Error Handling**
   - Graceful failure recovery
   - Clear error messages
   - Fallback paths

3. **User Experience**
   - Natural conversation flow
   - Appropriate pacing
   - Engaging interactions

### State Management

1. **Minimal State**
   - Only track necessary data
   - Clean up unused variables
   - Optimize for performance

2. **Consistent Structure**
   - Standard naming conventions
   - Predictable data formats
   - Clear data organization

## Advanced Features

### Dynamic Content Generation

```json
"functions": [
  {
    "type": "function",
    "function": {
      "name": "generate_personalized_content",
      "description": "Create content based on user profile",
      "parameters": {
        "type": "object",
        "properties": {
          "user_interests": {
            "type": "array",
            "items": {"type": "string"}
          },
          "difficulty_preference": {
            "type": "string",
            "enum": ["easy", "medium", "hard"]
          }
        }
      },
      "handler": "content_generation_handler"
    }
  }
]
```

### Multi-Modal Interactions

```json
"pre_actions": [
  {
    "type": "display_image",
    "image_path": "resources/images/lesson1.png"
  },
  {
    "type": "play_audio",
    "audio_path": "resources/audio/intro.mp3"
  },
  {
    "type": "tts_say",
    "text": "Let's explore this image together."
  }
]
```

### Adaptive Learning Paths

```json
"transition_logic": {
  "conditions": [
    {
      "parameters": {
        "variable_path": "user.performance_metrics.accuracy",
        "operator": ">=",
        "value": 0.8
      },
      "target_node": "advanced_challenges"
    },
    {
      "parameters": {
        "variable_path": "user.performance_metrics.accuracy",
        "operator": "<",
        "value": 0.6
      },
      "target_node": "remedial_practice"
    }
  ],
  "default_target_node": "standard_progression"
}
```

## Troubleshooting

### Common Issues

1. **JSON Syntax Errors**
   - Use a JSON validator
   - Check for missing commas/brackets
   - Verify quote consistency

2. **Schema Validation Failures**
   - Ensure all required fields are present
   - Check data types match schema
   - Verify enum values are valid

3. **Flow Logic Problems**
   - Test all transition paths
   - Verify condition logic
   - Check variable path references

4. **Function Call Issues**
   - Verify handler names are correct
   - Check parameter schema matches usage
   - Ensure required parameters are provided

### Debugging Tips

1. **Use Console Logging**
   - Add debug output to handlers
   - Log state changes
   - Track function calls

2. **Test Incrementally**
   - Start with simple flows
   - Add complexity gradually
   - Test each addition thoroughly

3. **Validate Early**
   - Check configuration syntax first
   - Test basic flow before adding features
   - Verify resource access

### Performance Optimization

1. **Minimize State Size**
   - Only store necessary data
   - Clean up completed stages
   - Use efficient data structures

2. **Optimize Function Calls**
   - Batch related operations
   - Cache frequently accessed data
   - Minimize external API calls

3. **Resource Management**
   - Optimize media file sizes
   - Use lazy loading for large assets
   - Implement resource cleanup

This comprehensive guide should give you everything you need to create sophisticated, engaging activities in the Riverst platform. Start simple, test thoroughly, and iterate based on user feedback to create the best possible learning experiences.
