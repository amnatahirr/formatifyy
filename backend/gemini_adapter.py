"""
gemini_adapter.py — Google Gemini client adapter for Formatify.

Emulates the Anthropic AsyncAnthropic client API so the 6 analysis functions 
can remain unchanged while running all checks on gemini-2.5-flash (free tier).
"""

from __future__ import annotations

import base64
import asyncio
from typing import Any, List, Dict, Optional
import google.generativeai as genai

class GeminiClientAdapter:
    """
    Adapter emulating `anthropic.AsyncAnthropic` using `google-generativeai`.
    """
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.messages = self.Messages()

    class Messages:
        """Emulates the `messages` attribute on the Anthropic client."""
        
        async def create(
            self,
            model: str,
            max_tokens: int,
            messages: List[Dict[str, Any]],
            **kwargs,
        ) -> "GeminiResponse":
            """
            Emulates the `client.messages.create` method.
            Maps all input model names to "gemini-2.5-flash" (almost free tier).
            """
            contents: List[Any] = []
            prompt_text = ""

            for msg in messages:
                content_val = msg.get("content")
                if isinstance(content_val, str):
                    contents.append(content_val)
                    prompt_text += content_val
                elif isinstance(content_val, list):
                    for item in content_val:
                        if item.get("type") == "text":
                            txt = item.get("text", "")
                            contents.append(txt)
                            prompt_text += txt
                        elif item.get("type") == "image":
                            source = item.get("source", {})
                            b64_data = source.get("data", "")
                            mime_type = source.get("media_type", "image/png")
                            if b64_data:
                                img_bytes = base64.b64decode(b64_data)
                                contents.append({
                                    "mime_type": mime_type,
                                    "data": img_bytes
                                })

            # Determine response mime type based on prompt requirement
            response_mime_type = "text/plain"
            if "json" in prompt_text.lower():
                response_mime_type = "application/json"

            gemini_model = "gemini-2.5-flash"
            model_obj = genai.GenerativeModel(gemini_model)

            config = genai.GenerationConfig(
                max_output_tokens=max_tokens,
                response_mime_type=response_mime_type
            )

            # Generate content asynchronously using the native SDK method
            response = await model_obj.generate_content_async(
                contents,
                generation_config=config
            )

            text_result = response.text or "{}"
            return GeminiResponse(text_result)


class GeminiResponse:
    """Emulates Anthropic API response wrapper."""
    def __init__(self, text: str):
        self.content = [GeminiContentBlock(text)]


class GeminiContentBlock:
    """Emulates Anthropic content block."""
    def __init__(self, text: str):
        self.text = text
