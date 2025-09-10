# Activities Structure

This document describes the modular activity structure implemented in the system.

## Directory Structure

```
server/
├── activities/
│   ├── basic-avatar-demo/
│   │   └── session_config.json
│   ├── basic-avatar-interaction/
│   │   └── session_config.json
│   ├── dynamic-test/
│   │   ├── flow_config.json
│   │   └── session_config.json
│   ├── esl-vocab-tutoring/
│   │   └── session_config.json
│   ├── isl-vocab-tutoring/
│   │   └── session_config.json
│   └── vocab-tutoring/
│       ├── flow_config.json
│       ├── session_config.json
│       ├── book_processor.py
│       └── resources/
│           ├── alice_in_wonderland/
│           ├── a_christmas_carol.../
│           └── the_tale_of_peter_rabbit/
```

## File Types

### session_config.json
Contains the JSON schema that defines the configuration options for an activity. This file:
- Defines available settings and their defaults
- Specifies which services (STT, LLM, TTS) are supported
- Points to flow configuration files for advanced activities
- Contains validation rules and constraints

### flow_config.json
Contains the conversation flow definition for activities that use advanced flows. This file:
- Defines conversation stages and transitions
- Specifies available functions and handlers
- Contains system prompts and behavior instructions

### resources/
Directory containing activity-specific resources like books, audio files, or other assets.

### handlers.py (optional)
Contains activity-specific handler functions for custom business logic.

## API Endpoints

### Session Configuration
- `GET /api/activities/{activity_name}/session_config` - Load activity configuration schema

### Resources
- `GET /api/activities/{activity_name}/resources` - List available resources for an activity
- `GET /api/resources?activity={activity_name}` - Alternative resource listing
- `GET /api/resources/chapters?resourcePath={path}` - Get chapter count for a resource

## Adding New Activities

To add a new activity:

1. Create a new directory under `activities/`
2. Add a `session_config.json` file with the activity schema
3. For advanced flow activities, add a `flow_config.json` file
4. Optionally add a `resources/` directory with activity-specific assets
5. Update `assets/activity_groups.json` to include the new activity

### Example Activity Configuration

```json
{
  "title": "My New Activity",
  "description": "Schema for configuring my new activity.",
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "const": "my-new-activity"
    },
    "description": {
      "type": "string",
      "const": "My New Activity"
    },
    "options": {
      "type": "object",
      "properties": {
        "advanced_flows": {
          "type": "boolean",
          "const": false,
          "default": false
        }
      }
    }
  }
}
```

## Benefits

- **Modularity**: Each activity is self-contained
- **Plug-and-play**: Easy to add new activities
- **Resource Management**: Activity-specific resources are cleanly organized
- **Maintainability**: Clear separation of concerns
- **Scalability**: Easy to extend with new functionality
