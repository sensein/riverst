import os
from typing import Optional, Tuple, Literal, List, Dict, Any
from dataclasses import dataclass

from pipecat.services.openai.stt import OpenAISTTService
from pipecat.services.openai import OpenAILLMService, OpenAITTSService
from pipecat.services.openai_realtime_beta import (
    InputAudioNoiseReduction, InputAudioTranscription,
    OpenAIRealtimeBetaLLMService, SemanticTurnDetection, SessionProperties
)
from pipecat.services.ollama import OLLamaLLMService
from pipecat.services.piper import PiperTTSService
from pipecat.services.gemini_multimodal_live import GeminiMultimodalLiveLLMService
from pipecat.services.whisper.stt import WhisperSTTService
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.transports.base_transport import TransportParams

ModalityType = Literal["classic", "e2e"]
LLMType = Literal["openai", "openai_realtime_beta", "gemini", "llama3.2"]
STTType = Literal["openai", "whisper"]
TTSType = Literal["openai", "piper"]

ALLOWED_LLM = {
    "classic": {"openai", "llama3.2"},
    "e2e": {"openai_realtime_beta", "gemini"},
}

VALID_ANIMATIONS = [
    {"id": "wave", "description": "When the user joins the room, say hi and (sometimes) wave with your hand."},
    {"id": "dance", "description": "When you want to congratulate, sometimes you can dance."},
    {"id": "i_dont_know", "description": "When you don’t know something, you can do the 'I don’t know' animation."},
]

@dataclass
class BotComponentFactory:
    modality: ModalityType
    llm_type: LLMType
    llm_params: Optional[Dict[str, Any]] = None
    stt_type: Optional[STTType] = None
    stt_params: Optional[Dict[str, Any]] = None
    tts_type: Optional[TTSType] = None
    tts_params: Optional[Dict[str, Any]] = None
    advanced_flows: bool = False
    flow_params: Optional[Dict[str, Any]] = None

    task_description: str = ""
    user_description: Optional[str] = None
    avatar_personality_description: str = ""
    avatar_system_prompt: str = ""
    body_animations: Optional[List[str]] = None

    def __post_init__(self):
        if self.llm_type not in ALLOWED_LLM[self.modality]:
            raise ValueError(f"LLM '{self.llm_type}' not allowed for modality '{self.modality}'.")

        if self.modality == "classic" and (not self.stt_type or not self.tts_type):
            raise ValueError("Both 'stt_type' and 'tts_type' are required in 'classic' modality.")

        if self.modality == "e2e" and (self.stt_type or self.tts_type):
            print("'stt_type' and 'tts_type' will be ignored in 'e2e' mode.")

        if self.llm_type.startswith("openai") or self.stt_type == "openai" or self.tts_type == "openai":
            if not os.getenv("OPENAI_API_KEY"):
                raise EnvironmentError("Missing OPENAI_API_KEY in environment.")
        if self.llm_type == "gemini":
            if not os.getenv("GOOGLE_API_KEY"):
                raise EnvironmentError("Missing GOOGLE_API_KEY in environment.")

        if self.tts_type == "piper" and not self.tts_params.get("client_session"):
            raise ValueError("Piper TTS requires 'client_session' in tts_params.")

        if self.body_animations:
            valid_ids = {a["id"] for a in VALID_ANIMATIONS}
            invalid = [a for a in self.body_animations if a not in valid_ids]
            if invalid:
                raise ValueError(f"Invalid animations: {invalid}. Allowed: {sorted(valid_ids)}")

    def build_animation_instruction(self) -> str:
        if not self.body_animations:
            return ""

        animation_map = {a["id"]: a["description"] for a in VALID_ANIMATIONS}
        instructions = [
            animation_map[anim_id]
            for anim_id in set(self.body_animations) & set(animation_map)
        ]
        return " ".join(instructions)

    def build_instruction(self) -> str:
        instruction = f"{self.avatar_system_prompt}\n"
        animation_instruction = self.build_animation_instruction()
        if animation_instruction:
            instruction += f"\nAnimation instructions: {animation_instruction}\n"
        instruction += f"Avatar description: {self.avatar_personality_description}\n"
        instruction += f"Task description: {self.task_description}\n"
        if self.user_description:
            instruction += f"User description: {self.user_description}\n"
        return instruction.strip()

    def build_tools(self) -> ToolsSchema:
        valid_ids = {a["id"] for a in VALID_ANIMATIONS}
        animations = list(set(self.body_animations or []) & valid_ids)
        return ToolsSchema(standard_tools=[
            FunctionSchema(
                name="trigger_animation",
                description="Trigger an avatar animation (only one at a time).",
                properties={
                    "animation_id": {
                        "type": "string",
                        "enum": animations,
                        "description": "The animation ID to trigger.",
                    }
                },
                required=["animation_id"]
            )
        ])

    async def build(self) -> Tuple[
        Optional[object],  # STT
        object,            # LLM
        Optional[object],  # TTS
        ToolsSchema,
        str,
        object,            # context
        object            # context_aggregator
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
                    model=(self.llm_params or {}).get("model", "gpt-4o-mini")
                )
            elif self.llm_type == "llama3.2":
                llm = OLLamaLLMService(model=self.llm_type)

            if self.tts_type == "openai":
                tts = OpenAITTSService(
                    voice=(self.tts_params or {}).get("voice", "nova"), # TODO: add more voices
                    model=(self.tts_params or {}).get("model", "gpt-4o-mini-tts")
                )
            elif self.tts_type == "piper":
                tts = PiperTTSService(
                    base_url=(self.tts_params or {}).get("base_url", "http://localhost:5001/"),
                    aiohttp_session=(self.tts_params or {})["client_session"]
                )

        elif self.modality == "e2e":
            if self.llm_type == "openai_realtime_beta":
                props = SessionProperties(
                    input_audio_transcription=InputAudioTranscription(),
                    turn_detection=SemanticTurnDetection(),
                    input_audio_noise_reduction=InputAudioNoiseReduction(type="near_field"),
                    instructions=instruction,
                )
                llm = OpenAIRealtimeBetaLLMService(
                    api_key=os.getenv("OPENAI_API_KEY"),
                    model=(self.llm_params or {}).get("model", "gpt-4o-realtime-preview-2024-12-17"),
                    session_properties=props,
                    start_audio_paused=False,
                    send_transcription_frames=True,
                )
                # TODO: add more voices
            elif self.llm_type == "gemini":
                llm = GeminiMultimodalLiveLLMService(
                    api_key=os.getenv("GOOGLE_API_KEY"),
                    voice_id=(self.llm_params or {}).get("voice_id", "Aoede"), # TODO: add more voices
                    transcribe_user_audio=True,
                    transcribe_model_audio=True,
                    system_instruction=instruction,
                    tools=tools,
                )

        messages = [{"role": "system", "content": instruction}]
        context = OpenAILLMContext(messages=messages, tools=tools)
        context_aggregator = llm.create_context_aggregator(context=context)

        return stt, llm, tts, tools, instruction, context, context_aggregator
