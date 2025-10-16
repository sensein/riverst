# Lip sync resources

This file collects references and tools for implementing lip sync.

- [overview-of-avatar-creation+animation-tools-options.pdf](overview-of-avatar-creation+animation-tools-options.pdf)
  Literature review of existing methods to create and animate avatars.

- [phoneme_viseme_map.json](phoneme_viseme_map.json)
  Mapping between phonemes and visemes following Microsoft’s [Speech SDK viseme mapping](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/how-to-speech-synthesis-viseme?tabs=visemeid&pivots=programming-language-python).

---

## More resources

### General animation libraries and docs
- [Ready Player Me Animation library](https://github.com/readyplayerme/animation-library/)
- [Apple ARKit morph targets](https://docs.readyplayer.me/ready-player-me/api-reference/avatars/morph-targets/apple-arkit)
- [Oculus OVR LipSync morph targets](https://docs.readyplayer.me/ready-player-me/api-reference/avatars/morph-targets/oculus-ovr-libsync)
- [Video tutorial: Face animations from audio](https://readyplayer.me/developers/video-tutorials/face-animations-generated-from-audio-with-oculus-lipsync)


### Lip sync animation libraries and models
- [MuseTalk](https://github.com/TMElyralab/MuseTalk?tab=readme-ov-file)
- [SadTalker](https://github.com/OpenTalker/SadTalker)
- [GeneFace](https://github.com/yerfor/GeneFace)
- [ProMoNet](https://github.com/maxrmorrison/promonet)


### Time-stamped phoneme extraction libraries and models
- [PPGs](https://github.com/interactiveaudiolab/ppgs)
- [CUPE-2i](https://huggingface.co/Tabahi/CUPE-2i)
- [wav2vec2-ljspeech-gruut](https://huggingface.co/bookbot/wav2vec2-ljspeech-gruut)
- [Berkeley Speech Group: Speech-Articulatory-Coding](https://github.com/Berkeley-Speech-Group/Speech-Articulatory-Coding) — this one actually does timestamped articulatory coding.

### Commercial / Cloud lip sync solutions
- [NVIDIA Audio2Face](https://build.nvidia.com/nvidia/audio2face-3d/deploy)
- [Mascot Bot](https://www.mascot.bot/#features)
- [Gooey AI](https://gooey.ai/)


### Other References
- [DAGAN (paper page)](https://harlanhong.github.io/publications/dagan.html)
- [Lip Sync Application (Medium article)](https://medium.com/@phototech/lip-sync-application-f529ae7e59ca)
- [LipSync.js (volume-based example)](https://github.com/webaverse-studios/CharacterCreator/blob/stable/src/library/lipsync.js)
- [OpenAI community discussion](https://community.openai.com/t/how-to-implement-real-time-lip-sync-of-avatar-chatbot-powered-by-gpt/534035/10)
- [Pipecat issue #1516](https://github.com/pipecat-ai/pipecat/issues/1516)
- [Colab demo](https://colab.research.google.com/drive/1eFEqb8Tbq9DlSrZt9-KbGwFSTAHQP_Uz#scrollTo=CMN7o6OgBcNL)
- [Optimum issue #2250](https://github.com/huggingface/optimum/issues/2250)
