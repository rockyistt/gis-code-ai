#!/usr/bin/env python3
"""llama.cpp server predictor for local GGUF deployment.

This wrapper talks to a running llama.cpp server instead of loading model
weights inside the Python process. It is designed for CPU-friendly GGUF models.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Dict, Optional


class LlamaCppServerPredictor:
    """Predict GIS step JSON through a local llama.cpp HTTP server."""

    SYSTEM_PROMPT = (
        "You are a GIS step instruction parser. "
        "Given a natural language instruction, output a JSON object "
        "describing the corresponding GIS step."
    )

    def __init__(
        self,
        server_url: str = "http://127.0.0.1:8080",
        max_tokens: int = 512,
        temperature: float = 0.0,
        top_p: float = 1.0,
        timeout_seconds: int = 120,
    ):
        self.server_url = server_url.rstrip("/")
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.top_p = top_p
        self.timeout_seconds = timeout_seconds
        self.last_completion = ""

    def predict_step(
        self,
        instruction: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        prompt = self._format_prompt(instruction)
        text = self._completion(
            prompt=prompt,
            max_tokens=max_tokens or self.max_tokens,
            temperature=self.temperature if temperature is None else temperature,
            top_p=self.top_p if top_p is None else top_p,
        )
        self.last_completion = text
        return self._extract_json(text)

    def health_check(self) -> bool:
        try:
            with urllib.request.urlopen(
                f"{self.server_url}/health",
                timeout=10,
            ) as response:
                return 200 <= response.status < 500
        except Exception:
            return False

    def _completion(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        top_p: float,
    ) -> str:
        payload = {
            "prompt": prompt,
            "n_predict": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "stream": False,
            "json_schema": {},
        }
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.server_url}/completion",
            data=data,
            headers={"Content-Type": "application/json", "Connection": "close"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"llama.cpp server returned HTTP {exc.code}") from exc

        return body.get("content") or body.get("text") or ""

    @classmethod
    def _format_prompt(cls, instruction: str) -> str:
        return (
            "### System:\n"
            f"{cls.SYSTEM_PROMPT}\n"
            "\n\n"
            f"### Instruction:\n{instruction}\n\n"
            "### Response:\n"
        )

    @staticmethod
    def _extract_json(text: str) -> Optional[Dict[str, Any]]:
        text = (text or "").strip()
        first_brace_idx = text.find("{")
        if first_brace_idx == -1:
            return None
        text = text[first_brace_idx:]

        end_markers = [
            "\n\n### Instruction:",
            "\n\n###",
            "---",
            "<|endoftext|>",
            "</s>",
        ]
        effective_end_idx = len(text)
        for marker in end_markers:
            marker_idx = text.find(marker)
            if marker_idx != -1 and marker_idx < effective_end_idx:
                effective_end_idx = marker_idx
        text = text[:effective_end_idx].strip()

        balance = 0
        for index, char in enumerate(text):
            if char == "{":
                balance += 1
            elif char == "}":
                balance -= 1
                if balance == 0:
                    candidate = text[: index + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        return None
        return None
