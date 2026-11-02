"""Client for a local OpenAI-compatible model server (LM Studio, Ollama or vLLM).

Two safety properties, as in alberta-lmp-lab and claims-fraud-mlops: the endpoint must be on this machine, so RFP text never
leaves it, and every caller has an offline path, so the pipeline still runs when no model server is up.
"""

from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import urlparse

import httpx

DEFAULT_BASE = "http://127.0.0.1:1234/v1"
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1", "host.docker.internal"}
CHAT_PREFERENCE = ["qwen2.5-3b-instruct", "qwen2.5-7b-instruct", "llama-3.2-3b-instruct"]
NO_THINK = " /no_think"


class LLMUnavailable(RuntimeError):
    """No local model server, no chat model loaded, or the model returned nothing usable."""


class SchemaUnsupported(LLMUnavailable):
    """The server answered HTTP 400 to a request carrying `response_format`."""


def assert_local(base: str) -> str:
    parsed = urlparse(base)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Unsupported LLM URL scheme: {parsed.scheme!r}")
    if (parsed.hostname or "") not in LOCAL_HOSTS:
        raise ValueError(f"Refusing non-local inference host: {parsed.hostname}. RFP text must stay on this machine.")
    return base.rstrip("/")


def disabled() -> bool:
    return os.environ.get("RFPX_NO_LLM", "").strip() not in ("", "0", "false")


def strip_think(text: str) -> str:
    """Reasoning models wrap their thinking in <think> tags; only what follows is the answer."""
    text = re.sub(r"(?is)<think>.*?</think>", "", text)
    return text.split("</think>")[-1].replace("<think>", "").strip()


class LocalLLM:
    def __init__(self, base: str | None = None, model: str | None = None, timeout: float = 900.0,
                 client: httpx.Client | None = None):
        self.base = assert_local(base or os.environ.get("LLM_BASE_URL") or DEFAULT_BASE)
        self._model = model
        self._timeout = timeout
        self._client = client or httpx.Client(follow_redirects=False)

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None, timeout: float = 10.0) -> dict[str, Any]:
        if disabled():
            raise LLMUnavailable("LLM calls are disabled (RFPX_NO_LLM)")
        try:
            response = self._client.request(method, self.base + path, json=payload, timeout=timeout)
        except httpx.HTTPError as error:
            raise LLMUnavailable(f"Local model server not reachable at {self.base}: {error.__class__.__name__}") from error
        if response.status_code == 400 and payload and "response_format" in payload:
            raise SchemaUnsupported(f"Local model server rejected response_format: {response.text[:200]}")
        if response.status_code != 200:
            raise LLMUnavailable(f"Local model server returned HTTP {response.status_code}: {response.text[:200]}")
        return response.json()

    def model(self) -> str:
        if self._model is None:
            ids = [m["id"] for m in self._request("GET", "/models", timeout=3.0).get("data", []) if isinstance(m.get("id"), str)]
            chat = [i for i in ids if "embed" not in i.lower()]
            override = os.environ.get("LLM_CHAT_MODEL")
            self._model = (override if override in chat else None) or next((p for p in CHAT_PREFERENCE if p in chat), None) \
                or (chat[0] if chat else None)
            if not self._model:
                raise LLMUnavailable("No chat model loaded in the local model server")
        return self._model

    def chat(self, messages: list[dict[str, str]], max_tokens: int = 1800, temperature: float = 0.0,
             schema: dict[str, Any] | None = None) -> str:
        model = self.model()
        messages = [dict(m) for m in messages]
        if "qwen3" in model.lower():
            for m in reversed(messages):
                if m["role"] == "user":
                    m["content"] += NO_THINK
                    break
        payload: dict[str, Any] = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
        if schema is not None:
            payload["response_format"] = {"type": "json_schema", "json_schema": {"name": "rfp_questions", "strict": True, "schema": schema}}
        data = self._request("POST", "/chat/completions", payload, self._timeout)
        text = strip_think(((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "")
        if not text:
            raise LLMUnavailable("The model returned an empty answer")
        return text

    def status(self) -> dict[str, Any]:
        try:
            return {"endpoint": self.base, "ready": True, "model": self.model()}
        except LLMUnavailable as error:
            return {"endpoint": self.base, "ready": False, "model": None, "reason": str(error)}
