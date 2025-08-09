import os
from typing import Optional, Tuple, Literal, List, Dict, Any
from dataclasses import dataclass

from pipecat.services.openai.stt import OpenAISTTService
from pipecat.services.openai.tts import OpenAITTSService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.services.openai_realtime_beta import (
    InputAudioNoiseReduction,
    InputAudioTranscription,
    OpenAIRealtimeBetaLLMService,
    SemanticTurnDetection,
    SessionProperties,
)
from pipecat.services.ollama.llm import OLLamaLLMService
from pipecat.services.piper.tts import PiperTTSService
from pipecat.services.gemini_multimodal_live import GeminiMultimodalLiveLLMService
from pipecat.services.whisper.stt import WhisperSTTService
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
from pipecat.services.llm_service import FunctionCallParams

import json
from .animation_handler import AnimationHandler
from .end_conversation_handler import EndConversationHandler
from .lipsync_processor import LipsyncProcessor
import shutil
from loguru import logger

ModalityType = Literal["classic", "e2e"]
LLMType = Literal["openai", "openai_realtime_beta", "gemini", "llama3.2"]
STTType = Literal["openai", "whisper"]
TTSType = Literal["openai", "elevenlabs", "piper"]

ALLOWED_LLM = {
    "classic": {"openai", "llama3.2"},
    "e2e": {"openai_realtime_beta", "gemini"},
}


@dataclass
class BotComponentFactory:
    session_dir: str
    user_id: str
    modality: ModalityType
    llm_type: LLMType
    llm_params: Optional[Dict[str, Any]] = None
    stt_type: Optional[STTType] = None
    stt_params: Optional[Dict[str, Any]] = None
    tts_type: Optional[TTSType] = None
    tts_params: Optional[Dict[str, Any]] = None
    flow_params: Optional[Dict[str, Any]] = None
    short_term_memory: bool = False
    long_term_memory: bool = False

    task_description: str = ""
    user_description: Optional[str] = None
    avatar_personality_description: str = ""
    avatar_system_prompt: str = ""
    body_animations: Optional[List[str]] = None
    languages: Optional[List[str]] = None
    avatar: Dict[str, Any] = None
    animation_instruction: str = ""

    def __post_init__(self):
        if self.llm_type not in ALLOWED_LLM[self.modality]:
            raise ValueError(
                f"LLM '{self.llm_type}' not allowed for modality '{self.modality}'."
            )

        if self.modality == "classic" and (not self.stt_type or not self.tts_type):
            raise ValueError(
                "Both 'stt_type' and 'tts_type' are required in 'classic' modality."
            )

        if self.modality == "e2e" and (self.stt_type or self.tts_type):
            print("'stt_type' and 'tts_type' will be ignored in 'e2e' mode.")

        if (
            self.llm_type.startswith("openai")
            or self.stt_type == "openai"
            or self.tts_type == "openai"
        ):
            if not os.getenv("OPENAI_API_KEY"):
                raise EnvironmentError("Missing OPENAI_API_KEY in environment.")
        if self.llm_type == "gemini":
            if not os.getenv("GOOGLE_API_KEY"):
                raise EnvironmentError("Missing GOOGLE_API_KEY in environment.")

        if self.tts_type == "elevenlabs":
            if not os.getenv("ELEVENLABS_API_KEY"):
                raise EnvironmentError("Missing ELEVENLABS_API_KEY in environment.")

        if self.tts_type == "piper" and not self.tts_params.get("client_session"):
            raise ValueError("Piper TTS requires 'client_session' in tts_params.")

        if self.body_animations:
            valid_ids = AnimationHandler.get_valid_animation_ids()
            invalid = [a for a in self.body_animations if a not in valid_ids]
            if invalid:
                raise ValueError(
                    f"Invalid animations: {invalid}. Allowed: {sorted(valid_ids)}"
                )

    def build_instruction(self) -> str:
        instruction = f"{self.avatar_system_prompt}\n"
        self.animation_instruction = AnimationHandler.get_animation_instruction(
            self.body_animations
        )
        if self.animation_instruction:
            instruction += self.animation_instruction

        # Add end conversation instruction
        end_conversation_instruction = (
            EndConversationHandler.get_end_conversation_instruction()
        )
        if end_conversation_instruction:
            instruction += end_conversation_instruction

        if self.languages:
            print(f"Supported languages: {self.languages}")
            instruction += (
                f"You are restricted to understanding and responding in the following languages only: "
                f"{', '.join(self.languages)}.\n"
                f"- Do NOT respond in any language outside of {', '.join(self.languages)}.\n"
                f"- If the language used by the user *is* among {', '.join(self.languages)}, "
                "reply in the same language.\n"
                f"- If the language used by the user is *not* among {', '.join(self.languages)}, "
                "respond in one of the allowed languages "
                f"({', '.join(self.languages)}) with a message indicating that you do not understand "
                "or speak that language.\n"
                f"For example: if the user speaks in Spanish and your allowed language is English, "
                f"reply in English with a message saying you do not understand Spanish "
                "and pretend you do not understand the user.\n"
            )
            # TODO: we may improve this by adding a language detection tool!!
        instruction += f"Avatar description: {self.avatar_personality_description}\n"
        instruction += f"Task description: {self.task_description}\n"
        if self.user_description:
            instruction += f"User description: {self.user_description}\n"
        return instruction.strip()

    def build_tools(self) -> ToolsSchema:
        animation_schema = AnimationHandler.build_animation_tools_schema(
            self.body_animations
        )
        self.used_animations = animation_schema.properties.get("animation_id", {}).get(
            "enum", []
        )

        end_conversation_schema = (
            EndConversationHandler.build_end_conversation_tools_schema()
        )

        return ToolsSchema(standard_tools=[animation_schema, end_conversation_schema])

    def get_function_registrations(self, rtvi_processor, use_flows: bool = False):
        """Get the function registrations for the LLM based on configuration.

        Args:
            rtvi_processor: The RTVI processor instance
            use_flows: Whether advanced flows are being used

        Returns:
            List of tuples (function_name, handler_function) to register
        """

        def function_call_debug_wrapper(fn):
            """Debug wrapper for function calls with logging."""

            async def wrapper(params: FunctionCallParams):
                args = (
                    params.arguments
                    if isinstance(params, FunctionCallParams)
                    else params
                )
                logger.info(
                    "FUNCTION_DEBUG: Function '{}' called with args: {}",
                    fn.__name__,
                    json.dumps(args),
                )
                try:
                    result = await fn(params)
                    logger.info(
                        "FUNCTION_DEBUG: Function '{}' completed successfully with result: {}",
                        fn.__name__,
                        json.dumps(result) if result else "None",
                    )

                    # Handle result callback if present
                    if isinstance(params, FunctionCallParams):
                        await params.result_callback(result)
                        return None
                    else:
                        return result

                except Exception as e:
                    logger.error(
                        "FUNCTION_DEBUG: Function '{}' failed with error: {}",
                        fn.__name__,
                        str(e),
                    )
                    # Re-raise the exception after logging
                    raise

            return wrapper

        registrations = []

        # Always register animation handler
        async def animation_handler_wrapper(params):
            """Wrapper for the animation handler to include RTVI and allowed animations."""
            return await AnimationHandler.handle_animation(
                params,
                rtvi=rtvi_processor,
                allowed_animations=self.body_animations or [],
            )

        registrations.append(
            (
                "trigger_animation",
                function_call_debug_wrapper(animation_handler_wrapper),
            )
        )

        # Only register end_conversation when NOT using flows
        # When using flows, end_conversation is handled through pre-actions
        if not use_flows:

            async def end_conversation_handler_wrapper(params):
                """Wrapper for the end conversation handler to include RTVI instance."""
                return await EndConversationHandler.handle_end_conversation(
                    params, rtvi=rtvi_processor
                )

            registrations.append(
                (
                    "end_conversation",
                    function_call_debug_wrapper(end_conversation_handler_wrapper),
                )
            )

        return registrations

    async def build(self) -> Tuple[
        Optional[object],  # STT
        object,  # LLM
        Optional[object],  # TTS
        ToolsSchema,  # tools
        str,  # instruction
        object,  # context
        object,  # context_aggregator
        object,  # used_animations
        str,  # animation_instruction
        object,  # lipsync_processor
    ]:
        stt, llm, tts = None, None, None
        instruction = self.build_instruction()
        tools = self.build_tools()

        if self.modality == "classic":
            if self.stt_type == "openai":
                stt = OpenAISTTService(
                    api_key=os.getenv("OPENAI_API_KEY"),
                    model=(self.stt_params or {}).get("model", "gpt-4o-transcribe"),
                    audio_passthrough=True,
                    prompt=(self.stt_params or {}).get("prompt", None),
                )
            elif self.stt_type == "whisper":
                stt = WhisperSTTService(audio_passthrough=True)

            if self.llm_type == "openai":
                llm = OpenAILLMService(
                    api_key=os.getenv("OPENAI_API_KEY"),
                    model=(self.llm_params or {}).get("model", "gpt-4o-mini"),
                )
            elif self.llm_type == "llama3.2":
                llm = OLLamaLLMService(model=self.llm_type)

            if self.tts_type == "openai":
                voice = (
                    "alloy"
                    if "gender" in self.avatar and self.avatar["gender"] == "feminine"
                    else "ash"
                )
                tts = OpenAITTSService(
                    voice=voice,
                    model=(self.tts_params or {}).get("model", "gpt-4o-mini-tts"),
                )
            elif self.tts_type == "piper":
                # this assumes that 5001 offers female and 5002 offers male
                base_url = (
                    "http://localhost:5001/"
                    if "gender" in self.avatar and self.avatar["gender"] == "feminine"
                    else "http://localhost:5002/"
                )
                tts = PiperTTSService(
                    base_url=base_url,
                    aiohttp_session=(self.tts_params or {})["client_session"],
                )
            elif self.tts_type == "elevenlabs":
                if self.avatar and self.avatar["elevenlabs_voice_id"]:
                    voice_id = self.avatar[
                        "elevenlabs_voice_id"
                    ]  # elevenlabs supports custom voice IDs
                else:
                    voice_id = (
                        "XrExE9yKIg1WjnnlVkGX"
                        if "gender" in self.avatar
                        and self.avatar["gender"] == "feminine"
                        else "cjVigY5qzO86Huf0OWal"
                    )

                tts = ElevenLabsTTSService(
                    api_key=os.getenv("ELEVENLABS_API_KEY"),
                    voice_id=voice_id,
                    model="eleven_flash_v2_5",
                )

        elif self.modality == "e2e":
            if self.llm_type == "openai_realtime_beta":
                voice = (
                    "alloy"
                    if "gender" in self.avatar and self.avatar["gender"] == "feminine"
                    else "ash"
                )
                print(
                    "Using OpenAI Realtime Beta LLM Service with voice:",
                    voice,
                    "avatar: ",
                    self.avatar,
                )
                props = SessionProperties(
                    input_audio_transcription=InputAudioTranscription(),
                    turn_detection=SemanticTurnDetection(),
                    input_audio_noise_reduction=InputAudioNoiseReduction(
                        type="near_field"
                    ),
                    instructions=instruction,
                    voice=voice,
                )
                llm = OpenAIRealtimeBetaLLMService(
                    api_key=os.getenv("OPENAI_API_KEY"),
                    model=(self.llm_params or {}).get(
                        "model", "gpt-4o-realtime-preview-2025-06-03"
                    ),
                    session_properties=props,
                    start_audio_paused=False,
                    send_transcription_frames=True,
                )
            elif self.llm_type == "gemini":
                llm = GeminiMultimodalLiveLLMService(
                    api_key=os.getenv("GOOGLE_API_KEY"),
                    voice_id=(
                        "Aoede"
                        if "gender" in self.avatar
                        and self.avatar["gender"] == "feminine"
                        else "Charon"
                    ),
                    transcribe_user_audio=True,
                    transcribe_model_audio=True,
                    system_instruction=instruction,
                    tools=tools,
                )

        messages = []
        messages.append({"role": "system", "content": instruction})
        if self.long_term_memory:
            print("Building long term memory...")
            parent_dir = os.path.dirname(self.session_dir)
            print("Parent directory:", parent_dir)
            current_session_name = os.path.basename(self.session_dir)

            # Get all previous sessions for this user
            user_sessions = sorted(
                [
                    d
                    for d in os.listdir(parent_dir)
                    if d.startswith(self.user_id)
                    and d != current_session_name
                    and os.path.isdir(os.path.join(parent_dir, d))
                ]
            )

            print("Previous sessions for this user:", user_sessions)

            all_past_messages = []
            for session_id in user_sessions:
                session_path = os.path.join(parent_dir, session_id)
                transcript_path = os.path.join(session_path, "transcript.json")
                if os.path.exists(transcript_path):
                    try:
                        with open(transcript_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            # Add a system message before each session's messages
                            all_past_messages.append(
                                {
                                    "role": "system",
                                    "content": f"--- Start of previous session `{session_id}` ---",
                                }
                            )
                            for message in data:
                                if "role" in message and "content" in message:
                                    all_past_messages.append(
                                        {
                                            "role": (
                                                message["role"]
                                                if message["role"] == "user"
                                                else "assistant"
                                            ),
                                            "content": message["content"],
                                        }
                                    )
                            all_past_messages.append(
                                {
                                    "role": "system",
                                    "content": f"--- End of previous session `{session_id}` ---",
                                }
                            )
                    except Exception as e:
                        print(f"Error loading transcript from {session_id}: {e}")
                        continue

            if all_past_messages:
                messages.extend(all_past_messages)

        print("messages before this session:", messages)

        transcript_path = os.path.join(self.session_dir, "transcript.json")
        if self.short_term_memory and os.path.exists(transcript_path):
            print("Loading transcript.json from:", transcript_path)
            try:
                with open(transcript_path, "r", encoding="utf-8") as f:
                    transcript_data = json.load(f)

                    messages.append(
                        {
                            "role": "system",
                            "content": "--- Start of the current session ---",
                        }
                    )
                    for message in transcript_data:
                        messages.append(
                            {
                                "role": (
                                    message["role"]
                                    if message["role"] == "user"
                                    else "assistant"
                                ),
                                "content": message["content"],
                            }
                        )
                    messages.append(
                        {
                            "role": "system",
                            "content": (
                                "Please continue the conversation from where you left. "
                                "There has been an interruption. "
                                "Make a summary of the conversation so far before continuing."
                            ),
                        }
                    )
            except Exception as e:
                print(f"Failed to load transcript.json: {e}")
                raise ValueError("Failed to load transcript.json")
        else:
            if self.short_term_memory:
                print("Transcript.json not found. Starting a new conversation.")
            else:
                print("Short term memory disabled. Starting a new conversation.")
                # Clean up session directory: remove audios, json folders, and specific files
                for item in os.listdir(self.session_dir):
                    item_path = os.path.join(self.session_dir, item)
                    if os.path.isdir(item_path) and item in ("audios", "json"):
                        try:
                            shutil.rmtree(item_path)
                            print(f"Deleted folder: {item_path}")
                        except Exception as e:
                            print(f"Failed to delete folder {item_path}: {e}")
                    elif os.path.isfile(item_path):
                        if (
                            item
                            in (
                                "metrics_log.json",
                                "metrics_summary.json",
                                "transcript.json",
                            )
                            or item.startswith("session_")
                            and (item.endswith(".wav") or item.endswith(".mp4"))
                        ):
                            try:
                                os.remove(item_path)
                                print(f"Deleted file: {item_path}")
                            except Exception as e:
                                print(f"Failed to delete file {item_path}: {e}")
            if self.long_term_memory and all_past_messages:
                print("Still, be aware of the previous sessions.")
                messages.append(
                    {
                        "role": "system",
                        "content": (
                            "Please make a summary of the previous conversations so far "
                            "(stressing goals and achievements), "
                            "and then continue the conversation from where you left."
                        ),
                    }
                )

        # print("Messages of this session:", messages)

        context = OpenAILLMContext(messages=messages, tools=tools, tool_choice="auto")
        context_aggregator = llm.create_context_aggregator(context=context)
        lipsync_processor = LipsyncProcessor(strategy="timestamped_asr")

        return (
            stt,
            llm,
            tts,
            tools,
            instruction,
            context,
            context_aggregator,
            self.used_animations,
            self.animation_instruction,
            lipsync_processor,
        )
