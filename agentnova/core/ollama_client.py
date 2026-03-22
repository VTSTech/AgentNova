"""
⚛️ AgentNova R00 — Ollama Client
Zero-dependency wrapper around the local Ollama HTTP API.
Uses only Python stdlib (urllib + json) — no pip install required.

Features:
  • Automatic retry with exponential backoff
  • Native tool-calling support detection
  • Cloudflare tunnel timeout handling

Written by VTSTech — https://www.vts-tech.org — https://github.com/VTSTech/AgentNova
"""

from __future__ import annotations

import json
import os
import socket
import time
import urllib.request
import urllib.error
from typing import Any, Iterator

# Import centralized config
from ..config import OLLAMA_BASE_URL as DEFAULT_BASE_URL

# Default timeout: configurable via environment variable
# Cloudflare tunnels have ~100 second timeout, so default to 90s for remote
DEFAULT_TIMEOUT = float(os.environ.get("OLLAMA_TIMEOUT", "600.0"))

# Retry configuration
MAX_RETRIES = int(os.environ.get("OLLAMA_MAX_RETRIES", "3"))
RETRY_DELAY = float(os.environ.get("OLLAMA_RETRY_DELAY", "5.0"))


class OllamaError(Exception):
    """Base exception for Ollama errors."""
    def __init__(self, message: str, is_timeout: bool = False, can_retry: bool = False):
        super().__init__(message)
        self.is_timeout = is_timeout
        self.can_retry = can_retry


class OllamaClient:
    """
    Synchronous interface to the local Ollama server.
    Zero external dependencies — uses only Python stdlib.

    Parameters
    ----------
    base_url : str
        URL of the Ollama server (default: http://localhost:11434)
    timeout : float
        Request timeout in seconds
    """

    def __init__(self, base_url: str = DEFAULT_BASE_URL, timeout: float = DEFAULT_TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # ------------------------------------------------------------------ #
    #  Low-level helpers                                                   #
    # ------------------------------------------------------------------ #

    def _request(self, req: urllib.request.Request, _retry_count: int = 0) -> bytes:
        """
        Execute an HTTP request with exponential-backoff retry on transient errors.
        Returns the raw response bytes. Raises OllamaError on failure.
        """
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            retryable_codes = {502, 503, 504, 524}
            if e.code in retryable_codes and _retry_count < MAX_RETRIES:
                delay = RETRY_DELAY * (2 ** _retry_count)
                label = "Cloudflare tunnel timeout" if e.code == 524 else f"HTTP {e.code}"
                print(f"  ⚠ {label}, retrying in {delay:.1f}s (attempt {_retry_count + 1}/{MAX_RETRIES})...")
                time.sleep(delay)
                return self._request(req, _retry_count + 1)
            if e.code == 524:
                raise OllamaError(
                    f"HTTP 524: Cloudflare tunnel timeout after {MAX_RETRIES} retries. "
                    f"Try: 1) Use a local Ollama instance, 2) Increase OLLAMA_TIMEOUT env var, "
                    f"3) Use a smaller model, or 4) Check your cloudflare tunnel connection.",
                    is_timeout=True, can_retry=True
                ) from e
            raise OllamaError(f"HTTP {e.code}: {body}") from e
        except urllib.error.URLError as e:
            if "timed out" in str(e.reason).lower() and _retry_count < MAX_RETRIES:
                delay = RETRY_DELAY * (2 ** _retry_count)
                print(f"  ⚠ Connection timeout, retrying in {delay:.1f}s (attempt {_retry_count + 1}/{MAX_RETRIES})...")
                time.sleep(delay)
                return self._request(req, _retry_count + 1)
            if "timed out" in str(e.reason).lower():
                raise OllamaError(
                    f"Connection timeout after {MAX_RETRIES} retries. "
                    f"Try increasing OLLAMA_TIMEOUT environment variable (current: {self.timeout}s).",
                    is_timeout=True, can_retry=True
                ) from e
            raise OllamaError(f"Connection error: {e.reason}") from e
        except (TimeoutError, socket.timeout) as e:
            if _retry_count < MAX_RETRIES:
                delay = RETRY_DELAY * (2 ** _retry_count)
                print(f"  ⚠ Socket timeout, retrying in {delay:.1f}s (attempt {_retry_count + 1}/{MAX_RETRIES})...")
                time.sleep(delay)
                return self._request(req, _retry_count + 1)
            raise OllamaError(
                f"Socket timeout after {MAX_RETRIES} retries. "
                f"The model may be too slow or the connection unstable. "
                f"Try: 1) Increase OLLAMA_TIMEOUT (current: {self.timeout}s), "
                f"2) Use a smaller/faster model, or 3) Check Ollama server status.",
                is_timeout=True, can_retry=True
            ) from e

    def _post(self, endpoint: str, payload: dict) -> dict:
        url = f"{self.base_url}{endpoint}"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        return json.loads(self._request(req).decode("utf-8"))

    def _get(self, endpoint: str) -> dict:
        url = f"{self.base_url}{endpoint}"
        req = urllib.request.Request(url, method="GET")
        return json.loads(self._request(req).decode("utf-8"))

    def _delete(self, endpoint: str, payload: dict) -> dict:
        """Send a DELETE request with JSON payload. Handles empty responses."""
        url = f"{self.base_url}{endpoint}"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"},
            method="DELETE",
        )
        try:
            response_data = self._request(req).decode("utf-8")
            if not response_data or not response_data.strip():
                # Empty response = success for some endpoints like /api/delete
                return {"status": "success"}
            return json.loads(response_data)
        except json.JSONDecodeError:
            # Non-JSON response, treat as success if no error was raised
            return {"status": "success"}

    def _stream(self, endpoint: str, payload: dict) -> Iterator[dict]:
        """Yield JSON objects from a streaming Ollama response."""
        url = f"{self.base_url}{endpoint}"
        stream_payload = {**payload, "stream": True}
        data = json.dumps(stream_payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                for raw_line in resp:
                    line = raw_line.decode("utf-8").strip()
                    if line:
                        try:
                            yield json.loads(line)
                        except json.JSONDecodeError:
                            continue
        except urllib.error.URLError as e:
            raise OllamaError(f"Stream error: {e.reason}") from e

    # ------------------------------------------------------------------ #
    #  Chat API                                                            #
    # ------------------------------------------------------------------ #

    def chat(
        self,
        model: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        stream: bool = False,
        options: dict | None = None,
        think: bool | None = None,
    ) -> dict | Iterator[dict]:
        """
        Call /api/chat. Returns a dict (stream=False) or Iterator[dict] (stream=True).
        
        Parameters
        ----------
        think : bool | None
            For thinking-capable models (qwen3, deepseek-r1, etc.):
            - None: Use model default (thinking enabled)
            - False: Disable thinking mode (just return content)
            - True: Enable thinking mode (returns thinking + content)
        """
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "keep_alive": "1m",  # Keep model loaded briefly but clear KV cache between requests
        }
        if tools:
            payload["tools"] = tools
        if options:
            payload["options"] = options
        if think is not None:
            payload["think"] = think

        if stream:
            return self._stream("/api/chat", payload)
        return self._post("/api/chat", payload)

    # ------------------------------------------------------------------ #
    #  Utility                                                             #
    # ------------------------------------------------------------------ #

    def list_models(self) -> list[str]:
        """Return names of locally available models."""
        try:
            data = self._get("/api/tags")
            return [m["name"] for m in data.get("models", [])]
        except OllamaError:
            return []

    def is_running(self) -> bool:
        """Return True if the Ollama server is reachable."""
        try:
            self._get("/api/tags")
            return True
        except Exception:
            return False

    def get_model_info(self, model: str) -> dict:
        """
        Get model information including Modelfile details.
        Returns dict with 'system', 'template', 'parameters', etc.
        
        Uses Ollama's /api/show endpoint.
        """
        payload = {"name": model}
        return self._post("/api/show", payload)
    
    def get_model_family(self, model: str) -> str | None:
        """
        Get the model family from Ollama API.
        Returns None if model not found or family not available.
        
        This queries /api/show endpoint for model details.
        """
        try:
            info = self.get_model_info(model)
            details = info.get("details", {})
            return details.get("family")
        except OllamaError:
            return None
    
    def get_modelfile_system_prompt(self, model: str) -> str | None:
        """
        Get the SYSTEM prompt from the model's Modelfile.
        Returns None if not set.
        
        This is the default system prompt baked into the model
        when it was created with `ollama create`.
        """
        try:
            info = self.get_model_info(model)
            return info.get("system", None)
        except OllamaError:
            return None
    
    def model_supports_tools(self, model: str) -> bool:
        """
        Heuristic check for native tool-calling support.
        Models not in this list fall back to text-based ReAct parsing.
        
        Based on Ollama's native tool-calling support:
        https://github.com/ollama/ollama/blob/main/docs/api.md#generate-chat-completion
        
        Model families confirmed to support tools:
        - Llama 3.x (Meta)
        - Mistral/Mixtral (Mistral AI)
        - Qwen 2/2.5/3 (Alibaba)
        - Command-R (Cohere)
        - DeepSeek V2/V3 (DeepSeek)
        - Phi-3 (Microsoft)
        - And others listed below
        
        Note: Some models may have native support but behave poorly:
        - functiongemma: Designed for tools but often returns empty/refuses
        - granite: Has support but may refuse due to safety filters
        - gemma3: Limited tool support, ReAct fallback often works better
        """
        tool_families = (
            # Meta Llama family
            "llama3", "llama3.1", "llama3.2", "llama3.3",
            "llama3-groq-tool-use",
            
            # Mistral AI family
            "mistral", "mixtral", "mistral-nemo", "mistral-small", "mistral-large",
            "codestral", "ministral",
            
            # Alibaba Qwen family
            "qwen2", "qwen2.5", "qwen3", "qwen35",
            "qwen2.5-coder", "qwen2-math",
            
            # Cohere family
            "command-r", "command-r7b",
            
            # DeepSeek family (strong tool support)
            "deepseek", "deepseek-coder", "deepseek-v2", "deepseek-v3",
            
            # Microsoft Phi family
            "phi-3", "phi3", "phi-4",
            
            # Google Gemma family (limited support)
            "functiongemma",  # Specifically designed for function calling
            # "gemma3",  # Uncomment if you want to enable for gemma3
            
            # IBM Granite family (confirmed tool support)
            "granite", "granite4", "granitemoe",
            
            # 01.ai Yi family
            "yi-", "yi1.5", "yi34b",
            
            # InternLM family
            "internlm2", "internlm2.5",
            
            # Upstage Solar
            "solar",
            
            # ChatGLM / GLM-4
            "glm4", "chatglm",
            
            # Other tool-capable models
            "firefunction", "hermes", "nemotron",
            "cogito", "athene",
        )
        
        # Check if model name matches known families
        model_lower = model.lower()
        if any(f in model_lower for f in tool_families):
            return True
        
        # Fallback: Check API-reported model family
        # This catches models like "driaforall/tiny-agent-a:1.5b" which has family "qwen2"
        api_family = self.get_model_family(model)
        if api_family:
            # Map API family names to our tool_families patterns
            api_family_lower = api_family.lower()
            if any(f in api_family_lower for f in tool_families):
                return True
        
        return False

    # ------------------------------------------------------------------ #
    #  Model Management API (ollama CLI equivalent)                       #
    # ------------------------------------------------------------------ #

    def pull_model(self, name: str, stream: bool = True) -> dict | Iterator[dict]:
        """
        Pull a model from the registry.
        Equivalent to: ollama pull <name>

        Parameters
        ----------
        name : str
            Model name to pull (e.g., "llama3.2:3b")
        stream : bool
            If True, yields progress updates; if False, waits for completion

        Returns
        -------
        dict | Iterator[dict]
            If stream=False, returns final status dict.
            If stream=True, yields progress dicts with 'status', 'completed', 'total' fields.
        """
        payload = {"name": name, "stream": stream}
        if stream:
            return self._stream("/api/pull", payload)
        return self._post("/api/pull", payload)

    def delete_model(self, name: str) -> dict:
        """
        Delete a model from local storage.
        Equivalent to: ollama rm <name>

        Parameters
        ----------
        name : str
            Model name to delete

        Returns
        -------
        dict
            Response from the server
        """
        return self._delete("/api/delete", {"name": name})

    def list_running(self) -> list[dict]:
        """
        List currently running models.
        Equivalent to: ollama ps

        Returns
        -------
        list[dict]
            List of running models with details like name, size, processor, until
        """
        try:
            data = self._get("/api/ps")
            return data.get("models", [])
        except OllamaError:
            return []

    def push_model(self, name: str, stream: bool = True) -> dict | Iterator[dict]:
        """
        Push a model to a registry.
        Equivalent to: ollama push <name>

        Parameters
        ----------
        name : str
            Model name to push
        stream : bool
            If True, yields progress updates

        Returns
        -------
        dict | Iterator[dict]
            Progress updates or final status
        """
        payload = {"name": name, "stream": stream}
        if stream:
            return self._stream("/api/push", payload)
        return self._post("/api/push", payload)

    def create_model(
        self,
        name: str,
        modelfile: str | None = None,
        from_: str | None = None,
        stream: bool = True
    ) -> dict | Iterator[dict]:
        """
        Create a new model from a Modelfile or base model.
        Equivalent to: ollama create <name> -f <modelfile>

        Parameters
        ----------
        name : str
            Name for the new model
        modelfile : str, optional
            Contents of the Modelfile
        from_ : str, optional
            Base model to create from (alternative to modelfile)
        stream : bool
            If True, yields progress updates

        Returns
        -------
        dict | Iterator[dict]
            Progress updates or final status
        """
        payload = {"name": name, "stream": stream}
        if modelfile:
            payload["modelfile"] = modelfile
        if from_:
            payload["from"] = from_
        if stream:
            return self._stream("/api/create", payload)
        return self._post("/api/create", payload)

    def unload_model(self, name: str) -> dict:
        """
        Unload a model from memory (stop keeping it warm).
        Equivalent to: ollama stop <name>

        Parameters
        ----------
        name : str
            Model name to unload

        Returns
        -------
        dict
            Response from the server, or {"status": "not_running"} if model wasn't loaded
        """
        # Ollama uses /api/generate with keep_alive=0 to unload
        try:
            return self._post("/api/generate", {"model": name, "keep_alive": 0})
        except OllamaError as e:
            # Check if model wasn't loaded (HTTP 404 or similar)
            error_str = str(e)
            if "404" in error_str or "not found" in error_str.lower():
                return {"status": "not_running", "message": f"Model '{name}' is not currently loaded"}
            raise
        except Exception as e:
            # Handle any other errors
            error_str = str(e)
            if "404" in error_str:
                return {"status": "not_running", "message": f"Model '{name}' is not currently loaded"}
            raise OllamaError(f"Failed to unload model: {e}") from e

    def copy_model(self, source: str, destination: str) -> dict:
        """
        Copy a model to a new name.
        Equivalent to: ollama cp <source> <destination>

        Parameters
        ----------
        source : str
            Source model name
        destination : str
            New model name

        Returns
        -------
        dict
            Response from the server
        """
        return self._post("/api/copy", {"source": source, "destination": destination})

    def get_model_details(self, name: str) -> dict:
        """
        Get detailed model information formatted for display.
        Equivalent to: ollama show <name>

        This is an alias for get_model_info but returns a cleaner format.

        Parameters
        ----------
        name : str
            Model name

        Returns
        -------
        dict
            Model details including family, size, quantization, etc.
        """
        return self.get_model_info(name)

    def __repr__(self):
        return f"OllamaClient(base_url={self.base_url!r})"