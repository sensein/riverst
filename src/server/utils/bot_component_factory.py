import os
from typing import Optional, Tuple, Literal, List, Dict, Any
from dataclasses import dataclass

from pipecat.services.openai.stt import OpenAISTTService
from pipecat.services.openai.tts import OpenAITTSService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.services.openai_realtime_beta import (
    InputAudioNoiseReduction, InputAudioTranscription,
    OpenAIRealtimeBetaLLMService, SemanticTurnDetection, SessionProperties
)
from pipecat.services.ollama.llm import OLLamaLLMService
from pipecat.services.piper.tts import PiperTTSService
from pipecat.services.gemini_multimodal_live import GeminiMultimodalLiveLLMService
from pipecat.services.whisper.stt import WhisperSTTService
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.transports.base_transport import TransportParams
import json

ModalityType = Literal["classic", "e2e"]
LLMType = Literal["openai", "openai_realtime_beta", "gemini", "llama3.2"]
STTType = Literal["openai", "whisper"]
TTSType = Literal["openai", "piper"]

ALLOWED_LLM = {
    "classic": {"openai", "llama3.2"},
    "e2e": {"openai_realtime_beta", "gemini"},
}

VALID_ANIMATIONS = [
    {"id": "wave", "description": "When you welcome the user or greet them or introduce yourself, you always wave with your hand (animation)."},
    {"id": "dance", "description": "When you congratulate or appreciate the user or are happy, you dance (animation)."},
    {"id": "i_dont_know", "description": "When you don’t know something, you do the 'I don’t know' animation."},
]

@dataclass
class BotComponentFactory:
    session_dir: str
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
    languages: Optional[List[str]] = None
    avatar: Dict[str, Any] = None

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
        if self.languages:
            print(f"Supported languages: {self.languages}")
            instruction += (
                f"You are restricted to understanding and responding in the following languages only: "
                f"{', '.join(self.languages)}. Do NOT respond in any language outside if {', '.join(self.languages)}. "
                f"If that language is among {', '.join(self.languages)}, reply in the same language used by the user in the last interaction.\n"
                f"If the lanugage is NOT among {', '.join(self.languages)}, reply in one and only one of these languages ({', '.join(self.languages)}) with a message indicating "
                f"that you do not understand or speak that language and pretend you do not understand the user.\n"
                f"For instance, if the user speaks in Spanish and you only understand English, "
                f"reply in English with a message indicating that you do not understand or speak that language and pretend you do not understand the user.\n"
            )
            #TODO: we may improve this by adding a language detection tool!!
        instruction += f"Avatar description: {self.avatar_personality_description}\n"
        instruction += f"Task description: {self.task_description}\n"
        if self.user_description:
            instruction += f"User description: {self.user_description}\n"
        return instruction.strip()

    def build_tools(self) -> ToolsSchema:
        valid_ids = {a["id"] for a in VALID_ANIMATIONS}
        animations = list(set(self.body_animations or []) & valid_ids)
        self.used_animations = animations
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
                voice = "alloy" if 'gender' in self.avatar and self.avatar['gender'] == 'feminine' else "ash"
                tts = OpenAITTSService(
                    voice=voice,
                    model=(self.tts_params or {}).get("model", "gpt-4o-mini-tts")
                )
            elif self.tts_type == "piper":
                # this assumes that 5001 offers female and 5002 offers male
                base_url = "http://localhost:5001/" if 'gender' in self.avatar and self.avatar['gender'] == 'feminine' else "http://localhost:5002/"
                tts = PiperTTSService(
                    base_url=base_url,
                    aiohttp_session=(self.tts_params or {})["client_session"]
                )

        elif self.modality == "e2e":
            if self.llm_type == "openai_realtime_beta":
                voice = "alloy" if 'gender' in self.avatar and self.avatar['gender'] == 'feminine' else "ash"
                print("Using OpenAI Realtime Beta LLM Service with voice:", voice, "avatar: ", self.avatar)
                props = SessionProperties(
                    input_audio_transcription=InputAudioTranscription(),
                    turn_detection=SemanticTurnDetection(),
                    input_audio_noise_reduction=InputAudioNoiseReduction(type="near_field"),
                    instructions=instruction,
                    voice = voice
                )
                llm = OpenAIRealtimeBetaLLMService(
                    api_key=os.getenv("OPENAI_API_KEY"),
                    model=(self.llm_params or {}).get("model", "gpt-4o-realtime-preview-2024-12-17"),
                    session_properties=props,
                    start_audio_paused=False,
                    send_transcription_frames=True,
                )
            elif self.llm_type == "gemini":
                llm = GeminiMultimodalLiveLLMService(
                    api_key=os.getenv("GOOGLE_API_KEY"),
                    voice_id= "Aoede" if 'gender' in self.avatar and self.avatar['gender'] == 'feminine' else "Charon",
                    transcribe_user_audio=True,
                    transcribe_model_audio=True,
                    system_instruction=instruction,
                    tools=tools,
                )


        transcript_path = os.path.join(self.session_dir, "transcript.json")
        if os.path.exists(transcript_path):
            print("Loading transcript.json from:", transcript_path)
            try:
                with open(transcript_path, "r", encoding="utf-8") as f:
                    transcript_data = json.load(f)
                    messages = [{"role": "system", "content": instruction}]
                    for message in transcript_data:
                        messages.append({
                            "role": message["role"] if message["role"] == "user" else "model",
                            "content": message["content"],
                        })
                    messages.append({
                        "role": "system",
                        "content": "Please continue the conversation from where you left. There has been an interruption. Maybe make a summary of the conversation so far before continuing.",
                    })
            except Exception as e:
                print(f"Failed to load transcript.json: {e}")
                raise ValueError("Failed to load transcript.json")
        else:
            print("No transcript.json found. Starting a new conversation.")
            messages = [{"role": "system", "content": instruction}]

        print("Messages:", messages)
        context = OpenAILLMContext(messages=messages, tools=tools)
        context_aggregator = llm.create_context_aggregator(context=context)

        return stt, llm, tts, tools, instruction, context, context_aggregator, self.used_animations
