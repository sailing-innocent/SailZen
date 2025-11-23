# -*- coding: utf-8 -*-
# @file llm_service.py
# @brief Real LLM service with DeepSeek API integration

import httpx
import json
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

from server.utils.prompt import PromptManager

logger = logging.getLogger(__name__)


class LLMService:
    """Service for calling LLM APIs (DeepSeek, OpenAI-compatible)"""

    def __init__(
        self,
        api_key: str,
        endpoint: str = "https://api.deepseek.com/v1",
        model: str = "deepseek-chat",
        temperature: float = 0.3,
        max_tokens: int = 4096,
        timeout: float = 60.0,
        max_retries: int = 3,
    ):
        self.api_key = api_key
        self.endpoint = endpoint
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.max_retries = max_retries

        # Initialize HTTP client
        self.client = httpx.AsyncClient(
            base_url=endpoint,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(timeout),
        )

        # Initialize prompt manager
        prompts_dir = Path(__file__).parent.parent / "prompts"
        self.prompt_manager = PromptManager(prompts_dir)

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()

    async def call_llm(
        self,
        system_message: str,
        user_message: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Call LLM API with retry logic

        Args:
            system_message: System prompt
            user_message: User message
            temperature: Override temperature
            max_tokens: Override max tokens

        Returns:
            LLM response text
        """
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ]

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature or self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
        }

        last_error = None
        for attempt in range(self.max_retries):
            try:
                logger.info(f"LLM API call attempt {attempt + 1}/{self.max_retries}")
                response = await self.client.post("/chat/completions", json=payload)
                response.raise_for_status()

                data = response.json()
                content = data["choices"][0]["message"]["content"]

                # Log token usage if available
                if "usage" in data:
                    usage = data["usage"]
                    logger.info(f"LLM tokens: {usage.get('total_tokens', 'N/A')}")

                return content

            except httpx.HTTPStatusError as e:
                logger.error(
                    f"HTTP error on attempt {attempt + 1}: {e.response.status_code} - {e.response.text}"
                )
                last_error = e
                if e.response.status_code == 429:  # Rate limit
                    # Exponential backoff for rate limits
                    await httpx.AsyncClient().aclose()  # Dummy await for backoff
                    continue
                elif e.response.status_code >= 500:  # Server error
                    continue
                else:
                    # Client error (400, 401, etc.) - don't retry
                    raise

            except (httpx.TimeoutException, httpx.ConnectError) as e:
                logger.error(f"Network error on attempt {attempt + 1}: {e}")
                last_error = e
                continue

            except Exception as e:
                logger.error(f"Unexpected error on attempt {attempt + 1}: {e}")
                last_error = e
                raise

        # All retries failed
        raise Exception(
            f"LLM API call failed after {self.max_retries} attempts: {last_error}"
        )

    def parse_json_response(self, response: str) -> Any:
        """Parse JSON from LLM response, handling markdown code blocks

        Args:
            response: Raw LLM response

        Returns:
            Parsed JSON object
        """
        # Try direct JSON parse first
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Try to extract JSON from markdown code blocks
        lines = response.strip().split("\n")
        json_lines = []
        in_code_block = False

        for line in lines:
            if line.strip().startswith("```"):
                if not in_code_block:
                    in_code_block = True
                else:
                    in_code_block = False
                continue

            if in_code_block or (not line.strip().startswith("```")):
                json_lines.append(line)

        json_text = "\n".join(json_lines).strip()

        try:
            return json.loads(json_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from LLM response: {e}")
            logger.error(f"Response text: {response[:500]}...")
            raise ValueError(f"Could not parse JSON from LLM response: {e}")

    async def extract_entities(
        self, text: str, context: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Extract entities from text using LLM

        Args:
            text: Text to analyze
            context: Optional context from surrounding text

        Returns:
            List of entity dicts with keys: canonical_name, entity_type, aliases, first_mention_text, confidence
        """
        # Render prompt template
        messages = self.prompt_manager.render(
            "entity_extraction", text=text, context=context or ""
        )

        # Call LLM
        response = await self.call_llm(
            system_message=messages["system"], user_message=messages["user"]
        )

        # Parse response
        entities = self.parse_json_response(response)

        if not isinstance(entities, list):
            logger.warning(f"LLM returned non-list response: {type(entities)}")
            return []

        # Validate and normalize entities
        normalized = []
        for entity in entities:
            if not isinstance(entity, dict):
                continue

            if "canonical_name" not in entity or "entity_type" not in entity:
                logger.warning(f"Skipping malformed entity: {entity}")
                continue

            # Ensure required fields
            normalized_entity = {
                "canonical_name": str(entity["canonical_name"]),
                "entity_type": str(entity["entity_type"]),
                "aliases": entity.get("aliases", []),
                "first_mention_text": entity.get("first_mention_text", ""),
                "confidence": float(entity.get("confidence", 0.8)),
            }

            normalized.append(normalized_entity)

        logger.info(
            f"Extracted {len(normalized)} entities from text ({len(text)} chars)"
        )
        return normalized


# Global LLM service instance (to be initialized in main.py)
_llm_service: Optional[LLMService] = None


def init_llm_service(
    api_key: str,
    endpoint: str = "https://api.deepseek.com/v1",
    model: str = "deepseek-chat",
    **kwargs,
) -> LLMService:
    """Initialize global LLM service instance"""
    global _llm_service
    _llm_service = LLMService(api_key=api_key, endpoint=endpoint, model=model, **kwargs)
    return _llm_service


def get_llm_service() -> LLMService:
    """Get global LLM service instance"""
    if _llm_service is None:
        raise RuntimeError(
            "LLM service not initialized. Call init_llm_service() first."
        )
    return _llm_service
