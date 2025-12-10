# Complete Guide to Creating Activities

This comprehensive guide provides in-depth documentation for creating sophisticated activities in the Riverst platform. It covers every component, configuration option, and best practice needed to build engaging, interactive learning experiences.

## Table of Contents

1. [System Architecture and Activity Flow](#system-architecture-and-activity-flow)
2. [Prerequisites and Development Environment](#prerequisites-and-development-environment)
3. [File Structure and Organization](#file-structure-and-organization)
4. [Session Configuration Deep Dive](#session-configuration-deep-dive)
5. [Flow Configuration Mastery](#flow-configuration-mastery)
6. [Handler System](#handler-system)
7. [Step-by-Step Creation Process](#step-by-step-creation-process)
8. [Best Practices](#best-practices)
9. [API Reference](#api-reference)

## System Architecture and Activity Flow

### How Activities Work in Riverst

Riverst activities are sophisticated, interactive learning experiences that integrate multiple AI services (Speech-to-Text, Large Language Models, Text-to-Speech) with a conversational flow system.

#### The Complete Activity Lifecycle

1. **Activity Discovery** → Frontend loads activity groups from `/api/activities`
2. **Activity Configuration** → User selects activity and configures options via session schema
3. **Session Creation** → Frontend calls `/api/session` with configuration
4. **WebRTC Connection** → Real-time audio/video connection established via `/api/offer`
5. **Flow Initialization** → Backend loads flow configuration and initializes conversation state
6. **Conversational Loop** → AI agent follows flow logic, managing state transitions
7. **Session Completion** → Flow reaches end node, session data is saved

#### Core System Components

**Frontend (React)**
- `ActivityCard.tsx` - Displays activity options to users
- `GroupedActivitySection.tsx` - Organizes activities by category
- `AvatarInteractionSettings.tsx` - Activity configuration interface
- WebRTC connection management for real-time interaction

**Backend (FastAPI)**
- `main.py` - Core API endpoints for activities and sessions
- `bot_runner.py` - Orchestrates AI pipeline and flow management
- `flow_factory.py` - Builds and configures flow managers
- `loaders.py` - Loads and validates flow configurations
- `handlers.py` - Built-in flow state management functions

**Flow System (Pipecat-Flows)**
- State management with stage progression tracking
- Function calling system for dynamic behavior
- Transition logic for adaptive conversation paths
- Context management for maintaining conversation history

### Activity Types and Complexity Levels

**Simple Activities** (Configuration Only)
- Use only `session_config.json` for basic interactions
- Rely on built-in conversation patterns
- Suitable for open-ended conversations or demos
- Examples: `basic-avatar-interaction`, `basic-avatar-demo`

**Advanced Flow Activities** (Full Flow System)
- Use both `session_config.json` and `flow_config.json`
- Implement structured conversation stages with completion tracking
- Support dynamic content adaptation and branching logic
- Examples: `vocab-tutoring`, `esl-vocab-tutoring`, `isl-vocab-tutoring`

### Activity Registration and Discovery

Activities are organized into groups via `server/assets/activity_groups.json`:

```json
[
  {
    "title": "Your Activity Category",
    "activities": [
      {
        "title": "Activity Display Name",
        "images": ["/figures/icon1.svg", "/figures/icon2.svg"],
        "description": "User-facing description",
        "route": "/avatar-interaction-settings",
        "disabled": false,
        "settings_options_filepath": "api/activities/your-activity/session_config"
      }
    ]
  }
]
```

## Prerequisites and Development Environment

### Required Knowledge
- **JSON Schema** - For activity configuration validation
- **Python** - For custom handlers and backend integration
- **TypeScript/React** - For frontend integration (if needed)
- **Conversational AI Concepts** - Understanding of LLM interactions and flow design
- **Pipecat Framework** - For advanced flow features

### Development Tools
- **JSON Validator** - For configuration syntax checking
- **Python Environment** - For handler development and testing
- **FastAPI** - Backend framework knowledge
- **WebRTC Understanding** - For real-time communication features

### System Dependencies
- OpenAI API access (for LLM, STT, TTS services)
- Google API access (optional, for Gemini LLM)
- Pipecat and Pipecat-Flows libraries
- FastAPI backend with WebRTC support

## File Structure and Organization

### Directory Structure

```
server/activities/
├── assets/
│   ├── activity_groups.json      # Frontend activity organization
│   └── avatars.json              # Available avatar configurations
├── your-activity-name/           # Your activity directory
│   ├── session_config.json       # REQUIRED: JSON Schema for activity options
│   ├── flow_config.json          # OPTIONAL: Conversation flow definition
│   ├── handlers.py               # OPTIONAL: Custom Python business logic
│   └── resources/                # OPTIONAL: Activity-specific data files
│       ├── resource_1.json       # Books, content, or other data
│       └── resource_2.json       # Multiple resources supported
└── existing-activities/          # Reference implementations
    ├── vocab-tutoring/           # Complex flow example
    ├── basic-avatar-demo/        # Simple configuration example
    └── ...
```

### Required Files

#### session_config.json (ALWAYS REQUIRED)
Defines the activity's schema, configuration options, and metadata using JSON Schema format.

**Purpose:**
- Validates user configuration inputs
- Defines available LLM, STT, TTS service options
- Specifies default values and constraints
- Enables dynamic UI generation in frontend
- Filters available options based on API key availability

### Optional Files

#### flow_config.json (ADVANCED ACTIVITIES)
Defines sophisticated conversation flows with state management, function calling, and branching logic.

**When to Use:**
- Structured learning experiences with specific objectives
- Multi-stage conversations requiring completion tracking
- Dynamic content adaptation based on user responses
- Activities requiring custom business logic

#### handlers.py (CUSTOM LOGIC)
Contains Python functions for specialized business logic that built-in handlers cannot provide.

**Use Cases:**
- Complex content generation algorithms
- External API integrations
- Specialized validation or processing logic
- Custom state management requirements

#### resources/ Directory (CONTENT ASSETS)
Stores activity-specific data files, typically JSON formatted.

**Common Resource Types:**
- Books or reading materials (`book_title.json`)
- Learning content databases
- Media asset references
- Configuration templates

### File Naming Conventions

**Activity Directory Names:**
- Use kebab-case: `vocab-tutoring`, `basic-avatar-demo`
- Be descriptive but concise
- Avoid special characters or spaces
- Must match `properties.name.const` in session_config.json

**Resource File Names:**
- Use snake_case or kebab-case consistently
- Include file type in name when helpful: `peter_pan.json`
- Group related resources logically

## Session Configuration Deep Dive

The `session_config.json` file is the cornerstone of every activity. It defines a complete JSON Schema that validates user configurations, generates the frontend interface, and provides metadata for the entire system.

### Complete Schema Structure

```json
{
  "title": "Human-Readable Activity Name",
  "description": "Schema description used for validation and documentation",
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "const": "directory-name-exactly",
      "description": "Must match activity directory name exactly"
    },
    "description": {
      "type": "string",
      "const": "Display Name for UI",
      "description": "User-facing activity name"
    },
    "options": {
      "type": "object",
      "properties": {
        // All configurable options go here - see detailed breakdown below
      },
      "required": ["list", "of", "required", "options"]
    }
  },
  "required": ["name", "description", "options"],
  "additionalProperties": false
}
```

### Critical Configuration Options

#### Flow System Integration

```json
"advanced_flows": {
  "type": "boolean",
  "const": true,  // or false for simple activities
  "default": true,
  "description": "Enable structured conversation flows with state management"
},
"advanced_flows_config_path": {
  "type": "string",
  "const": "./activities/your-activity/flow_config.json",
  "description": "Path to flow configuration file (required if advanced_flows = true)"
}
```

#### AI Service Configuration

```json
"pipeline_modality": {
  "type": "string",
  "enum": ["classic"],  // "e2e" not supported for advanced flows
  "default": "classic",
  "description": "Pipeline architecture: classic = separate STT/LLM/TTS services"
},
"stt_type": {
  "type": "string",
  "enum": ["whisper", "openai"],  // Filtered by backend based on API keys
  "default": "openai",
  "description": "Speech-to-text service selection"
},
"llm_type": {
  "type": "string",
  "enum": ["openai", "openai_gpt-realtime", "gemini"],  // Auto-filtered
  "default": "openai",
  "description": "Language model service selection"
},
"tts_type": {
  "type": "string",
  "enum": ["openai", "kokoro"],  // Add other TTS providers as needed
  "default": "openai",
  "description": "Text-to-speech service selection"
}
```

#### Avatar and Embodiment Settings

```json
"embodiment": {
  "type": "string",
  "enum": ["humanoid_avatar", "waveform"],
  "default": "humanoid_avatar",
  "description": "Visual representation type"
},
"body_animations": {
  "type": "array",
  "items": {
    "type": "string",
    "enum": ["dance", "wave", "i_have_a_question", "thank_you", "i_dont_know",
             "ok", "thumbup", "thumbdown", "happy", "sad", "angry", "fear",
             "disgust", "love", "sleep"]
  },
  "default": ["wave", "thumbup", "happy"],
  "description": "Available avatar animations for expression"
},
"camera_settings": {
  "type": "string",
  "enum": ["full", "mid", "upper", "head"],
  "default": "upper",
  "description": "Avatar camera framing"
}
```

#### Dynamic Content Integration

```json
"activity_variables_path": {
  "type": "string",
  "title": "Content Selection",
  "dynamicEnum": "books",  // Backend generates options from resources/
  "default": "./activities/your-activity/resources/default_content.json",
  "description": "Select content file for activity"
},
"index": {
  "type": "integer",
  "title": "Starting Chapter/Section",
  "minimum": 1,
  "default": null,
  "description": "Starting point in indexed content (null = ask user)"
}
```

#### User Experience Options

```json
"user_description": {
  "type": "string",
  "maxLength": 500,
  "default": "Default user persona for this activity",
  "description": "Customize the user persona for personalized interactions"
},
"languages": {
  "type": "array",
  "items": {
    "type": "string",
    "enum": ["english", "italian", "spanish", "german"]
  },
  "default": ["english"],
  "description": "Supported interaction languages"
}
```

### API Key Filtering System

The backend automatically filters configuration options based on available API keys:

```python
# From main.py - automatic filtering logic
has_openai = os.getenv("OPENAI_API_KEY") is not None
has_google = os.getenv("GOOGLE_API_KEY") is not None

# Options are filtered to only show available services
```

### Conditional Schema Logic

Use JSON Schema's `allOf`, `if/then` patterns for complex validation:

```json
"allOf": [
  {
    "if": {
      "properties": {
        "advanced_flows": { "enum": [true] }
      }
    },
    "then": {
      "required": ["advanced_flows_config_path"],
      "properties": {
        "advanced_flows_config_path": {
          "type": "string",
          "pattern": "^\\./activities/.+/flow_config\\.json$"
        }
      }
    }
  }
]
```

## Flow Configuration Mastery

The `flow_config.json` file defines the conversation flow for advanced activities.

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

### Understanding the State System

The flow system uses three main types of state that serve different purposes:

**1. User State - Session Memory**
- **Purpose**: Tracks user progress and preferences throughout the conversation
- **Contains**: Current position, learning progress, user preferences, session-specific data
- **Example**: `"user": {"index": 3, "vocab_words_learned": ["rabbit", "garden"]}`

**2. Activity State - Content Repository**
- **Purpose**: Provides static content and resources for the activity
- **Contains**: Books, curricula, learning materials, structured content
- **Example**: `"activity": {"reading_context": {"book_title": "Peter Rabbit", "chapters": [...]}}`

**3. Stages State - Flow Control**
- **Purpose**: Manages conversation progression and completion tracking
- **Contains**: Checklists of required tasks per stage, transition rules, progress tracking
- **Example**: `"stages": {"warm_up": {"checklist": {"greeting_done": true}}}`

### State Configuration

#### Stages with Transition Logic

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

#### Activity Data Indexable System

The `indexable_by` system enables automatic navigation through structured content:

```json
"activity": {
  "reading_context": {
    "indexable_by": "chapters",           // Key field that enables indexing
    "book_title": "Peter Rabbit",
    "total_chapters": 4,
    "chapters": [                         // Array that gets indexed
      {"chapter_number": 1, "title": "Chapter 1", "content": "..."},
      {"chapter_number": 2, "title": "Chapter 2", "content": "..."}
    ]
  }
}
```

**Index Resolution Process:**
1. **Function Parameter**: Direct specification `{"current_index": 2}`
2. **User Session State**: From user state `{"user": {"index": 3}}`
3. **User Prompting**: System asks user "Which chapter would you like?"

### Flow Nodes

Nodes define the actual conversation interactions and behaviors:

```json
"nodes": {
  "warm_up": {
    "name": "warm_up",
    "role_messages": [
      {
        "role": "system",
        "content": "You are a friendly tutor..."
      }
    ],
    "task_messages": [
      {
        "role": "system",
        "content": "Detailed instructions for this specific node..."
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
    "pre_actions": [
      {
        "type": "tts_say",
        "text": "Welcome! Let's begin."
      }
    ],
    "post_actions": [
      {
        "type": "get_variable",
        "variable_name": "reading_context",
        "handler": "get_variable_action_handler"
      }
    ]
  }
}
```

#### Node Components

- **role_messages**: Persistent system messages defining AI persona (carry across all nodes)
- **task_messages**: Node-specific instructions for the AI agent
- **functions**: Available function calls for the node
- **pre_actions**: Actions executed before node conversation begins
- **post_actions**: Actions executed after node completion (often for context injection)

#### Context Injection System

Post-actions provide automatic context injection to the LLM:

```json
"post_actions": [
  {
    "type": "get_variable",
    "variable_name": "reading_context",
    "handler": "get_variable_action_handler"
  }
]
```

This automatically adds relevant data to the LLM's context without manual management.

## Handler System

### Built-in Handlers

Built-in handlers are provided by the system and referenced directly by name:

1. **general_handler**: Processes checklist progress functions
   - Updates stage completion status
   - Manages state transitions
   - Handles user state updates

2. **get_variable_action_handler**: Retrieves variables from state
   - Accesses user, activity, or session variables
   - Provides data to the AI for decision making

3. **get_activity_handler**: Handles activity-specific data retrieval
   - Often used for content like reading contexts
   - Manages resource access with indexable support

4. **get_session_variable_handler**: Specialized session variable access
   - Retrieves session-specific data
   - Manages temporary conversation state

### Custom Handlers

Custom handlers are created in your activity's `handlers.py` file and referenced with the `"activity:"` prefix.

#### Creating Custom Handlers

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

#### Handler Function Signature

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

#### Handler Reference Pattern

- Built-in handlers: `"handler": "general_handler"`
- Custom handlers: `"handler": "activity:my_custom_handler"`

The system provides detailed error messages for:
- Missing handlers.py file
- Handler function not found
- Handler is not callable
- Import/syntax errors in handlers.py

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

For advanced activities:

1. **Define State Structure**
2. **Create Flow Nodes**
3. **Add Functions and Handlers**
4. **Set up transitions**

### Step 5: Add Custom Handlers (Optional)

Create `handlers.py` if custom business logic is needed.

### Step 6: Add Resources

Place JSON resources in the `resources/` directory.

### Step 7: Update Activity Registry

Add your activity to `assets/activity_groups.json`.

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

## API Reference

### Core Endpoints

- `GET /api/activities` - Returns activity groups for frontend display
- `GET /api/activities/{name}/session_config` - Loads activity schema with API key filtering
- `GET /api/resources?activity={name}` - Lists available resources for activity
- `POST /api/session` - Creates new session with activity configuration
- `POST /api/offer` - Establishes WebRTC connection and starts activity

### Frontend Integration Points

Activities integrate with the frontend through:
- Activity discovery via homepage components
- Configuration interface generation from JSON Schema
- WebRTC connection management for real-time interaction
- Session state management and completion tracking
