"""
Detection module base interface for incomplete sales element detection.
Defines the Strategy pattern for different detection implementations.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class DetectionStrategy(ABC):
    """Abstract base class for incomplete sales element detection strategies."""
    
    @abstractmethod
    async def detect(self, text: str, prompt: str) -> Dict[str, Any]:
        """
        Detect incomplete sales elements in the given text.
        
        Args:
            text: The main text content to analyze
            prompt: The prompt to use for detection
            
        Returns:
            Dictionary containing:
            {
                "detected_issues": [issue1, issue2, ...],
                "confidence": 0.0-1.0,
                "raw_response": "...",
                "tokens_used": 1234,
                "model_used": "...",
                "processing_time_ms": 1234
            }
        """
        pass
    
    @abstractmethod
    def validate_config(self) -> bool:
        """
        Validate that all required configuration is available.
        
        Returns:
            True if config is valid, raises ValueError otherwise
        """
        pass
    
    async def extract_issues(self, response: str) -> list:
        """
        Extract detected issues from the model response.
        
        Override in subclass if custom parsing is needed.
        
        Args:
            response: Raw response from the model
            
        Returns:
            List of detected issues
        """
        # Default implementation: split by newlines and filter
        lines = [line.strip() for line in response.split('\n') if line.strip()]
        return lines
