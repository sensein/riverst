# riverst
Just the coolest multimodal avatar interface 

## Introduction
Riverst is a platform for interactive interaction and data collection. It enables the easy creation of multimodal experiences—such as conversational agents, educational games, health-related assessment and treatment—and supports automatic behavioral analysis of the collected data. 

## Project Structure

```
src/
├── server/              # Bot server implementation
│   ├── utils           # Utility functions
│   ├── main.py        # FastAPI server
│   └── requirements.txt
└── client/              # Client implementations
    └── react/           # React client
```

### Important Note

The code has a client-server architecture. You find instructions on how to run the client and the server in the respective folders. The bot server must be running for the client to work. Start the server first before trying the client app.

### Requirements

- Python 3.10+
- Node.js 16+ (for React implementations)
- 3rd party services API KEYs
- Modern web browser with WebRTC support (e.g., Chrome 134)

## Project board

You can follow [the project plan here](https://github.com/users/fabiocat93/projects/3/views/1).