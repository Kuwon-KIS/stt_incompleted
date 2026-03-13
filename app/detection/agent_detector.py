"""
AI Agent-based implementation of the detection strategy.
Uses direct user input without prompt templates.
"""

import logging
import requests
import time
from typing import Dict, Any
from .base import DetectionStrategy

logger = logging.getLogger(__name__)


class AgentDetector(DetectionStrategy):
    """Detection strategy using AI Agent API with direct user input.
    
    Characteristics:
    - Uses agent_name to identify the specific agent
    - Direct user input without template formatting
    - Supports streaming responses
    - Requires AGENT_NAME and LLM_URL configuration
    """
    
    def __init__(self, config):
        """
        Initialize AI Agent detector.
        
        Args:
            config: Application configuration object
        """
        self.config = config
        self.agent_name = config.AGENT_NAME
        self.llm_url = config.LLM_URL
        self.auth_header = config.LLM_AUTH_HEADER
        self.use_streaming = config.USE_STREAMING
    
    def validate_config(self) -> bool:
        """Validate required Agent configuration."""
        if not self.agent_name:
            raise ValueError("AGENT_NAME is required for Agent detector")
        if not self.llm_url:
            raise ValueError("LLM_URL is required for Agent detector")
        return True
    
    async def detect(self, text: str, prompt: str) -> Dict[str, Any]:
        """
        Detect incomplete sales elements using AI Agent API.
        
        Args:
            text: Main content to analyze
            prompt: User query/prompt (used directly)
            
        Returns:
            Detection result dictionary
        """
        self.validate_config()
        
        logger.info("Agent detection starting: agent=%s, use_streaming=%s",
                   self.agent_name, self.use_streaming)
        
        start_time = time.time()
        
        try:
            # Call Agent API
            # Note: Adjust endpoint based on actual Agent API format
            agent_endpoint = f"{self.llm_url}/{self.agent_name}/messages"
            
            payload = {
                "parameters": {
                    "user_query": prompt,
                    "context": text
                },
                "use_streaming": self.use_streaming
            }
            
            headers = {
                "Content-Type": "application/json"
            }
            if self.auth_header:
                headers["Authorization"] = self.auth_header
            
            logger.debug("Agent request: url=%s, agent=%s", agent_endpoint, self.agent_name)
            
            response = requests.post(
                agent_endpoint,
                json=payload,
                headers=headers,
                timeout=60
            )
            response.raise_for_status()
            
            result_data = response.json()
            logger.debug("Agent response received: status=%d", response.status_code)
            
            # Extract result from response
            # Note: Adjust based on actual Agent response format
            completion = result_data.get("result", "")
            
            # Extract detected issues
            detected_issues = await self.extract_issues(completion)
            
            processing_time = (time.time() - start_time) * 1000
            
            logger.info("Agent detection completed: agent=%s, issues=%d, time=%.2fms",
                       self.agent_name, len(detected_issues), processing_time)
            
            return {
                "detected_issues": detected_issues,
                "confidence": 0.80,  # Agent doesn't provide confidence, use default
                "raw_response": completion,
                "tokens_used": 0,  # Agent API may not provide token count
                "model_used": self.agent_name,
                "processing_time_ms": int(processing_time),
                "strategy": "agent"
            }
        
        except requests.exceptions.RequestException as e:
            logger.exception("Agent API call failed: %s", e)
            raise RuntimeError(f"Agent detection failed: {str(e)}")
        except (KeyError, IndexError) as e:
            logger.exception("Agent response parsing failed: %s", e)
            raise RuntimeError(f"Failed to parse Agent response: {str(e)}")
