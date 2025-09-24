import os
from typing import Optional, Literal, List, Dict, Any, NamedTuple
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
from pipecat.services.piper.tts import PiperTTSService
from pipecat.services.gemini_multimodal_live import GeminiMultimodalLiveLLMService
from pipecat.services.whisper.stt import WhisperSTTService
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService

from ..components.llm_tools.animation_handler import AnimationHandler
from ..components.llm_tools.end_conversation_handler import EndConversationHandler
from ..processors.speech.lipsync_processor import LipsyncProcessor
from ..transport.custom_services.kokoro_service import KokoroTTSService
from ..utils.device_utils import get_best_device
from ..transport.custom_services.ollama_service import CustomOLLamaLLMService
from ..components.memory import MemoryHandler

ModalityType = Literal["classic", "e2e"]
LLMType = Literal[
    "openai",
    "openai_gpt-realtime",
    "ollama/qwen3:4b-instruct-2507-q4_K_M",
]
STTType = Literal["openai", "whisper"]
TTSType = Literal["openai", "piper", "kokoro"]

ALLOWED_LLM = {
    "classic": {"openai", "ollama/qwen3:4b-instruct-2507-q4_K_M"},
    "e2e": {"openai_gpt-realtime"},
}


class BotComponents(NamedTuple):
    """Named tuple containing all bot components built by the factory."""

    stt: Optional[object]
    llm: object
    tts: Optional[object]
    tools_schema: object
    instruction: str
    context: object
    context_aggregator: object
    used_animations: List[str]
    animation_instruction: str
    lipsync_processor: object


class FixedOpenAIRealtimeBetaLLMService(OpenAIRealtimeBetaLLMService):
    """This class overrides the _calculate_audio_duration_ms method to add a 85ms safety buffer.

    https://github.com/pipecat-ai/pipecat/issues/2106#issuecomment-3168228292
    """

    def _calculate_audio_duration_ms(
        self, total_bytes: int, sample_rate: int = 24000, bytes_per_sample: int = 2
    ) -> int:
        samples = total_bytes / bytes_per_sample
        duration_seconds = samples / sample_rate

        # Add a 85ms safety buffer by subtracting from the calculated duration
        return int((duration_seconds * 1000) - 85)


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
    advanced_flows: bool = False
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
            # print(f"Supported languages: {self.languages}")
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

    def build_tools_schemas(self) -> ToolsSchema:
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

    def register_tools(self, llm, rtvi, task) -> None:
        """Register tool handlers with the LLM after all components are built.

        This method should be called after the task is created but before pipeline execution.

        Args:
            llm: The LLM service instance
            rtvi: The RTVI processor instance
            task: The pipeline task instance

        Returns: A dictionary of tool handlers
                    - animation: The animation handler
                    - end_conversation: The end conversation handler

        """
        # Register animation handler
        animation_handler = AnimationHandler(
            rtvi=rtvi, allowed_animations=self.used_animations
        )
        llm.register_function("trigger_animation", animation_handler.handle_animation)

        # Register end conversation handler
        end_conversation_handler = EndConversationHandler(task)
        llm.register_function(
            "end_conversation", end_conversation_handler.handle_end_conversation
        )

        return {
            "animation": animation_handler,
            "end_conversation": end_conversation_handler,
        }

    async def build(self) -> BotComponents:
        instruction = self.build_instruction()
        tools_schemas = self.build_tools_schemas()

        stt = self._build_stt_service()
        llm = self._build_llm_service(instruction, tools_schemas)
        tts = self._build_tts_service()

        memory_handler = MemoryHandler(self.session_dir, self.user_id)
        messages = memory_handler.build_memory_context(
            instruction, self.long_term_memory, self.short_term_memory
        )

        context = OpenAILLMContext(
            messages=messages, tools=tools_schemas, tool_choice="auto"
        )
        context_aggregator = llm.create_context_aggregator(context=context)

        return BotComponents(
            stt=stt,
            llm=llm,
            tts=tts,
            tools_schema=tools_schemas,
            instruction=instruction,
            context=context,
            context_aggregator=context_aggregator,
            used_animations=self.used_animations,
            animation_instruction=self.animation_instruction,
            lipsync_processor=LipsyncProcessor(),
        )

    def _get_voice_for_openai(self) -> str:
        """Get OpenAI voice based on avatar gender."""
        return (
            "alloy"
            if "gender" in self.avatar and self.avatar["gender"] == "feminine"
            else "ash"
        )

    def _get_voice_id_for_elevenlabs(self) -> str:
        """Get ElevenLabs voice ID based on avatar configuration."""
        if self.avatar and self.avatar.get("elevenlabs_voice_id"):
            return self.avatar["elevenlabs_voice_id"]

        return (
            "XrExE9yKIg1WjnnlVkGX"
            if "gender" in self.avatar and self.avatar["gender"] == "feminine"
            else "cjVigY5qzO86Huf0OWal"
        )

    def _get_base_url_for_piper(self) -> str:
        """Get Piper base URL based on avatar gender."""
        return (
            "http://localhost:5001/"
            if "gender" in self.avatar and self.avatar["gender"] == "feminine"
            else "http://localhost:5002/"
        )

    def _get_voice_id_for_kokoro(self) -> str:
        """Get Kokoro voice based on avatar gender."""
        return (
            "af_heart"
            if "gender" in self.avatar and self.avatar["gender"] == "feminine"
            else "am_puck"
        )

    def _get_voice_id_for_gemini(self) -> str:
        """Get Gemini voice ID based on avatar gender."""
        return (
            "Aoede"
            if "gender" in self.avatar and self.avatar["gender"] == "feminine"
            else "Charon"
        )

    def _build_stt_service(self) -> Optional[object]:
        """Build STT service based on configuration."""
        if not self.stt_type:
            return None

        if self.stt_type == "openai":
            return OpenAISTTService(
                api_key=os.getenv("OPENAI_API_KEY"),
                model=(self.stt_params or {}).get("model", "gpt-4o-transcribe"),
                audio_passthrough=True,
                prompt=(self.stt_params or {}).get("prompt", None),
            )
        elif self.stt_type == "whisper":
            best_device = str(get_best_device(options=["mps", "cpu"]))
            if best_device == "mps":
                from pipecat.services.whisper.stt import WhisperSTTServiceMLX, MLXModel

                return WhisperSTTServiceMLX(
                    audio_passthrough=True, device=best_device, model=MLXModel.TINY
                )
            else:
                return WhisperSTTService(
                    audio_passthrough=True,
                    device=best_device,
                    model="tiny",
                )
        return None

    def _build_llm_service(self, instruction: str, tools_schemas) -> object:
        """Build LLM service based on configuration."""
        if self.modality == "classic":
            if self.llm_type == "openai":
                return OpenAILLMService(
                    api_key=os.getenv("OPENAI_API_KEY"),
                    model=(self.llm_params or {}).get("model", "gpt-4.1"),
                )
            elif self.llm_type.startswith("ollama/"):
                return CustomOLLamaLLMService(
                    model=self.llm_type.replace("ollama/", ""),
                    base_url="http://localhost:11434/v1",
                )
        elif self.modality == "e2e":
            if self.llm_type == "openai_gpt-realtime":
                voice = self._get_voice_for_openai()
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
                return FixedOpenAIRealtimeBetaLLMService(
                    api_key=os.getenv("OPENAI_API_KEY"),
                    model=(self.llm_params or {}).get("model", "gpt-realtime"),
                    session_properties=props,
                    start_audio_paused=False,
                    send_transcription_frames=True,
                )
            elif self.llm_type == "gemini":
                return GeminiMultimodalLiveLLMService(
                    api_key=os.getenv("GOOGLE_API_KEY"),
                    voice_id=self._get_voice_id_for_gemini(),
                    transcribe_user_audio=True,
                    transcribe_model_audio=True,
                    system_instruction=instruction,
                    tools=tools_schemas,
                )
        raise ValueError(
            f"Unsupported LLM configuration: {self.llm_type} with modality {self.modality}"
        )

    def _build_tts_service(self) -> Optional[object]:
        """Build TTS service based on configuration."""
        if not self.tts_type:
            return None

        if self.tts_type == "openai":
            return OpenAITTSService(
                voice=self._get_voice_for_openai(),
                model=(self.tts_params or {}).get("model", "gpt-4o-mini-tts"),
            )
        elif self.tts_type == "piper":
            return PiperTTSService(
                base_url=self._get_base_url_for_piper(),
                aiohttp_session=(self.tts_params or {})["client_session"],
            )
        elif self.tts_type == "elevenlabs":
            return ElevenLabsTTSService(
                api_key=os.getenv("ELEVENLABS_API_KEY"),
                voice_id=self._get_voice_id_for_elevenlabs(),
                model="eleven_flash_v2_5",
            )
        elif self.tts_type == "kokoro":
            device = get_best_device()
            return KokoroTTSService(
                voice=self._get_voice_id_for_kokoro(), device=device
            )
        return None
