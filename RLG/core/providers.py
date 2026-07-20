import os
import time
import json
import base64
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class VisionProvider(ABC):
    @abstractmethod
    def get_models(self) -> List[str]:
        """Fetch available vision models from the provider."""
        pass

    @abstractmethod
    def call(self, model: str, system_prompt: str, user_text: str, image_b64: str) -> Dict[str, Any]:
        """Make an API call to the provider."""
        pass

    @abstractmethod
    def is_rate_limit_daily(self, error: Exception) -> bool:
        """Check if the error is a daily quota limit (exhausted for the day)."""
        pass

class GeminiProvider(VisionProvider):
    def __init__(self, api_key: str):
        import google.generativeai as genai
        self.api_key = api_key
        genai.configure(api_key=api_key)
        self.genai = genai

    def get_models(self) -> List[str]:
        """
        Settling for the user-defined architecture with exact API strings:
        PRIMARY: gemini-flash-lite-latest, gemini-flash-latest, gemini-2.0-flash-lite, gemini-2.5-flash-lite
        SECONDARY: gemini-2.0-flash, gemini-2.5-flash
        FALLBACK: gemini-2.5-pro
        """
        return [
            "models/gemini-flash-lite-latest",       # Primary 1.5 Flash-lite
            "models/gemini-flash-latest",            # Primary 1.5 Flash
            "models/gemini-2.0-flash-lite",          # Primary 2.0 Flash-lite
            "models/gemini-2.5-flash-lite",          # Primary 2.5 Flash-lite
            "models/gemini-2.0-flash",               # Secondary 2.0
            "models/gemini-2.5-flash",               # Secondary 2.5
            "models/gemini-2.5-pro"                  # Fallback 2.5 Pro
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
        return json.loads(response.text)

    def is_rate_limit_daily(self, error: Exception) -> bool:
        msg = str(error).lower()
        return "429" in msg or "quota" in msg or "limit" in msg

class OpenRouterProvider(VisionProvider):
    def __init__(self, api_key: str):
        from openai import OpenAI
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )

    def get_models(self) -> List[str]:
        """
        FAILSAFE hierarchy with updated verified slugs:
        - google/gemma-3-27b-it:free (Verified Vision)
        - nvidia/nemotron-nano-12b-v2-vl:free (Verified Vision)
        - openai/gpt-4o (Paid)
        - google/gemini-2.0-flash-exp:free (Failsafe)
        """
        return [
            "google/gemma-3-27b-it:free",
            "nvidia/nemotron-nano-12b-v2-vl:free",
            "google/gemini-2.0-flash-exp:free",
            "openai/gpt-4o"
        ]

    def call(self, model: str, system_prompt: str, user_text: str, image_b64: str) -> Dict[str, Any]:
        response = self.client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": "https://dfa-scan.local",
                "X-Title": "DFA Image Scan",
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
        content = response.choices[0].message.content or ""
        return json.loads(content)

    def is_rate_limit_daily(self, error: Exception) -> bool:
        msg = str(error).lower()
        # 429 = Rate/Quota, 402 = Insufficient Credits
        return "429" in msg or "402" in msg or "limit" in msg or "quota" in msg
