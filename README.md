# riverst
Just the coolest multimodal avatar interface 

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
- [x] add some more animations (Fabio)
- [x] incorporating video (with google gemini, but honestly doesn't work very well) (Fabio)
- [x] Getting visemes more closely aligned with speech (Fabio)
- [x] allowing opensource models (we have llama3.2 as llm and piper as tts that work decenlty for now) (Fabio)
- [x] cleaning up the code and making it more modular (Fabio)
- [x] remove dependency from Daily
- [x] DO BETTER LIP SYNC (Fabio - it may be further improved, but that's more for the future)
- [x] Integrate YOLO with onnx to make inference faster (Fabio)
- [x] more structured conversation flows (pipecat flows) (Bruce)
- [x] Integrate the advanced flows for the KIVA activities (Bruce)
- [x] Saving the transcript and the audio clips (Fabio)
- [ ] Enabling recovering the session from the transcript (Bruce)
- [ ] Saving the video (Bruce)
- [ ] cleaning animations (Fabio: I have cleaned them a bit but they are still not good if you play them multiple times...)
- [ ] [BUG+HELP WANTED] there is something off with UserTranscript (it seems that the event is received twice on the client)
- [ ] Understand how to communicate video-based emotion recognition (+ pose estimation?) to the llm (ethical and technical questions)
- [ ] speech emotion recognition (ethical and technical questions)
- [ ] record and add more animations (for expressivity!!!): https://github.com/readyplayerme/animation-library/tree/master/masculine/fbx/idle
- [ ] handle multi-users:
    - [ ] speaker verification (multi-user sessions) - we should try with diart
- [ ] create an error page for the web app
- [ ] add and structure a bit more avatar creation and voice selection (Fabio)
- [ ] handle the end of the conversation on the client side
- [ ] handle conversation memory
- [ ] add session history page
- [ ] add the user_id to the history of the session
- [ ] add senselab analysis afterwards
- [ ] clean the server main folder (moving models to the assets folder)
- [ ] improve the UI and UX for building a flow!!
- [ ] multilanguage (or at least non english) experiences
- [ ] add a language identification tool
- [ ] make sure the llm calls only existings tools (especially helpful with llama3.2)
- [ ] transcription problem!!

########## FUTURE WORK ##########
- TranscriptionLogger: https://github.com/pipecat-ai/pipecat/blob/09ff836ef6dec7070717a03111dc61f252e93814/examples/foundational/13-whisper-transcription.py
 - https://github.com/pipecat-ai/pipecat/blob/09ff836ef6dec7070717a03111dc61f252e93814/examples/foundational/20a-persistent-context-openai.py
 - https://github.com/pipecat-ai/pipecat/blob/09ff836ef6dec7070717a03111dc61f252e93814/examples/foundational/20b-persistent-context-openai-realtime.py
 - https://github.com/pipecat-ai/pipecat/blob/09ff836ef6dec7070717a03111dc61f252e93814/examples/foundational/22-natural-conversation.py

- ALTERNATIVE SMART TURN DETECTION? 
    - https://github.com/pipecat-ai/pipecat/blob/09ff836ef6dec7070717a03111dc61f252e93814/examples/foundational/22b-natural-conversation-proposal.py
    - https://github.com/pipecat-ai/pipecat/blob/09ff836ef6dec7070717a03111dc61f252e93814/examples/foundational/22c-natural-conversation-mixed-llms.py
- RETRIEVAL AUGMENTED GENERATION
    # https://github.com/pipecat-ai/pipecat/blob/09ff836ef6dec7070717a03111dc61f252e93814/examples/foundational/33-gemini-rag.py
- MEMORY (long-term)

## Notes:
- https://www.sesame.com/research/crossing_the_uncanny_valley_of_voice#demo
- https://www.linkedin.com/posts/andrewyng_the-voice-stack-is-improving-rapidly-systems-activity-7300912040959778818-B_hc/
- https://www.linkedin.com/feed/update/urn:li:activity:7306294278815633408/
- https://github.com/Berkeley-Speech-Group/Speech-Articulatory-Coding
