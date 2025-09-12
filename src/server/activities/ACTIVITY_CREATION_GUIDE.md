# Complete Guide to Creating Activities

This comprehensive guide provides in-depth documentation for creating sophisticated activities in the Riverst platform. It covers every component, configuration option, and best practice needed to build engaging, interactive learning experiences.

## Table of Contents

1. [System Architecture and Activity Flow](#system-architecture-and-activity-flow)
2. [Prerequisites and Development Environment](#prerequisites-and-development-environment)
3. [Activity System Overview](#activity-system-overview)
4. [File Structure and Organization](#file-structure-and-organization)
5. [Session Configuration Deep Dive](#session-configuration-deep-dive)
6. [Flow Configuration Mastery](#flow-configuration-mastery)
7. [Backend Integration Points](#backend-integration-points)
8. [Frontend Integration](#frontend-integration)
9. [Step-by-Step Creation Process](#step-by-step-creation-process)
10. [Advanced Features](#advanced-features)
11. [Testing and Validation](#testing-and-validation)
12. [Deployment and Registration](#deployment-and-registration)
13. [Best Practices](#best-practices)
14. [Troubleshooting](#troubleshooting)

## System Architecture and Activity Flow

### How Activities Work in Riverst

Riverst activities are sophisticated, interactive learning experiences that integrate multiple AI services (Speech-to-Text, Large Language Models, Text-to-Speech) with a conversational flow system. Understanding the complete system architecture is crucial for creating effective activities.

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

## Activity System Overview

### Directory Structure Deep Dive

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

### Activity Registration and Discovery

#### 1. Activity Groups Configuration

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

#### 2. Backend API Integration

The backend exposes several key endpoints:

- `GET /api/activities` - Returns activity groups for frontend display
- `GET /api/activities/{name}/session_config` - Loads activity schema with API key filtering
- `GET /api/resources?activity={name}` - Lists available resources for activity
- `POST /api/session` - Creates new session with activity configuration
- `POST /api/offer` - Establishes WebRTC connection and starts activity

#### 3. Frontend Integration Points

Activities integrate with the frontend through:
- Activity discovery via homepage components
- Configuration interface generation from JSON Schema
- WebRTC connection management for real-time interaction
- Session state management and completion tracking

## File Structure and Organization

### Required Files

#### session_config.json (ALWAYS REQUIRED)
Defines the activity's schema, configuration options, and metadata using JSON Schema format.

**Purpose:**
- Validates user configuration inputs
- Defines available LLM, STT, TTS service options
- Specifies default values and constraints
- Enables dynamic UI generation in frontend
- Filters available options based on API key availability

**Key Properties:**
- `title` - Human-readable activity name
- `description` - Schema description for validation
- `properties.name` - Unique activity identifier (must match directory name)
- `properties.options` - All configurable activity options
- `required` - Required configuration fields

### Optional Files

#### flow_config.json (ADVANCED ACTIVITIES)
Defines sophisticated conversation flows with state management, function calling, and branching logic.

**When to Use:**
- Structured learning experiences with specific objectives
- Multi-stage conversations requiring completion tracking
- Dynamic content adaptation based on user responses
- Activities requiring custom business logic

#### handlers.py (CUSTOM LOGIC)
Contains Python functions for specialized business logic that built-in handlers cannot provide. These functions serve as handlers for functions defined in the flow_config.json file, which are callable by the LLM. These custom handlers are activity specifc, whereas the built-in handlers as in flows/handlers.py can be used in a variety of applications.

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
for key, model_list in {
    "llm_type": ["openai", "openai_gpt-realtime", "gemini"],
    "stt_type": ["openai"],
    "tts_type": ["openai"]
}.items():
    # Remove options for unavailable services
    filtered = [m for m in allowed if not (
        (not has_openai and m in ["openai", "openai_gpt-realtime"]) or
        (not has_google and m == "gemini")
    )]
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


## Flow Configuration Mastery

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

### Understanding the State System

Before diving into configuration details, it's important to understand what the flow state system does and how the different types of state work together.

#### State System Overview

The flow system uses three main types of state that serve different purposes in managing conversation flow and content delivery:

**1. User State - Session Memory**
- **Purpose**: Tracks user progress and preferences throughout the conversation
- **What it contains**: Current position (chapter, page), learning progress (words learned, tasks completed), user preferences, session-specific data
- **How it works**: Initialized from user selections, updated continuously via function calls, persists across conversation turns
- **Example**: `"user": {"index": 3, "vocab_words_learned": ["rabbit", "garden"], "current_progress": 0.6}`

**2. Activity State - Content Repository**
- **Purpose**: Provides static content and resources for the activity
- **What it contains**: Books, curricula, learning materials, structured content (chapters, vocabulary lists), reference data
- **How it works**: Loaded from external JSON files in `resources/` directory, selected by user, accessed via handler functions with indexing support
- **Example**: `"activity": {"reading_context": {"book_title": "Peter Rabbit", "chapters": [...]}}`

**3. Stages State - Flow Control**
- **Purpose**: Manages conversation progression and completion tracking
- **What it contains**: Checklists of required tasks per stage, transition rules between phases, progress tracking
- **How it works**: Defined in flow_config.json, updated as tasks complete, controls conversation progression
- **Example**: `"stages": {"warm_up": {"checklist": {"greeting_done": true, "topic_introduced": false}}}`

#### How They Work Together

**Integration Example**:
```
User picks chapter 3 → User State (index: 3) → Activity State provides chapter 3 content →
Stages State tracks introduction completion → LLM gets context about current chapter and remaining tasks
```

**System Purpose**:
- **User State**: "Where is the user in their learning journey?"
- **Activity State**: "What content should be presented to them?"
- **Stages State**: "What conversation tasks need to be completed?"

The system automatically manages context injection, so the LLM always knows what content is relevant, where the user is in their progress, and what needs to happen next in the conversation flow.

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
  "index": null,                     // Current chapter/page position
  "confidence_level": 1,
  "topics_mastered": [],
  "current_progress": 0,
  "preferences": {
    "learning_style": "visual",
    "pace": "moderate"
  }
},
"activity": {
  "reading_context": {               // Activity content with indexable navigation
    "indexable_by": "chapters",      // Enables automatic chapter navigation
    "book_title": "The Tale of Peter Rabbit",
    "chapters": [                    // Array structure for indexed access
      {
        "chapter_number": 1,
        "title": "Peter's Adventure Begins",
        "content": "Once upon a time...",
        "vocabulary": ["rabbit", "garden"]
      }
    ]
  }
},
```

#### Activity Data Indexable System

The `indexable_by` system enables automatic navigation through structured content like books, chapters, or lessons:

**How Indexable Data Works:**
```json
"activity": {
  "reading_context": {
    "indexable_by": "chapters",           // Key field that enables indexing
    "book_title": "Peter Rabbit",
    "total_chapters": 4,
    "chapters": [                         // Array that gets indexed
      {"chapter_number": 1, "title": "Chapter 1", "content": "..."},
      {"chapter_number": 2, "title": "Chapter 2", "content": "..."},
      {"chapter_number": 3, "title": "Chapter 3", "content": "..."},
      {"chapter_number": 4, "title": "Chapter 4", "content": "..."}
    ]
  }
}
```

**Index Resolution Process:**
1. **Function Parameter**: Direct specification `{"current_index": 2}`
2. **User Session State**: From user state `{"user": {"index": 3}}`
3. **User Prompting**: System asks user "Which chapter would you like?"

**Automatic Navigation:**
- System automatically resolves which chapter to show
- Validates index is within bounds (1 to total chapters)
- Returns specific chapter data to LLM context
- Handles navigation between chapters seamlessly

**Usage in Functions:**
```json
{
  "type": "function",
  "function": {
    "name": "get_current_chapter",
    "description": "Get information about the current chapter",
    "parameters": {
      "type": "object",
      "properties": {
        "current_index": {
          "type": "integer",
          "description": "Specific chapter number (optional)"
        }
      }
    },
    "handler": "get_activity_handler"     // Handles indexable data automatically
  }
}
```

**Benefits:**
- Users can navigate content naturally ("Let's go to chapter 3")
- System remembers current position across conversation
- Content adapts automatically based on user's current location
- No manual content management required

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
- **Context injection**: Automatically adds relevant data to LLM conversation context

#### Context Injection System

Post-actions provide automatic context injection, making state data available to the LLM without manual management:

**Automatic Variable Injection:**
```json
"post_actions": [
  {
    "type": "get_variable",
    "variable_name": "reading_context",        // Variable to inject
    "handler": "get_variable_action_handler"   // Context injection handler
  }
]
```

**What Happens:**
1. **Node Completion**: Current conversation node finishes
2. **Handler Execution**: `get_variable_action_handler` retrieves the specified variable
3. **Data Formatting**: Variable data formatted for LLM consumption
4. **Context Addition**: System message automatically queued to conversation
5. **LLM Access**: Next LLM interaction includes structured context

**Example Context Injection Result:**
```
SYSTEM: Current Reading Context:
Book: The Tale of Peter Rabbit by Beatrix Potter
Current Chapter: Chapter 2 - Meeting Mr. McGregor
Content: Peter squeezed under the gate into Mr. McGregor's garden...
Vocabulary Words: farmer, vegetables
```

**Context Injection Types:**
- **Activity Variables**: Content from resources (books, curricula)
- **User Variables**: Session progress and preferences
- **Dynamic Data**: Real-time calculated information

**Benefits:**
- LLM always has relevant context
- No manual context management required
- Automatic adaptation to user's current state
- Consistent information delivery

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

## System Architecture and Activity Flow

### How Activities Work in Riverst

Riverst activities integrate multiple AI services with a conversational flow system to create interactive learning experiences.

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

#### API Integration

The backend exposes key endpoints:

- `GET /api/activities` - Returns activity groups for frontend display
- `GET /api/activities/{name}/session_config` - Loads activity schema with API key filtering
- `GET /api/resources?activity={name}` - Lists available resources for activity
- `POST /api/session` - Creates new session with activity configuration
- `POST /api/offer` - Establishes WebRTC connection and starts activity

#### Frontend Integration

Activities integrate with the frontend through:
- Activity discovery via homepage components
- Configuration interface generation from JSON Schema
- WebRTC connection management for real-time interaction
- Session state management and completion tracking

#### Activity Groups Configuration

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
