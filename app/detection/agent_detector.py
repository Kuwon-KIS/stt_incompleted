"""
AI Agent-based implementation of the detection strategy.
Uses direct user input without prompt templates.
"""

import logging
import requests
import time
import json
from typing import Dict, Any, List
from .base import DetectionStrategy

logger = logging.getLogger(__name__)


class AgentDetector(DetectionStrategy):
    """Detection strategy using AI Agent API with direct user input.
    
    Characteristics:
    - Uses agent_name to identify the specific agent
    - Direct user input without template formatting
    - Supports streaming responses
    - Requires AGENT_NAME, AGENT_URL, and AGENT_AUTH_HEADER configuration
    """
    
    def __init__(self, config):
        """
        Initialize AI Agent detector.
        
        Args:
            config: Application configuration object
        """
        self.config = config
        self.agent_name = config.AGENT_NAME
        self.agent_url = config.AGENT_URL
        self.auth_header = config.AGENT_AUTH_HEADER
        self.use_streaming = config.USE_STREAMING
    
    def validate_config(self) -> bool:
        """Validate required Agent configuration."""
        if not self.agent_name:
            raise ValueError("AGENT_NAME is required for Agent detector")
        if not self.agent_url:
            raise ValueError("AGENT_URL is required for Agent detector")
        return True
    
    async def extract_issues(self, response: str) -> List[Dict[str, Any]]:
        """
        Extract detected issues from Agent response in structured format.
        
        Agent response can have two formats:
        1. Simple format (direct output):
           { category, summary, omission_num, omission_steps, omission_reasons, reason }
        
        2. Nested format (actual Agent API):
           { message_id, chat_thread_id, answer: { answer: { category, summary, ... } } }
        
        Args:
            response: JSON string from Agent API
            
        Returns:
            List of issue dictionaries with structured format
        """
        try:
            # Parse Agent response as JSON
            agent_response = json.loads(response)
            
            # Try to extract the actual data from nested structure first
            agent_result = agent_response
            
            # Check if response has nested answer structure
            if "answer" in agent_response and isinstance(agent_response["answer"], dict):
                if "answer" in agent_response["answer"]:
                    agent_result = agent_response["answer"]["answer"]
                    logger.debug("Extracted nested Agent response format")
            
            # Extract omission information
            omission_steps = agent_result.get("omission_steps", [])
            omission_reasons = agent_result.get("omission_reasons", [])
            omission_num = int(agent_result.get("omission_num", "0"))
            
            # Validate that steps and reasons are paired
            if len(omission_steps) != len(omission_reasons):
                logger.warning("Mismatch between omission_steps (%d) and omission_reasons (%d)",
                              len(omission_steps), len(omission_reasons))
            
            # Create issue list pairing steps with reasons
            issues = []
            for i, (step, reason) in enumerate(zip(omission_steps, omission_reasons)):
                issues.append({
                    "index": i,
                    "step": step,
                    "reason": reason,
                    "category": agent_result.get("category", "unknown"),
                    "summary": agent_result.get("summary", ""),
                    "severity": "high" if i < omission_num else "medium"
                })
            
            # Add root reason to each issue if exists
            if "reason" in agent_result and agent_result["reason"]:
                for issue in issues:
                    issue["root_reason"] = agent_result["reason"]
            
            logger.debug("Extracted %d issues from Agent response", len(issues))
            return issues
            
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse Agent response as JSON: %s. Returning error.", e)
            return [{"error": "parse_error", "details": str(e), "raw_response": response[:200]}]
        except Exception as e:
            logger.exception("Error extracting issues from Agent response: %s", e)
            return [{"error": "extraction_error", "details": str(e)}]
    
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
            # Agent endpoint format: {AGENT_URL}/{agent_name}/messages
            agent_endpoint = f"{self.agent_url}/{self.agent_name}/messages"
            
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
