"""
Simple test file to verify flow configuration loading works correctly.
"""
import json
import sys
from pathlib import Path

from utils.flows import load_config
from loguru import logger

def main():
    try:
        # Find a flow configuration file to test with
        flow_file = Path(__file__).parent / "assets" / "activities" / "flows" / "vocab-tutoring.json"
        
        if not flow_file.exists():
            logger.error(f"Flow file not found: {flow_file}")
            return 1
            
        logger.info(f"Loading flow configuration from: {flow_file}")
        config = load_config(str(flow_file))
        logger.info("Successfully loaded and validated flow configuration:")
        logger.info(f"Flow name: {config['name']}")
        logger.info(f"Initial node: {config['node_config']['initial_node']}")
        logger.info(f"Number of nodes: {len(config['node_config']['nodes'])}")
        logger.info(f"Number of schemas: {len(config['schemas'])}")
        return 0
        
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())