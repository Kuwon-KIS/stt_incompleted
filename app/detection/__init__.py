"""
Detection module initialization and factory function.
Provides a unified interface to get the appropriate detector strategy.
"""

from .base import DetectionStrategy
from .vllm_detector import VLLMDetector
from .agent_detector import AgentDetector
import logging

logger = logging.getLogger(__name__)


def get_detector(call_type: str, config) -> DetectionStrategy:
    """
    Factory function to get the appropriate detection strategy.
    
    Args:
        call_type: Type of detector to use ("vllm" or "agent")
        config: Application configuration object
        
    Returns:
        Instance of DetectionStrategy
        
    Raises:
        ValueError: If call_type is not recognized
    """
    if call_type == "vllm":
        logger.debug("Creating VLLMDetector")
        detector = VLLMDetector(config)
    elif call_type == "agent":
        logger.debug("Creating AgentDetector")
        detector = AgentDetector(config)
    else:
        raise ValueError(f"Unknown call_type: {call_type}. Must be 'vllm' or 'agent'")
    
    # Validate configuration
    detector.validate_config()
    
    return detector


__all__ = [
    "DetectionStrategy",
    "VLLMDetector",
    "AgentDetector",
    "get_detector"
]
