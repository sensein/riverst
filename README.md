# riverst
Just a simple multimodal avatar interaction platform

## Introduction
Riverst is a platform for interactive interaction and data collection. It enables the easy creation of multimodal experiences—such as conversational agents, educational games, health-related interactions (for assessment and treatment) —and supports automatic behavioral analysis of the collected data (using [senselab](https://github.com/sensein/senselab)).

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

## 🙏 Acknowledgments

This project stands on the shoulders of some fantastic open-source work. Huge thanks to:

- **[TalkingHead](https://github.com/met4citizen/TalkingHead)** — a slick WebGL/Three.js talking-head renderer that makes avatars animations practical.
- **[Contextless Phonemes (CUPE)](https://github.com/tabahi/contexless-phonemes-CUPE)** — phoneme modeling utilities that help with time-stamped phoneme recognition efficiently.
- **[Pipecat](https://github.com/pipecat-ai/pipecat)** — a real-time, multimodal agent framework powering low-latency streaming and interactions.
- **[senselab](https://github.com/sensein/senselab)** — a python package for speech processing and analysis (e.g., behavior characterization, feature extraction, automatic speech recognition)


## Project board

You can follow [the project plan here](https://github.com/orgs/sensein/projects/55).
