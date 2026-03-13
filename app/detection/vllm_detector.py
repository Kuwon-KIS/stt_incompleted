"""
vLLM-based implementation of the detection strategy.
Uses prompt templates for structured detection.
"""

import logging
import requests
import time
from typing import Dict, Any
from .base import DetectionStrategy

logger = logging.getLogger(__name__)


class VLLMDetector(DetectionStrategy):
    """Detection strategy using vLLM API with prompt templates.
    
    Characteristics:
    - Uses prompt templates for consistent input format
    - Supports custom model paths
    - Requires LLM_URL and MODEL_PATH configuration
    """
    
    def __init__(self, config):
        """
        Initialize vLLM detector.
        
        Args:
            config: Application configuration object
        """
        self.config = config
        self.model_path = config.MODEL_PATH
        self.llm_url = config.LLM_URL
        self.auth_header = config.LLM_AUTH_HEADER
    
    def validate_config(self) -> bool:
        """Validate required vLLM configuration."""
        if not self.llm_url:
            raise ValueError("LLM_URL is required for vLLM detector")
        if not self.model_path:
            raise ValueError("MODEL_PATH is required for vLLM detector")
        return True
    
    async def detect(self, text: str, prompt: str) -> Dict[str, Any]:
        """
        Detect incomplete sales elements using vLLM API.
        
        Args:
            text: Main content to analyze
            prompt: Complete prompt (already formatted from template)
            
        Returns:
            Detection result dictionary
        """
        self.validate_config()
        
        logger.info("vLLM detection starting: model=%s, prompt_length=%d", 
                    self.model_path, len(prompt))
        
        start_time = time.time()
        
        try:
            # Call vLLM API with /v1/chat/completions format
            payload = {
                "model": self.model_path,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 2000,
            }
            
            headers = {
                "Content-Type": "application/json"
            }
            if self.auth_header:
                headers["Authorization"] = self.auth_header
            
            logger.debug("vLLM request: url=%s, model=%s", self.llm_url, self.model_path)
            
            response = requests.post(
                self.llm_url,
                json=payload,
                headers=headers,
                timeout=60
            )
            response.raise_for_status()
            
            result_data = response.json()
            logger.debug("vLLM response received: status=%d", response.status_code)
            
            # Extract completion from response
            completion = result_data["choices"][0]["message"]["content"]
            usage = result_data.get("usage", {})
            
            # Extract detected issues
            detected_issues = await self.extract_issues(completion)
            
            processing_time = (time.time() - start_time) * 1000
            
            logger.info("vLLM detection completed: issues=%d, time=%.2fms",
                       len(detected_issues), processing_time)
            
            return {
                "detected_issues": detected_issues,
                "confidence": 0.85,  # vLLM doesn't provide confidence, use default
                "raw_response": completion,
                "tokens_used": usage.get("completion_tokens", 0),
                "model_used": self.model_path,
                "processing_time_ms": int(processing_time),
                "strategy": "vllm"
            }
        
        except requests.exceptions.RequestException as e:
            logger.exception("vLLM API call failed: %s", e)
            raise RuntimeError(f"vLLM detection failed: {str(e)}")
        except (KeyError, IndexError) as e:
            logger.exception("vLLM response parsing failed: %s", e)
            raise RuntimeError(f"Failed to parse vLLM response: {str(e)}")
