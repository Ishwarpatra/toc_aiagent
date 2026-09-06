"""
Vision and LLM Providers for Neuro-Symbolic DFA Image Recognition.

Provides unified abstractions for multimodality (VLM) calls across:
- Google Gemini API
- OpenRouter API
- Mock/Offline Fallbacks
"""

import os
import json
import base64
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class VisionProvider(ABC):
    """Abstract Base Class for Vision-Language model providers."""

    @abstractmethod
    def get_models(self) -> List[str]:
        """Fetch available vision models from the provider in priority order."""
        pass

    @abstractmethod
    def call(self, model: str, system_prompt: str, user_text: str, image_b64: str) -> Dict[str, Any]:
        """Make a multimodal API call and return the parsed JSON dictionary."""
        pass

    @abstractmethod
    def is_rate_limit_daily(self, error: Exception) -> bool:
        """Check if the error corresponds to a rate/quota exhaustion."""
        pass


class GeminiProvider(VisionProvider):
    """Google Gemini vision provider."""

    def __init__(self, api_key: str):
        import google.generativeai as genai
        self.api_key = api_key
        genai.configure(api_key=api_key)
        self.genai = genai

    def get_models(self) -> List[str]:
        return [
            "models/gemini-2.5-flash",
            "models/gemini-2.0-flash",
            "models/gemini-flash-latest",
            "models/gemini-2.5-pro",
        ]

    def call(self, model: str, system_prompt: str, user_text: str, image_b64: str) -> Dict[str, Any]:
        m = self.genai.GenerativeModel(
            model_name=model,
            system_instruction=system_prompt
        )
        img_data = base64.b64decode(image_b64)
        response = m.generate_content(
            [user_text, {"mime_type": "image/jpeg", "data": img_data}],
            generation_config={"response_mime_type": "application/json"}
        )
        text = response.text.strip()
        # Clean potential markdown formatting
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return json.loads(text.strip())

    def is_rate_limit_daily(self, error: Exception) -> bool:
        msg = str(error).lower()
        return "429" in msg or "quota" in msg or "limit" in msg


class OpenRouterProvider(VisionProvider):
    """OpenRouter vision provider for multi-model access."""

    def __init__(self, api_key: str):
        from openai import OpenAI
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )

    def get_models(self) -> List[str]:
        return [
            "google/gemini-2.0-flash-exp:free",
            "google/gemma-3-27b-it:free",
            "openai/gpt-4o",
        ]

    def call(self, model: str, system_prompt: str, user_text: str, image_b64: str) -> Dict[str, Any]:
        response = self.client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": "https://autodfa.local",
                "X-Title": "Auto-DFA Vision Engine",
            },
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_text},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                    ],
                },
            ],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        return json.loads(content.strip())

    def is_rate_limit_daily(self, error: Exception) -> bool:
        msg = str(error).lower()
        return "429" in msg or "402" in msg or "limit" in msg or "quota" in msg
