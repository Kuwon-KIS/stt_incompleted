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
            def _to_list(value: Any) -> List[Any]:
                """Convert a mixed value into a list for robust schema handling."""
                if value is None:
                    return []
                if isinstance(value, list):
                    return value
                if isinstance(value, str):
                    stripped = value.strip()
                    if not stripped:
                        return []
                    try:
                        parsed = json.loads(stripped)
                        return parsed if isinstance(parsed, list) else [value]
                    except (json.JSONDecodeError, TypeError):
                        return [value]
                return [value]

            # 1) Prefer explicit detected_issues when provided.
            raw_detected_issues = agent_result.get("detected_issues")
            issues: List[Dict[str, Any]] = []
            for i, issue in enumerate(_to_list(raw_detected_issues)):
                if isinstance(issue, dict):
                    step_value = issue.get("step") or ""
                    reason_value = issue.get("reason") or ""
                    if not str(step_value).strip() and not str(reason_value).strip():
                        continue
                    issues.append({
                        "index": i,
                        "step": step_value,
                        "reason": reason_value,
                        "category": issue.get("category") or agent_result.get("category") or "unknown"
                    })
                else:
                    if not str(issue).strip():
                        continue
                    issues.append({
                        "index": i,
                        "step": str(issue),
                        "reason": "",
                        "category": agent_result.get("category") or "unknown"
                    })

            # 2) Fallback to omission_steps + omission_reasons when detected_issues is missing/empty.
            omission_steps = _to_list(agent_result.get("omission_steps", []))
            omission_reasons = _to_list(agent_result.get("omission_reasons", []))
            omission_num_raw = agent_result.get("omission_num", 0)
            try:
                omission_num = int(omission_num_raw) if omission_num_raw is not None else 0
            except (TypeError, ValueError):
                omission_num = 0
            logger.debug("[extract_issues] omission_num=%s, steps=%d, reasons=%d, detected_issues=%s", 
                        omission_num_raw, len(omission_steps), len(omission_reasons), 
                        type(raw_detected_issues).__name__)

            if not issues:
                if len(omission_steps) != len(omission_reasons):
                    logger.warning(
                        "Mismatch between omission_steps (%d) and omission_reasons (%d)",
                        len(omission_steps),
                        len(omission_reasons)
                    )

                pair_count = max(len(omission_steps), len(omission_reasons))
                for i in range(pair_count):
                    step = omission_steps[i] if i < len(omission_steps) else ""
                    reason = omission_reasons[i] if i < len(omission_reasons) else ""
                    if not str(step).strip() and not str(reason).strip():
                        continue
                    issues.append({
                        "index": i,
                        "step": str(step) if step is not None else "",
                        "reason": str(reason) if reason is not None else "",
                        "category": agent_result.get("category") or "unknown"
                    })

            if omission_num != len(issues):
                logger.debug("[extract_issues] omission_num (%d) differs from issues count (%d)", omission_num, len(issues))
            
            logger.debug("[extract_issues_result] issues=%d, category=%s", len(issues), agent_result.get("category"))
            
            logger.debug("Extracted %d issues from Agent response", len(issues))
            return issues
        except Exception as e:
            logger.exception("Error extracting issues from Agent response: %s", e)
            return [{"error": "extraction_error", "details": str(e)}]

    def _normalize_agent_result(self, result_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize response payload to a single agent result dict.

        Supports mock format ({"result": "...json..."}) and on-prem nested answer format.
        """
        # Step 1: Parse top-level mock payload if present.
        agent_data: Any = result_data
        if "result" in result_data:
            completion = result_data.get("result", "")
            if not completion:
                return {}
            try:
                agent_data = json.loads(completion)
            except (json.JSONDecodeError, TypeError):
                logger.warning("Mock result is not valid JSON")
                return {}

        # Step 2: Repeatedly unwrap nested answer structures.
        # Examples handled:
        # - {"answer": {"answer": {...}}}
        # - {"answer": "{...json...}"}
        # - "{...json...}"
        max_depth = 6
        for _ in range(max_depth):
            if isinstance(agent_data, str):
                try:
                    agent_data = json.loads(agent_data)
                    continue
                except (json.JSONDecodeError, TypeError):
                    logger.warning("Nested answer is a string but not valid JSON")
                    return {}

            if not isinstance(agent_data, dict):
                logger.warning("Agent response normalized to non-dict type")
                return {}

            # Stop when payload already looks like the final analysis object.
            if any(k in agent_data for k in ("omission_num", "omission_steps", "omission_reasons", "detected_issues", "summary", "category")):
                break

            if "answer" in agent_data:
                agent_data = agent_data.get("answer")
                continue

            break

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
            logger.debug(f"Agent responsae raw data: {result_data}")
            
            completion = result_data.get("result", "") if "result" in result_data else json.dumps(result_data)
            agent_data = self._normalize_agent_result(result_data)

            if isinstance(agent_data, dict):
                logger.debug("Normalized agent data keys: %s", sorted(agent_data.keys()))
            else:
                logger.debug("Normalized agent data type: %s", type(agent_data).__name__)
            
            logger.debug("Agent response format: %s", "mock" if "result" in result_data else "on-prem")
            
            # Extract detected issues
            detected_issues = await self.extract_issues(agent_data)
            
            processing_time = (time.time() - start_time) * 1000
            
            logger.debug("Agent detection completed: agent=%s, issues=%d, time=%.2fms",
                        self.agent_name, len(detected_issues), processing_time)
            
            # Keep omission_num consistent with parsed/filtered issues.
            omission_num_raw = agent_data.get("omission_num")
            try:
                omission_num = int(omission_num_raw) if omission_num_raw is not None else 0
            except (TypeError, ValueError):
                omission_num = 0

            if omission_num != len(detected_issues):
                logger.debug(
                    "[detect] Adjusting omission_num from %d to detected_issues count %d",
                    omission_num,
                    len(detected_issues)
                )
                omission_num = len(detected_issues)
            
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
