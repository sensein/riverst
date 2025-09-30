"""Custom OLLama LLM Service"""

from pipecat.services.ollama.llm import OLLamaLLMService


class CustomOLLamaLLMService(OLLamaLLMService):
    def __init__(self, **kwargs):
        # Force think=False regardless of what the caller provides
        # See https://ollama.com/blog/thinking
        # This doesn't actually work because **kwargs is not used to initialize
        # BaseOpenAILLMService in pipecat-ai. Need to open a PR there.
        kwargs["think"] = False
        super().__init__(**kwargs)
