# TODO: how to sync video info???

import os
import sys

import cv2
import numpy as np
from dotenv import load_dotenv
from loguru import logger

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import Frame, InputImageRawFrame, OutputImageRawFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.processors.frameworks.rtvi import RTVIConfig, RTVIObserver, RTVIProcessor, RTVIServerMessageFrame
from pipecat.services.gemini_multimodal_live import GeminiMultimodalLiveLLMService
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.network.small_webrtc import SmallWebRTCTransport

from pipecat.processors.user_idle_processor import UserIdleProcessor
import aiofiles
from pipecat.processors.audio.audio_buffer_processor import AudioBufferProcessor
from pipecat.pipeline.parallel_pipeline import ParallelPipeline
from pipecat.services.openai.stt import OpenAISTTService
from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.frames.frames import EndFrame, LLMMessagesFrame, TTSSpeakFrame

from deepface import DeepFace
from ultralytics import YOLO
from ultralytics.utils import LOGGER
import logging
LOGGER.setLevel(logging.WARNING)

from pipecat.processors.transcript_processor import TranscriptProcessor

from pipecat.audio.filters.noisereduce_filter import NoisereduceFilter
import io
import wave
import datetime
import time
import asyncio
import uuid
import torch
from transformers import pipeline as transformers_pipeline
import json
from pipecat.services.openai import OpenAILLMService, OpenAITTSService
from pipecat.services.openai_realtime_beta import (
    InputAudioNoiseReduction,
    InputAudioTranscription,
    OpenAIRealtimeBetaLLMService,
    SemanticTurnDetection,
    SessionProperties,
)
from pipecat.services.ollama import OLLamaLLMService
from pipecat.services.piper import PiperTTSService
import aiohttp
from pipecat.services.whisper.stt import WhisperSTTService, Model
from pipecat.frames.frames import TranscriptionMessage, TranscriptionUpdateFrame

from senselab.audio.data_structures import Audio
from senselab.audio.tasks.features_extraction.api import extract_features_from_audios
from senselab.audio.tasks.preprocessing import downmix_audios_to_mono, resample_audios
from senselab.audio.tasks.speaker_embeddings import extract_speaker_embeddings_from_audios
from senselab.utils.data_structures import DeviceType, SpeechBrainModel

from transformers import Wav2Vec2Processor
from transformers.models.wav2vec2.modeling_wav2vec2 import Wav2Vec2Model, Wav2Vec2PreTrainedModel
import torch.nn as nn
import torch

class RegressionHead(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.dense = nn.Linear(config.hidden_size, config.hidden_size)
        self.dropout = nn.Dropout(config.final_dropout)
        self.out_proj = nn.Linear(config.hidden_size, config.num_labels)

    def forward(self, features, **kwargs):
        x = self.dropout(features)
        x = self.dense(x)
        x = torch.tanh(x)
        x = self.dropout(x)
        return self.out_proj(x)

class EmotionModel(Wav2Vec2PreTrainedModel):
    def __init__(self, config):
        super().__init__(config)
        self.config = config
        self.wav2vec2 = Wav2Vec2Model(config)
        self.classifier = RegressionHead(config)
        self.init_weights()

    def forward(self, input_values):
        outputs = self.wav2vec2(input_values)
        hidden_states = outputs[0]
        pooled = torch.mean(hidden_states, dim=1)
        logits = self.classifier(pooled)
        return pooled, logits


def load_emotion_model(model_name='audeering/wav2vec2-large-robust-12-ft-emotion-msp-dim', device='cpu'):
    processor = Wav2Vec2Processor.from_pretrained(model_name)
    model = EmotionModel.from_pretrained(model_name).to(device)
    return processor, model


import numpy as np

def extract_emotions(audios, output_files, model, processor, device='cpu'):
    results = []

    for audio in audios:
        waveform = audio.waveform  # Expected to be a 1D NumPy array
        sr = audio.sampling_rate

        processed = processor(waveform, sampling_rate=sr, return_tensors="pt", padding=True)
        input_values = processed['input_values'].to(device)

        with torch.no_grad():
            _, logits = model(input_values)
            scores = logits.cpu().numpy()[0].tolist()

        results.append({
            "arousal": scores[0],
            "dominance": scores[1],
            "valence": scores[2]
        })

    return results  # optionally write to output_files if needed


load_dotenv(override=True)

from typing import Optional, List

def tensor_to_serializable(obj):
    if isinstance(obj, torch.Tensor):
        return obj.detach().cpu().tolist()
    elif isinstance(obj, dict):
        return {k: tensor_to_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [tensor_to_serializable(v) for v in obj]
    return obj


class TranscriptHandler:
    """Handles real-time transcript processing and output.

    Maintains a list of conversation messages and outputs them either to a log
    or to a file as they are received. Each message includes its timestamp and role.

    Attributes:
        messages: List of all processed transcript messages
        output_file: Optional path to file where transcript is saved. If None, outputs to log only.
    
    # TODO: doesn't seem to work well with openai_realtime_beta!!!
    """

    def __init__(self, output_file: Optional[str] = None):
        """Initialize handler with optional file output.

        Args:
            output_file: Path to output file. If None, outputs to log only.
        """
        self.messages: List[dict] = []
        self.output_file: Optional[str] = output_file
        # Step 4: Emotion recognition
        self.processor, self.emotion_model = load_emotion_model(device="cpu")

        logger.debug(
            f"TranscriptHandler initialized {'with output_file=' + output_file if output_file else 'with log output only'}"
        )

    async def save_messages(self):
        """Save messages"""
        if self.output_file:
            try:
                os.makedirs(os.path.dirname(self.output_file), exist_ok=True)
                async with aiofiles.open(self.output_file, "w", encoding="utf-8") as f:
                    await f.write(json.dumps(self.messages, indent=2))
            except Exception as e:
                logger.error(f"Error saving transcript message to file: {e}")

    async def on_transcript_update(
        self, processor: TranscriptProcessor, frame: TranscriptionUpdateFrame
    ):
        """Handle new transcript messages.

        Args:
            processor: The TranscriptProcessor that emitted the update
            frame: TranscriptionUpdateFrame containing new messages
        """
        logger.debug(f"Received transcript update with {len(frame.messages)} new messages")

        for msg in frame.messages:
            updated = False
            for existing_msg in reversed(self.messages):
                if (
                    existing_msg["role"] == msg.role
                    and "audio_file" in existing_msg
                    and not existing_msg.get("content")
                ):
                    existing_msg["content"] = msg.content
                    existing_msg["timestamp"] = msg.timestamp
                    logger.info(f"Updated message with transcript: {existing_msg}")
                    updated = True
                    break

            if not updated:
                data = {
                    "timestamp": msg.timestamp if msg.timestamp else None,
                    "role": msg.role,
                    "content": msg.content,
                }
                self.messages.append(data)
                logger.info(f"Transcript: {data}")

        await self.save_messages()

    async def attach_audio_to_last_message(self, role: str, 
                                           audio_file: str):
        """Attach an audio file path to the most recent message of the given role that lacks one."""
        print("attach_audio_to_last_message: ", role, audio_file)
        for msg in reversed(self.messages):
            if msg["role"] == role and "audio_file" not in msg:
                msg["audio_file"] = audio_file
                logger.debug(f"Attached audio {audio_file} to {role} message: {msg.get('content')}")
                await self.save_messages()
                return

        # No suitable message found; append a new one with only audio and role
        new_msg = {"role": role, "audio_file": audio_file}
        self.messages.append(new_msg)
        logger.debug(f"Appended new audio-only message: {new_msg}")
        await self.save_messages()
        asyncio.create_task(self.process_audio_background(audio_file))

    async def process_audio_background(self, filepath: str):
        try:
            print("Processing audio in background: ", filepath)

            loop = asyncio.get_running_loop()

            def run_all_blocking_operations():
                audio = Audio(filepath=filepath)
                audio = downmix_audios_to_mono([audio])[0]
                audios = resample_audios([audio], 16000)

                acoustic_feats = extract_features_from_audios(
                    audios=audios,
                    opensmile=True,
                    parselmouth=True,
                    torchaudio=False,
                    torchaudio_squim=False
                )

                return {
                    "features": acoustic_feats[0],
                }

            result = await loop.run_in_executor(None, run_all_blocking_operations)

            for msg in reversed(self.messages):
                if msg.get("audio_file") == filepath:
                    msg["features"] = tensor_to_serializable(result["features"])
                    logger.debug(f"Attached audio processing results to message: {msg}")
                    await self.save_messages()
                    break

        except Exception as e:
            logger.error(f"Error in background audio processing for {filepath}: {e}")


def build_llm_and_tts(bot_type: str, session: aiohttp.ClientSession, tools = None):
    """Construct LLM and TTS services based on configuration.

    Args:
        bot_type (str): Selected bot backend implementation.
        session (aiohttp.ClientSession): HTTP session for API communication.

    Returns:
        tuple: (llm, tts)
    """
    llm, tts, stt = None, None, None
    bot_type = bot_type.lower().strip()

    if bot_type == "openai":
        stt = OpenAISTTService(
            api_key=os.getenv("OPENAI_API_KEY"),
            model="gpt-4o-transcribe",
            audio_passthrough=True,  # This is fundamental for audiobuffer to work
        )
        llm = OpenAILLMService(api_key=os.getenv("OPENAI_API_KEY"), model="gpt-4o")
        tts = OpenAITTSService(voice="nova", model="gpt-4o-mini-tts")

    elif bot_type == "openai_realtime_beta":

        session_properties = SessionProperties(
            input_audio_transcription=InputAudioTranscription(),
            # Set openai TurnDetection parameters. Not setting this at all will turn it
            # on by default
            turn_detection=SemanticTurnDetection(),
            # Or set to False to disable openai turn detection and use transport VAD
            # turn_detection=False,
            input_audio_noise_reduction=InputAudioNoiseReduction(type="near_field"),
            # tools=tools,
            instructions=SYSTEM_INSTRUCTION,
        )

        llm = OpenAIRealtimeBetaLLMService(
            api_key=os.getenv("OPENAI_API_KEY"),
            model="gpt-4o-realtime-preview-2024-12-17",
            session_properties=session_properties,
            start_audio_paused=False,
            send_transcription_frames=True,
        )

    elif bot_type == "gemini":
        llm = GeminiMultimodalLiveLLMService(
            api_key=os.getenv("GOOGLE_API_KEY"),
            voice_id="Aoede",
            transcribe_user_audio=True,
            transcribe_model_audio=True,
            system_instruction=SYSTEM_INSTRUCTION,
            tools=tools
        )
        # sad story for now
        # https://github.com/pipecat-ai/pipecat-flows/issues/66
        # TODO: make sure to integate this when they implement it

    elif bot_type == "opensource":
        stt = WhisperSTTService(
            audio_passthrough=True  # This is fundamental for audiobuffer to work
        )
        llm = OLLamaLLMService(model="llama3.2")
        tts = PiperTTSService(base_url="http://localhost:5001/", aiohttp_session=session)
        # TODO: check if this works now!!!

    else:
        raise ValueError(f"Invalid BOT_IMPLEMENTATION: {bot_type}")

    return llm, tts, stt


async def save_audio_file(audio: bytes, filename: str, sample_rate: int, num_channels: int):
    """Save audio data to a WAV file.

    Args:
        audio (bytes): Audio byte stream.
        filename (str): Output filename.
        sample_rate (int): Audio sample rate.
        num_channels (int): Number of audio channels.
    """
    if len(audio) > 0:
        with io.BytesIO() as buffer:
            with wave.open(buffer, "wb") as wf:
                wf.setsampwidth(2)
                wf.setnchannels(num_channels)
                wf.setframerate(sample_rate)
                wf.writeframes(audio)
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            async with aiofiles.open(filename, "wb") as file:
                await file.write(buffer.getvalue())
        logger.info(f"Audio saved to {filename}")
    else:
        print("No audio data to save")

class PassthroughProcessor(FrameProcessor):
    def __init__(self, camera_out_width: int, camera_out_height: int):
        super().__init__()
        self._camera_out_width = camera_out_width
        self._camera_out_height = camera_out_height

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, InputImageRawFrame):
            img = np.frombuffer(frame.image, dtype=np.uint8).reshape(
                (frame.size[1], frame.size[0], 3)
            )

            desired_size = (self._camera_out_width, self._camera_out_height)
            if frame.size != desired_size:
                resized_image = cv2.resize(img, desired_size)
                output_frame = OutputImageRawFrame(resized_image.tobytes(), desired_size, frame.format)
            else:
                output_frame = OutputImageRawFrame(image=img.tobytes(), size=frame.size, format=frame.format)

            await self.push_frame(output_frame)
        else:
            await self.push_frame(frame, direction)

class VideoProcessor(FrameProcessor):
    def __init__(self, camera_out_width: int, camera_out_height: int, 
                 context = None, context_aggregator=None,
                 every_n_frames: int = 5, 
                 enable_pose=False, enable_face=False):
        super().__init__()
        # TODO: IF SUPPORTED, SEND VIDEO TO THE LLM!!!! (GEMINI)
        self.context = context
        self.context_aggregator = context_aggregator

        self._camera_out_width = camera_out_width
        self._camera_out_height = camera_out_height
        self.every_n_frames = every_n_frames
        self.enable_pose = enable_pose
        self.enable_face = enable_face
        self.frame_count = 0

        self.device = 'cuda' if hasattr(torch, "cuda") and torch.cuda.is_available() else 'cpu'

        if self.enable_pose:
            print("Initializing yolo...")
            yolo_model = YOLO("yolo11n-pose.pt")

            # Export the model to ONNX format
            yolo_model.export(format="onnx")  # creates 'yolo11n.onnx'

            # Load the exported ONNX model
            self.pose_inferencer = YOLO("yolo11n-pose.onnx")

            dummy_img = np.random.randint(0, 255, (camera_out_height, camera_out_width, 3), dtype=np.uint8)
            _ = self.pose_inferencer(dummy_img)
            print("yolo warmed up!: ")

        if self.enable_face:
            print("Warming up DeepFace...")
            dummy_img = np.random.randint(0, 255, (camera_out_height, camera_out_width, 3), dtype=np.uint8)
            _ = DeepFace.analyze(img_path=dummy_img, actions=['emotion'], enforce_detection=False)
            print("DeepFace warmed up!")

        self._pose_lock = asyncio.Lock()
        self._deepface_lock = asyncio.Lock()

        self.last_pose_results = None
        self.last_face_results = None

        self.previous_emotion = None

    async def _run_pose_in_background(self, img):
        if self._pose_lock.locked():
            return
        async with self._pose_lock:
            loop = asyncio.get_running_loop()
            try:
                results = await loop.run_in_executor(None, lambda: self.pose_inferencer(img))
                if results:
                    img_with_pose = results[0].plot()
                    self.last_pose_results = cv2.cvtColor(img_with_pose, cv2.COLOR_BGR2RGB)
                else:
                    self.last_pose_results = None
            except Exception as e:
                logger.warning(f"[yolo Error] {e}")
                self.last_pose_results = None

    async def _run_deepface_in_background(self, img):
        if self._deepface_lock.locked():
            return
        async with self._deepface_lock:
            loop = asyncio.get_running_loop()
            try:
                results = await loop.run_in_executor(None, lambda: DeepFace.analyze(
                    img_path=img,
                    actions=['emotion'], # ['age', 'gender', 'race', 'emotion'],
                    enforce_detection=False
                ))
                if isinstance(results, list):
                    self.last_face_results = results[0]
                    # Get the first result if it's a list (TODO: manage multiple faces)
                    # print("last_face_results: ", self.last_face_results)
            except Exception as e:
                logger.warning(f"[DeepFace Error] {e}")
                self.last_face_results = None
        # await self._update_emotion_to_llm()  
        # # TODO: uncomment this if you want to test the emotion to LLM
        # it is not supported by openai_realtime_beta yet
        # gemini doesn't seem to receive the info either

    def _overlay_pose_and_face(self, img):
        """Synchronously overlay pose and face info on the image."""
        output_img = img.copy()

        if self.enable_pose and self.last_pose_results is not None:
            try:
                if isinstance(self.last_pose_results, np.ndarray):
                    output_img = self.last_pose_results.copy()
                else:
                    logger.warning("[Overlay Pose Warning] last_pose_results is not a valid numpy array.")
            except Exception as e:
                logger.warning(f"[Overlay Pose Error] {e}")

        if self.enable_face and self.last_face_results:
            try:
                for face in self.last_face_results if isinstance(self.last_face_results, list) else [self.last_face_results]:
                    '''
                    label = (f"Age: {face['age']} "
                             f"Gender: {face['gender']} "
                             f"Race: {face['dominant_race']} "
                             f"Emotion: {face['dominant_emotion']}")
                    '''
                    label = f"Emotion: {face['dominant_emotion']}"
                    if isinstance(output_img, np.ndarray):
                        cv2.putText(output_img, label, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1)
                    else:
                        logger.warning("[Overlay Face Warning] output_img is not a valid numpy array, skipping putText.")
            except Exception as e:
                logger.warning(f"[Overlay Face Error] {e}")

        return output_img

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, InputImageRawFrame):
            if not self.enable_pose and not self.enable_face:
                await self.push_frame(frame, direction)
                output_frame = OutputImageRawFrame(frame.image, frame.size, frame.format)
                await self.push_frame(output_frame)
                return
            
            self.frame_count += 1
            try:
                img = np.frombuffer(frame.image, dtype=np.uint8).reshape((frame.size[1], frame.size[0], 3))
            except Exception as e:
                logger.warning(f"Error decoding input image: {e}")
                return

            # If it's time to update the predictions, run them asynchronously
            if self.frame_count % self.every_n_frames == 0:
                if self.enable_pose:
                    asyncio.create_task(self._run_pose_in_background(img))
                if self.enable_face:
                    asyncio.create_task(self._run_deepface_in_background(img))

            # ALWAYS overlay the *last available* pose and face results
            output_img = self._overlay_pose_and_face(img)

            desired_size = (self._camera_out_width, self._camera_out_height)
            if isinstance(output_img, np.ndarray):
                if frame.size != desired_size:
                    output_img = cv2.resize(output_img, desired_size)
            else:
                logger.warning("[Warning] output_img is not a valid numpy array after overlay. Skipping resize.")
                return

            output_img = cv2.cvtColor(output_img, cv2.COLOR_BGR2RGB)
            output_frame = OutputImageRawFrame(output_img.tobytes(), desired_size, frame.format)
            await self.push_frame(output_frame)
        else:
            await self.push_frame(frame, direction)

    '''
    async def _update_emotion_to_llm(self):
        """Send the detected emotion to the LLM context if it changed."""
        if self.last_face_results and isinstance(self.last_face_results, dict):
            emotion = self.last_face_results.get('dominant_emotion')
            if emotion and emotion != self.previous_emotion:
                self.previous_emotion = emotion
                if self.context and self.context_aggregator:
                    self.context.add_message({
                        "role": "system",
                        "content": f"The user appears {emotion} based on facial expression."
                    })
                    await self.queue_frame(self.context_aggregator.assistant().get_context_frame())
    '''

SYSTEM_INSTRUCTION = f"""
"You are KIVA, a friendly, helpful robot.

Your goal is to demonstrate your vocabulary teching skills in a succinct way.

Your output will be converted to audio so don't include special characters in your answers.

Respond to what the user said in a creative and helpful way. Keep your responses brief. One or two sentences at most.

When you want to congratulate, sometimes you can dance.

When the user joins the room say hi and (sometimes) wave with the hand.

When you don't know something, you can do the i don't know animation.

Start with a friendly greeting and ask how you can help the user.
"""


async def run_bot(webrtc_connection):

    phoneme_viseme_map_file = "./assets/phoneme_viseme_map.json"
    with open(phoneme_viseme_map_file, "r") as f:
        phoneme_viseme_map = json.load(f)

    if torch.cuda.is_available():
        device = torch.device("cuda")
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device = torch.device("mps")
    else:
        device = torch.device("cpu")

    asr_pipeline = transformers_pipeline(
        "automatic-speech-recognition",
        model="bookbot/wav2vec2-ljspeech-gruut",
        device=device,
        torch_dtype=torch.float16
    )

    print("ASR pipeline loaded on device:", device)
    dummy_audio = np.random.rand(16000).astype(np.int16) * 2 - 1  # values in [-1, 1]
    _ = asr_pipeline(dummy_audio)
    print("ASR pipeline warmed up")

    def process_visemes(audio_bytes, sample_rate, num_channels, phoneme_viseme_map):
        def clean_visemes(visemes_durations, silence_viseme=0, silence_threshold=0.2, general_threshold=0.05):
            cleaned = []
            skip_next_unwanted_duration = 0.0

            for _, current in enumerate(visemes_durations):
                vis = current["visemes"]
                dur = current["duration"]

                # Merge skipped durations
                if skip_next_unwanted_duration > 0:
                    dur += skip_next_unwanted_duration

                # Short viseme or silence
                if (vis == [silence_viseme] and dur < silence_threshold) or dur < general_threshold:
                    # Add the pause duration or short viseme duration to next non-silence viseme
                    skip_next_unwanted_duration += dur
                    continue

                if skip_next_unwanted_duration > 0:
                    skip_next_unwanted_duration = 0.0

                cleaned.append({
                    "visemes": vis,
                    "duration": round(dur, 6)
                })

            return cleaned

        try:
            waveform = np.frombuffer(audio_bytes, dtype=np.int16)

            with torch.inference_mode():
                phonemes = asr_pipeline(waveform.squeeze(), return_timestamps="char")

            visemes_durations = [
                {
                    "visemes": phoneme_viseme_map.get(chunk["text"], []),
                    "duration": round(chunk["timestamp"][1] - chunk["timestamp"][0], 2)
                }
                for chunk in phonemes["chunks"]
            ]

            cleaned_visemes_durations = clean_visemes(visemes_durations)
            # print("cleaned_visemes_durations: ", cleaned_visemes_durations)
            return cleaned_visemes_durations
        except Exception as e:
            print(f"Error processing audio: {e}")
            return None

    session_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + str(uuid.uuid4())[:8]
    session_dir = f"recordings/{session_id}"
    os.makedirs(session_dir, exist_ok=True)


    transport_params = TransportParams(
        camera_in_enabled=True,
        camera_out_enabled=True,
        camera_out_is_live=True,
        camera_out_width=640,
        camera_out_height=320,
        audio_in_enabled=True,
        audio_out_enabled=True,
        audio_in_filter=NoisereduceFilter(),

        vad_enabled=True,
        vad_analyzer=SileroVADAnalyzer(),
        vad_audio_passthrough=True,
        audio_out_10ms_chunks=4,
    )

    pipecat_transport = SmallWebRTCTransport(
        webrtc_connection=webrtc_connection, params=transport_params
    )

    audiobuffer = AudioBufferProcessor(enable_turn_audio=True)
    viseme_audiobuffer = AudioBufferProcessor(enable_turn_audio=True,
                                        sample_rate=16000,
                                        buffer_size=0.2 * 1 * 24000 * 2 # sec * channels * sampling_rate * bit_depth
                                        )

    async with aiohttp.ClientSession() as session:
        bot_impl = os.getenv("BOT_IMPLEMENTATION", "openai")
        print("bot_impl: ", bot_impl)
        tools = ToolsSchema(standard_tools=[
            FunctionSchema(
                name="trigger_animation",
                description="Trigger an avatar animation (only one animation at a time).",
                properties={
                    "animation_id": {"type": "string", 
                                     "enum": ["dance", "wave", "i_dont_know", "none"],
                                     "description": "The animation ID to trigger."},
                    "timing": {"type": "string", 
                               "enum": ["start"],
                               "description": "The timing of the animation."},
                },
                required=["animation_id", "timing"],
            )
        ])

        messages=[
            {
                "role": "system",
                "content": SYSTEM_INSTRUCTION,
            },
            {
                "role": "user",
                "content": "Hello!",
            }
        ]

        context = OpenAILLMContext(
            messages=messages,
            tools=tools
        )

        llm, tts, stt = build_llm_and_tts(bot_impl, session=session, tools=tools)
        context_aggregator = llm.create_context_aggregator(context=context)

        # RTVI events for Pipecat client UI
        rtvi = RTVIProcessor(config=RTVIConfig(config=[]))

        async def handle_animation(function_name, tool_call_id, args, llm, context, result_callback):
            """Trigger avatar animation from LLM function call.

            Args:
                function_name (str): Name of the function.
                tool_call_id (str): Tool call ID.
                args (dict): Arguments for the function.
                llm (BaseLLM): Language model instance.
                context (OpenAILLMContext): LLM context.
                result_callback (Callable): Callback for returning result.
            """
            animation_id = args.get("animation_id", "none")
            timing = args.get("timing", "start")
            print(f"Triggering animation: {animation_id} at {timing}")

            if animation_id != "none":
                frame = RTVIServerMessageFrame(
                    data={
                        "type": "animation-event",
                        "payload": {"animation_id": animation_id, "timing": timing},
                    }
                )
                await rtvi.push_frame(frame)

            await result_callback({"status": "animation_triggered"})

        llm.register_function("trigger_animation", handle_animation)

        async def handle_user_idle(user_idle: UserIdleProcessor, retry_count: int) -> bool:
            if retry_count == 1:
                # First attempt: Gentle reminder
                print("User has been idle for a while. Sending a gentle reminder #1.")
                context.add_message({
                    "role": "system",
                    "content": "The user has been quiet. Politely and briefly ask if they're still there."
                })
                await task.queue_frame(context_aggregator.assistant().get_context_frame())
                return True
            elif retry_count == 2:
                # Second attempt: Direct prompt
                print("User has been idle for a while. Sending a gentle reminder #2.")
                context.add_message({
                    "role": "system",
                    "content": "The user is still inactive. Ask if they'd like to continue our conversation."
                })
                await task.queue_frame(context_aggregator.assistant().get_context_frame())
                return True
            elif retry_count == 3:
                # Third attempt: Direct prompt #2
                print("User has been idle for a while. Ending the conversation.")
                context.add_message({
                    "role": "system",
                    "content": "The user is still inactive. It seems like they are busy right now. Wish them a nice day!"
                })
                await task.queue_frame(context_aggregator.assistant().get_context_frame())
                return True
            else:
                # Fourth attempt: End conversation
                print("User has been idle for a while. Actually ending the conversation.")
                await task.queue_frame(EndFrame())
                return False  # Stop monitoring

        # Create the processor
        user_idle = UserIdleProcessor(
            callback=handle_user_idle,
            timeout=15.0
        )

        # TODO: often lags the audio. i don't know why exactly

        # Create a single transcript processor instance
        transcript = TranscriptProcessor()
        transcript_handler = TranscriptHandler(output_file=f"{session_dir}/transcript.json")

        if tts:
            pipeline = Pipeline(
                [
                    pipecat_transport.input(),
                    rtvi,
                    stt,
                    transcript.user(),
                    context_aggregator.user(),
                    llm,
                    tts,
                    viseme_audiobuffer,
                    VideoProcessor(
                        transport_params.camera_out_width, transport_params.camera_out_height,
                        context, context_aggregator
                    ),  # Sending the video back to the user
                    pipecat_transport.output(),
                    audiobuffer,
                    transcript.assistant(),
                    user_idle,
                    context_aggregator.assistant(),
                ]
            )
        else:
            pipeline = Pipeline(
                [
                    pipecat_transport.input(),
                    rtvi,
                    context_aggregator.user(),
                    VideoProcessor(
                        transport_params.camera_out_width, transport_params.camera_out_height, 
                        context, context_aggregator
                    ),  # Sending the video back to the user
                    llm,  # LLM
                    transcript.user(),
                    viseme_audiobuffer,
                    pipecat_transport.output(),
                    audiobuffer,
                    transcript.assistant(),
                    user_idle,
                    context_aggregator.assistant(),
                ]
            )

        task = PipelineTask(
            pipeline,
            params=PipelineParams(
                allow_interruptions=True,
                enable_heartbeats=True,

                observers=[RTVIObserver(rtvi)],
            ),
        )

        # Register event handler for transcript updates
        @transcript.event_handler("on_transcript_update")
        async def on_transcript_update(processor, frame):
            await transcript_handler.on_transcript_update(processor, frame)

        @audiobuffer.event_handler("on_audio_data")
        async def on_audio_data(_, audio, sr, ch):
            await save_audio_file(audio, f"{session_dir}/session.wav", sr, ch)

        @audiobuffer.event_handler("on_user_turn_audio_data")
        async def on_user_audio(_, audio, sr, ch):
            name = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f") + "_USER.wav"
            path = f"{session_dir}/{name}"
            await save_audio_file(audio, path, sr, ch)
            await transcript_handler.attach_audio_to_last_message("user", path)

        @audiobuffer.event_handler("on_bot_turn_audio_data")
        async def on_bot_audio(_, audio, sr, ch):
            name = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f") + "_AGENT.wav"
            path = f"{session_dir}/{name}"
            await save_audio_file(audio, path, sr, ch)
            await transcript_handler.attach_audio_to_last_message("assistant", path)

        # TODO: can i use onnx model for viseme detection in the pipeline?
        @viseme_audiobuffer.event_handler("on_track_audio_data")
        async def on_track_audio_data(buffer, user_audio: bytes, bot_audio: bytes,
            sample_rate: int, num_channels: int):

            start_time = time.time()

            loop = asyncio.get_running_loop()
            visemes_durations = await loop.run_in_executor(
                None,
                lambda: process_visemes(bot_audio, sample_rate, num_channels, phoneme_viseme_map)
            )

            end_time = time.time()
            # logger.info(f"Viseme computation took {end_time - start_time:.6f} seconds")

            if visemes_durations and isinstance(visemes_durations, list) and len(visemes_durations) == 1 and visemes_durations[0]["visemes"] == [0]:
                # logger.info("Skipping visemes-event message due to empty or silent visemes.")
                return

            frame = RTVIServerMessageFrame(
                data={
                    "type": "visemes-event",
                    "payload": visemes_durations
                }
            )
            await rtvi.push_frame(frame)

        @rtvi.event_handler("on_client_ready")
        async def on_client_ready(rtvi):
            logger.info("Pipecat client ready.")
            await rtvi.set_bot_ready()
            # Kick off the conversation.
            await task.queue_frames([context_aggregator.user().get_context_frame()])

        @pipecat_transport.event_handler("on_client_connected")
        async def on_client_connected(transport, client):
            logger.info("Pipecat Client connected")
            await viseme_audiobuffer.start_recording()
            await audiobuffer.start_recording()

        @pipecat_transport.event_handler("on_client_disconnected")
        async def on_client_disconnected(transport, client):
            logger.info("Pipecat Client disconnected")
            await viseme_audiobuffer.stop_recording()
            await audiobuffer.stop_recording()

        @pipecat_transport.event_handler("on_client_closed")
        async def on_client_closed(transport, client):
            logger.info("Pipecat Client closed")
            await viseme_audiobuffer.stop_recording()
            await audiobuffer.stop_recording()
            await task.cancel()

        runner = PipelineRunner(handle_sigint=False)

        await runner.run(task)
