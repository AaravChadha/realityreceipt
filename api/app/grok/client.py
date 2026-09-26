"""HTTPS client for xAI chat completions that return JSON."""

from __future__ import annotations

import base64
import io
import json
import os
import re
from pathlib import Path

import httpx
from dotenv import load_dotenv
from PIL import Image, ImageOps

_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
_CHAT_URL = "https://api.x.ai/v1/chat/completions"
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)
MAX_SIDE_PX = 1600
JPEG_QUALITY = 85


def shrink_jpeg(image: bytes, max_side: int = MAX_SIDE_PX) -> bytes:
    """Any JPEG or PNG in, a JPEG no larger than `max_side` on its long edge out."""
    with Image.open(io.BytesIO(image)) as img:
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")
        img.thumbnail((max_side, max_side))
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=JPEG_QUALITY)
        return out.getvalue()


class GrokClient:
    """Reads `XAI_API_KEY` and `XAI_MODEL` from `api/.env`. `XAI_MODEL` should be a
    non-reasoning vision model with structured outputs (grok-4.20-0309-non-reasoning)."""

    def __init__(self) -> None:
        load_dotenv(_ENV_PATH)
        key = os.getenv("XAI_API_KEY", "").strip()
        model = os.getenv("XAI_MODEL", "").strip()
        if not key:
            raise RuntimeError("XAI_API_KEY is missing in api/.env")
        if not model:
            raise RuntimeError("XAI_MODEL is missing in api/.env")
        self._api_key = key
        self.model = model

    def build_payload(
        self,
        system: str,
        user: str,
        image_jpeg: bytes | None = None,
        schema: dict | None = None,
    ) -> dict:
        content: list[dict] = [{"type": "text", "text": user}]
        if image_jpeg is not None:
            b64 = base64.b64encode(shrink_jpeg(image_jpeg)).decode("ascii")
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "high"},
                }
            )
        payload: dict = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
            "temperature": 0,
        }
        if schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "extraction", "schema": schema, "strict": True},
            }
        else:
            payload["response_format"] = {"type": "json_object"}
        return payload

    def chat_json(
        self,
        system: str,
        user: str,
        image_jpeg: bytes | None = None,
        schema: dict | None = None,
    ) -> dict:
        payload = self.build_payload(system, user, image_jpeg, schema)
        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
        with httpx.Client(timeout=60.0) as client:
            response = client.post(_CHAT_URL, headers=headers, json=payload)
            response.raise_for_status()
            body = response.json()
        text = body["choices"][0]["message"]["content"]
        if not isinstance(text, str):
            raise ValueError("Grok response content is not a string")
        parsed = json.loads(_FENCE.sub("", text.strip()).strip())
        if not isinstance(parsed, dict):
            raise ValueError("Grok JSON root must be an object")
        return parsed
