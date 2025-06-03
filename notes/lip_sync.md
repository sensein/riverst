## Lip sync notes and resources

- https://github.com/readyplayerme/animation-library/
- https://github.com/TMElyralab/MuseTalk?tab=readme-ov-file
- https://harlanhong.github.io/publications/dagan.html
- https://github.com/OpenTalker/SadTalker
- https://github.com/yerfor/GeneFace
- https://medium.com/@phototech/lip-sync-application-f529ae7e59ca
- https://github.com/webaverse-studios/CharacterCreator/blob/stable/src/library/lipsync.js (volume based)
- https://build.nvidia.com/nvidia/audio2face-3d/deploy
- https://www.mascot.bot/#features (commercial solution. Note: see pricing!!!)
- https://github.com/maxrmorrison/promonet
- https://github.com/interactiveaudiolab/ppgs
- https://gooey.ai/
- https://github.com/huggingface/optimum/issues/2250 (related issue i opened on optimum)
- https://docs.readyplayer.me/ready-player-me/api-reference/avatars/morph-targets/apple-arkit
- https://docs.readyplayer.me/ready-player-me/api-reference/avatars/morph-targets/oculus-ovr-libsync
- https://readyplayer.me/developers/video-tutorials/face-animations-generated-from-audio-with-oculus-lipsync
- https://community.openai.com/t/how-to-implement-real-time-lip-sync-of-avatar-chatbot-powered-by-gpt/534035/10
- https://github.com/pipecat-ai/pipecat/issues/1516

- For Apple Silicon or Mac, PyTorch with MPS is currently the fastest and most reliable option for real-time inference.
- ONNX Runtime is only advantageous on CPU or with CUDA (NVIDIA GPU).
- There is no practical way to combine ONNX optimizations with PyTorch MPS, nor to use ONNX Runtime with MPS for this use case.

## Code:

- optimum-cli export onnx --model bookbot/wav2vec2-ljspeech-gruut onnx-wav2vec2/

- 

from optimum.onnxruntime import ORTModelForCTC
import onnxruntime as ort
from transformers import AutoProcessor, pipeline as transformers_pipeline
import numpy as np
import time
import torch

processor = AutoProcessor.from_pretrained("bookbot/wav2vec2-ljspeech-gruut")
model = ORTModelForCTC.from_pretrained(
    "onnx-wav2vec2/",
    file_name="model.onnx"
)

model.main_input_name = "input_values" # Patch for pipeline compatibility
asr_pipeline = transformers_pipeline(
    "automatic-speech-recognition",
    model=model,
    tokenizer=processor.tokenizer,
    feature_extractor=processor.feature_extractor,
)
asr_pipeline(dummy_audio, return_timestamps="char")