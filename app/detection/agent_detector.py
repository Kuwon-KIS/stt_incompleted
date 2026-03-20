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
    
    async def extract_issues(self, agent_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract detected issues from normalized Agent result in structured format.
        
        Args:
            agent_result: Normalized Agent result dict with omission fields
            
        Returns:
            List of issue dictionaries with structured format
        """
        try:
            # Extract omission information
            omission_steps = agent_result.get("omission_steps", [])
            omission_reasons = agent_result.get("omission_reasons", [])
            omission_num_raw = agent_result.get("omission_num", 0)
            try:
                if omission_num_raw is None or str(omission_num_raw).strip() == "None":
                    omission_num = 0
                else:
                    omission_num = int(omission_num_raw)
            except (TypeError, ValueError):
                omission_num = 0
            
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

            if omission_num != len(issues):
                logger.debug("omission_num (%d) differs from extracted issues (%d)", omission_num, len(issues))
            
            logger.debug("Extracted %d issues from Agent response", len(issues))
            return issues
        except Exception as e:
            logger.exception("Error extracting issues from Agent response: %s", e)
            return [{"error": "extraction_error", "details": str(e)}]

    def _normalize_agent_result(self, result_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize response payload to a single agent result dict.

        Supports mock format ({"result": "...json..."}) and on-prem nested answer format.
        """
        if "result" in result_data:
            completion = result_data.get("result", "")
            if not completion:
                return {}
            try:
                return json.loads(completion)
            except (json.JSONDecodeError, TypeError):
                logger.warning("Mock result is not valid JSON")
                return {}

        agent_data: Any = result_data
        if "answer" in agent_data and isinstance(agent_data["answer"], dict):
            if "answer" in agent_data["answer"]:
                agent_data = agent_data["answer"]["answer"]

        if isinstance(agent_data, str):
            try:
                agent_data = json.loads(agent_data)
                logger.debug("Parsed nested answer as JSON string")
            except (json.JSONDecodeError, TypeError):
                logger.warning("Nested answer is a string but not valid JSON")
                return {}

        if not isinstance(agent_data, dict):
            logger.warning("Agent response normalized to non-dict type")
            return {}

        return agent_data
    
    async def detect(self, text: str, prompt: str) -> Dict[str, Any]:
        """
        Detect incomplete sales elements using AI Agent API.
        
        Args:
            text: Main content (kept for interface compatibility)
            prompt: User query used as Agent input
            
        Returns:
            Detection result dictionary
        """
        self.validate_config()
        
        logger.debug("Agent detection starting: agent=%s, use_streaming=%s",
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
            
            # Memo format: Agent receives only chat_thread_id + parameters.user_query.
            user_query = prompt if prompt is not None else ""
            payload = {
                "chat_thread_id": "",
                "parameters": {
                    "user_query": user_query
                }
            }
            
            headers = {
                "Content-Type": "application/json"
            }
            if self.auth_header:
                headers["Authorization"] = self.auth_header
            
            logger.debug(
                "Agent request: url=%s, agent=%s, user_query_len=%d",
                agent_endpoint,
                self.agent_name,
                len(str(user_query))
            )
            
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
            
            completion = result_data.get("result", "") if "result" in result_data else json.dumps(result_data)
            agent_data = self._normalize_agent_result(result_data)
            
            logger.debug("Agent response format: %s", "mock" if "result" in result_data else "on-prem")
            
            # Extract detected issues
            detected_issues = await self.extract_issues(agent_data)
            
            processing_time = (time.time() - start_time) * 1000
            
            logger.debug("Agent detection completed: agent=%s, issues=%d, time=%.2fms",
                        self.agent_name, len(detected_issues), processing_time)
            
            # Ensure omission_num is a valid integer, handle None and "None" string
            omission_num_raw = agent_data.get("omission_num")
            omission_num = 0
            if omission_num_raw is not None and str(omission_num_raw).strip() != "None":
                try:
                    omission_num = int(omission_num_raw)
                except (ValueError, TypeError):
                    logger.debug("Could not convert omission_num to int: %s", omission_num_raw)
                    omission_num = 0
            
            return {
                "detected_issues": detected_issues,
                "category": agent_data.get("category"),
                "summary": agent_data.get("summary"),
                "omission_num": omission_num,
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
