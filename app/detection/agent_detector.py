"""
AI Agent-based implementation of the detection strategy.
Uses direct user input without prompt templates.
"""

import logging
import requests
import time
import json
import asyncio
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
           { category, summary, omission_num, omission_steps, omission_reasons }
        
        2. Nested format (actual Agent API):
           { message_id, chat_thread_id, answer: { answer: { category, summary, ... } } }
           또는 answer.answer가 JSON 문자열일 수도 있음
        
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
            
            # Handle case where agent_result might be a JSON string (double-nested)
            if isinstance(agent_result, str):
                try:
                    agent_result = json.loads(agent_result)
                    logger.debug("Parsed double-nested JSON string in agent_result")
                except (json.JSONDecodeError, TypeError):
                    logger.warning("agent_result is a string but not valid JSON: %s", agent_result[:100])
                    return [{"error": "invalid_format", "details": "agent_result is a string but not JSON"}]
            
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
                    "category": agent_result.get("category", "unknown")
                })
            
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
            # Determine endpoint format based on whether it's Mock or Real agent
            # Mock agent: AGENT_URL is base URL, append agent_name and /messages
            # Real agent: AGENT_URL is complete endpoint, use as-is
            if "/mock/agent" in self.agent_url.lower():
                # Mock agent format: base URL + agent_name + /messages
                agent_endpoint = f"{self.agent_url}/{self.agent_name}/messages"
                logger.debug("Using Mock agent endpoint format")
            else:
                # Real agent format: complete endpoint URL
                agent_endpoint = self.agent_url
                logger.debug("Using Real agent endpoint format")
            
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
            
            # Execute requests.post() in executor to avoid blocking event loop
            # Using a wrapper function to properly pass keyword arguments
            def make_agent_request():
                return requests.post(
                    agent_endpoint,
                    json=payload,
                    headers=headers,
                    timeout=60
                )
            
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, make_agent_request)
            response.raise_for_status()
            
            result_data = response.json()
            logger.debug("Agent response received: status=%d", response.status_code)
            
            # Handle two response formats:
            # 1. Mock format: {"result": "{...json string...}"}
            # 2. On-prem format: {"message_id": "...", "chat_thread_id": "...", "answer": {...}}
            
            if "result" in result_data:
                # Mock/agent format: result is a JSON string
                completion = result_data.get("result", "")
                try:
                    agent_data = json.loads(completion) if completion else {}
                except (json.JSONDecodeError, TypeError):
                    agent_data = {}
            else:
                # On-prem format: direct response structure
                agent_data = result_data
                completion = json.dumps(result_data)
            
            logger.debug("Agent response format: %s", "mock" if "result" in result_data else "on-prem")
            
            # Extract detected issues
            detected_issues = await self.extract_issues(completion)
            
            # Navigate nested structure if exists (for mock format)
            if "answer" in agent_data and isinstance(agent_data["answer"], dict):
                if "answer" in agent_data["answer"]:
                    agent_data = agent_data["answer"]["answer"]
                    # Handle case where nested answer is a JSON string
                    if isinstance(agent_data, str):
                        try:
                            agent_data = json.loads(agent_data)
                            logger.debug("Parsed nested answer as JSON string")
                        except (json.JSONDecodeError, TypeError):
                            logger.warning("Nested answer is a string but not valid JSON: %s", agent_data[:100])
                            agent_data = {}
            
            processing_time = (time.time() - start_time) * 1000
            
            logger.info("Agent detection completed: agent=%s, issues=%d, time=%.2fms",
                       self.agent_name, len(detected_issues), processing_time)
            
            return {
                "detected_issues": detected_issues,
                "category": agent_data.get("category"),
                "summary": agent_data.get("summary"),
                "omission_num": agent_data.get("omission_num"),
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
