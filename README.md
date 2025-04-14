# riverst
Just the coolest multimodal avatar interface 

## Project Structure

```
src/
├── server/              # Bot server implementation
│   ├── bot.py    # bot implementation
│   ├── runner.py        # Server runner utilities
│   ├── server.py        # FastAPI server
│   └── requirements.txt
└── client/              # Client implementations
    └── react/           # React client
```

## Important Note

The code has a client-server architecture. You find instructions on how to run the client and the server in the respective folders. The bot server must be running for the client to work. Start the server first before trying the client app.

## Requirements

- Python 3.10+
- Node.js 16+ (for React implementations)
- 3rd party services API KEYs
- Modern web browser with WebRTC support (e.g., Chrome 134)


## TODO:
- [x] Implement a way for Realtime to output body motions (Fabio)
    - https://platform.openai.com/docs/guides/realtime-conversations
    - https://github.com/pipecat-ai/pipecat/blob/main/src/pipecat/services/openai_realtime_beta/openai.py
    - https://github.com/pipecat-ai/pipecat/blob/main/src/pipecat/services/openai_realtime_beta/events.py
    - add some more animations
- [x] incorporating video (with google gemini, but honestly doesn't work very well) (Fabio)
- [x] Getting visemes more closely aligned with speech (Fabio)
- [ ] going opensource (Fabio)
    - [x] models (we have llama3.2 as llm and piper as tts for now)
    - [ ] infrastructure (remove dependency from Daily)
- [ ] more structured conversation flows (pipecat flows) (Bruce)
- [ ] summarizing sessions, saving (we save already the audio, but would be great if we also save transcripts and video). RAG model (Bruce)

- [ ] understanding emotions, speech emotion detection
- [ ] speaker verification (multi-user sessions) - is it just about looking for a good model that can do it?
- [ ] cleaning up the code

## Notes:
- https://www.sesame.com/research/crossing_the_uncanny_valley_of_voice#demo
- https://www.linkedin.com/posts/andrewyng_the-voice-stack-is-improving-rapidly-systems-activity-7300912040959778818-B_hc/
- https://www.linkedin.com/feed/update/urn:li:activity:7306294278815633408/
- https://github.com/Berkeley-Speech-Group/Speech-Articulatory-Coding
