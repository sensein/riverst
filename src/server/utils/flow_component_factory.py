import os
import json
from typing import Any, Optional

from loguru import logger
from pipecat.pipeline.task import PipelineTask
from pipecat_flows import FlowManager, ContextStrategy, ContextStrategyConfig

from .flows import load_config


class FlowComponentFactory:
    """Factory class for creating and initializing flow management components.
    
    This class encapsulates the creation and configuration of flow-related 
    components, ensuring proper initialization and error handling.
    """

    def __init__(
        self,
        llm: Any,
        context_aggregator: Any,
        task: PipelineTask,
        advanced_flows: bool = False,
        flow_config_path: Optional[str] = None,
        context_strategy: ContextStrategy = ContextStrategy.RESET_WITH_SUMMARY,
        summary_prompt: str = "Summarize the key moments of learning, words, and concepts discussed in the tutoring session so far. Keep it concise and focused on vocabulary learning.",
    ):
        """Initialize the FlowComponentFactory.
        
        Args:
            llm: The language model to use with the flow manager
            context_aggregator: The context aggregator component
            task: The pipeline task
            advanced_flows: Whether to use advanced flows
            flow_config_path: Path to the flow configuration file
            context_strategy: Strategy for managing context
            summary_prompt: Prompt for summarizing conversation
        """
        self.llm = llm
        self.context_aggregator = context_aggregator
        self.task = task
        self.advanced_flows = advanced_flows
        self.flow_config_path = flow_config_path
        self.context_strategy = context_strategy
        self.summary_prompt = summary_prompt
        self.flow_manager = None

    def build(self) -> Optional[FlowManager]:
        """Build and configure the flow manager.
        
        Returns:
            FlowManager: The configured flow manager, or None if flows are disabled
        """
        if not self.advanced_flows:
            logger.info("Advanced flows disabled, skipping flow manager initialization")
            return None

        logger.info(f"Initializing flow manager with config path: {self.flow_config_path}")
        
        if not self.flow_config_path:
            logger.error("Flow config path not provided but advanced_flows is enabled")
            return None
            
        try:
            
            flow_config, state = load_config(self.flow_config_path)

            flow_manager = FlowManager(
                llm=self.llm,
                context_aggregator=self.context_aggregator,
                context_strategy=ContextStrategyConfig(
                    strategy=self.context_strategy,
                    summary_prompt=self.summary_prompt,
                ),
                task=self.task,
                flow_config=flow_config
            )
            flow_manager.state = state
            
            self.flow_manager = flow_manager
            logger.info("Flow manager successfully built")
            return flow_manager
            
        except FileNotFoundError as e:
            logger.error(f"Flow configuration file not found: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in flow configuration file: {e}")
            return None
        except Exception as e:
            logger.error(f"Error initializing flow manager: {e}")
            return None
    
    async def initialize(self) -> bool:
        """Initialize the flow manager asynchronously.
        
        Returns:
            bool: True if initialization was successful, False otherwise
        """
        if not self.flow_manager:
            logger.warning("Flow manager not built, cannot initialize")
            return False
            
        try:
            await self.flow_manager.initialize()
            logger.info("Flow manager successfully initialized")
            return True
        except Exception as e:
            logger.error(f"Error during flow manager initialization: {e}")
            return False