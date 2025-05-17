"""
Simple test file to verify flow configuration loading works correctly.
"""
import sys
import json
from pathlib import Path

# Add parent directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.flows import load_config
from loguru import logger

def main():
    try:
        # Correct path to flow configuration (2 levels up from tests folder)
        flow_file = (
            Path(__file__).parent.parent / 
            "assets" / 
            "activities" / 
            "flows" / 
            "vocab-tutoring.json"
        )

        if not flow_file.exists():
            logger.error(f"Flow file not found: {flow_file}")
            return 1

        logger.info(f"Loading flow configuration from: {flow_file}")
        node_config, stages_config = load_config(str(flow_file))  # Unpack the tuple
        logger.info("Successfully loaded and validated flow configuration:")
        logger.info(f"Initial node: {node_config['initial_node']}")
        logger.info(f"Number of nodes: {len(node_config['nodes'])}")
        logger.info(f"Number of stages: {len(stages_config['stages'])}")
        return 0

    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())