"""HTTPS client for xAI chat completions that return JSON."""

from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path

import httpx
from dotenv import load_dotenv

_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
_CHAT_URL = "https://api.x.ai/v1/chat/completions"
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


class GrokClient:
    """Reads `XAI_API_KEY` and `XAI_MODEL` from `api/.env`."""

    def __init__(self) -> None:
        load_dotenv(_ENV_PATH)
        key = os.getenv("XAI_API_KEY", "").strip()
        model = os.getenv("XAI_MODEL", "").strip()
        if not key:
            raise RuntimeError("XAI_API_KEY is missing in api/.env")
        if not model:
            raise RuntimeError("XAI_MODEL is missing in api/.env")
        self._api_key = key
        self._model = model

    def chat_json(
        self,
        system: str,
        user: str,
        image_jpeg: bytes | None = None,
    ) -> dict:
        content: list[dict] = [{"type": "text", "text": user}]
        if image_jpeg is not None:
            b64 = base64.b64encode(image_jpeg).decode("ascii")
            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{b64}",
                        "detail": "high",
                    },
                }
            )
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
            "temperature": 0,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=60.0) as client:
            response = client.post(_CHAT_URL, headers=headers, json=payload)
            response.raise_for_status()
            body = response.json()
        text = body["choices"][0]["message"]["content"]
        if not isinstance(text, str):
            raise ValueError("Grok response content is not a string")
        cleaned = _FENCE.sub("", text.strip()).strip()
        parsed = json.loads(cleaned)
        if not isinstance(parsed, dict):
            raise ValueError("Grok JSON root must be an object")
        return parsed
