# GPU and Non-GPU Deployment Plan

## Goal

Allow Riverst to deploy in either of these modes without code changes:

- [x] CPU / non-GPU deployment
- [x] GPU-capable deployment

## Findings

After reviewing the repository, no server function strictly requires a GPU to execute. The GPU-sensitive paths are all local-model or local-inference paths where acceleration improves latency or throughput.

### GPU-sensitive functions and classes

- [x] `src/server/bot/utils/device_utils.py:get_best_device`
- [x] `src/server/bot/processors/audio/resampling_helper.py:AudioResamplingHelper._torchaudio_resample`
- [x] `src/server/bot/processors/speech/lipsync_processor.py:predict_phonemes_from_waveform`
- [x] `src/server/bot/processors/speech/lipsync_processor.py:load_cupe_model`
- [x] `src/server/bot/processors/speech/lipsync_processor.py:LipsyncProcessor.__init__`
- [x] `src/server/bot/processors/speech/lipsync_processor.py:LipsyncProcessor._warm_up`
- [x] `src/server/bot/processors/speech/lipsync_processor.py:LipsyncProcessor._preprocess_audio`
- [x] `src/server/bot/processors/speech/lipsync_processor.py:LipsyncProcessor._run_lipsync`
- [x] `src/server/bot/core/component_factory.py:BotComponentFactory._build_stt_service`
- [x] `src/server/bot/core/component_factory.py:BotComponentFactory._build_tts_service`
- [x] `src/server/bot/processors/video/processor.py:VideoProcessor.__init__`
- [x] `src/server/bot/processors/video/processor.py:VideoProcessor._run_pose_in_background`
- [x] `src/server/bot/processors/audio/analyzer.py:AudioAnalyzer.analyze_audio`

## Decisions

- [x] Add a runtime device policy via `RIVERST_COMPUTE_DEVICE=auto|cpu`
- [x] Add a Docker build target via `RIVERST_DEPLOYMENT_TARGET=cpu|gpu`
- [x] Add a GPU compose override for `gpus: all`
- [x] Keep CPU deployments functional when ONNX export dependencies are unavailable
- [x] Add a small test suite for the runtime device policy

## Implementation Notes

- CPU deployments now default to `requirements.txt`
- GPU deployments install `requirements.gpu.txt`
- Runtime device selection is centralized in `bot.utils.device_utils`
- Pose processing falls back to the PyTorch YOLO model if ONNX export is unavailable
