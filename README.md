# riverst
Just the coolest multimodal avatar interface 

## Project Structure

```
src/
├── server/              # Bot server implementation
│   ├── bot-openai.py    # OpenAI bot implementation
│   ├── bot-openai_realtime_beta.py    # OpenAI Realtime API bot implementation
│   ├── bot-gemini.py    # Gemini bot implementation
│   ├── runner.py        # Server runner utilities
│   ├── server.py        # FastAPI server
│   └── requirements.txt
└── client/              # Client implementations
    ├── prebuilt/        # Pipecat Prebuilt client (good for some testing)
    └── react/           # React client
```

## Important Note

The code has a client-server architecture. You find instructions on how to run the client and the server in the respective folders. The bot server must be running for any of the client implementations to work. Start the server first before trying any of the client apps.

## Requirements

- Python 3.10+
- Node.js 16+ (for React implementations)
- 3rd party services API KEYs
- Modern web browser with WebRTC support


## Short-term TODO:
- [] [CRITICAL] Figure out how to integrate "Ready player me" for animating the avatar (in their current implementation, all animations are generated on the server and video frames are streamed to the client (synced with the audio). IF we follow this approach, in the future, we can easily switch to alternative avatar services once they integrate some more - they have some but are all very expensive). Also, we can make the avatar cross-platform more easily (react, android, ios, ...), which is not a requirement for now but a cool nice-to-have. 
Useful resources include:
    - https://docs.pipecat.ai/server/services/video/simli
    - https://docs.pipecat.ai/server/services/video/tavus
    - Here is how these folks integrated heygen for avatar video animation generation (which is not directly integrated in pipecat) and may be worth taking inspiration for our Ready player me integration: https://github.com/HeyGen-Official/pipecat-realtime-demo/blob/main/heygen_video_service.py 
    - https://docs.readyplayer.me/ready-player-me/api-reference/avatars/morph-targets/apple-arkit
    - https://docs.readyplayer.me/ready-player-me/api-reference/avatars/morph-targets/oculus-ovr-libsync
    - https://readyplayer.me/developers/video-tutorials/face-animations-generated-from-audio-with-oculus-lipsync
    - https://community.openai.com/t/how-to-implement-real-time-lip-sync-of-avatar-chatbot-powered-by-gpt/534035/10
- [] Experiment and eventually integrate pipecat flows (https://github.com/pipecat-ai/pipecat-flows)
- [] [LOW PRIORITY FOR NOW] Make the server code more modular (see https://docs.pipecat.ai/guides/features/openai-audio-models-and-apis as an example) 
- [] [LOWER PRIORITY FOR NOW] Integrate multimodal models (including video). I have tried with Gemini multimodal realtime API is and CRAZY!!!!! The code we have should be a good start for this and we can also follow this guide (https://docs.pipecat.ai/guides/features/gemini-multimodal-live)
- [] animations (https://readyplayerme.github.io/visage/?path=/docs/components-avatar--docs)
    - [] play with camera settings
    - [] add some more body animations
    - [] [CRITICAL] VISEMES
    - [] play with M and F animations



## Notes:
- https://www.sesame.com/research/crossing_the_uncanny_valley_of_voice#demo
- https://www.linkedin.com/posts/andrewyng_the-voice-stack-is-improving-rapidly-systems-activity-7300912040959778818-B_hc/
- https://www.linkedin.com/feed/update/urn:li:activity:7306294278815633408/
- https://github.com/Berkeley-Speech-Group/Speech-Articulatory-Coding
