#!/usr/bin/env python3
"""
⚛️ AgentNova R04 — BitnetClient
Drop-in replacement for OllamaClient that uses Microsoft's bitnet.cpp
(llama-server) as the inference backend instead of Ollama.

Architecture:
  - Wraps bitnet.cpp's llama-server HTTP process
  - Exposes the same interface as OllamaClient: chat(), list_models(),
    model_supports_tools(), is_running()
  - Normalises OpenAI-format responses → Ollama-format so agent.py is
    completely unmodified
  - Manages llama-server lifecycle (start/stop/health-check)
  - Falls back gracefully to ReAct tool-calling (no native function
    calling in current bitnet models)

Supported models (as of bitnet.cpp 2025):
  - microsoft/BitNet-b1.58-2B-4T   (~0.4 GB, recommended)
  - 1bitLLM/bitnet_b1_58-3B        (~0.7 GB)
  - HF1BitLLM/Llama3-8B-1.58-100B-tokens
  - tiiuae/Falcon3-1B-Instruct-1.58bit
  - tiiuae/Falcon3-3B-Instruct-1.58bit
  - tiiuae/Falcon3-7B-Instruct-1.58bit
"""

import json
import urllib.request
from .config import BITNET_BASE_URL

# Known BitNet model identifiers
KNOWN_MODELS = [
    "bitnet-b1.58-2b-4t",
    "BitNet-b1.58-2B-4T",
    "bitnet-b1.58-large",
]

class BitnetClient:
    def __init__(self, base_url=None, timeout=120):
        # Prioritize passed URL, fallback to config
        self.base_url = base_url or BITNET_BASE_URL
        self.timeout = timeout

    def is_running(self) -> bool:
        try:
            with urllib.request.urlopen(f"{self.base_url}/health", timeout=2) as resp:
                return resp.getcode() == 200
        except:
            return False

    def list_models(self):
        try:
            with urllib.request.urlopen(f"{self.base_url}/v1/models", timeout=5) as resp:
                if resp.getcode() == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    # Return the ID of the model(s), cleaned up to show just model folder/filename
                    models = []
                    for m in data.get('data', []):
                        model_id = m['id']
                        # Strip common prefixes to show just model_dir/filename.gguf
                        # e.g., /content/BitNet/models/BitNet-b1.58-2B-4T/bitnet_2b_i2_s.gguf
                        #   -> BitNet-b1.58-2B-4T/bitnet_2b_i2_s.gguf
                        if '/models/' in model_id:
                            # Keep everything after /models/
                            model_id = model_id.split('/models/')[-1]
                        elif model_id.startswith('/'):
                            # Just keep last two path components
                            parts = model_id.strip('/').split('/')
                            if len(parts) >= 2:
                                model_id = '/'.join(parts[-2:])
                        models.append(model_id)
                    return models
        except:
            return []

    def chat(
        self,
        model: str,
        messages: list[dict],
        options: dict | None = None,
        stream: bool = False,
        tools: list | None = None, # Signature fix for agent.py
        **kwargs,                  # Catch-all for extra agent args
    ):
        """
        Chat completion for BitNet.
        
        Note: BitNet llama-server doesn't support streaming in the same way
        as Ollama. When stream=True, this yields tokens from a streaming
        response. Otherwise returns a complete response dict.
        """
        url = f"{self.base_url}/v1/chat/completions"
        
        data = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "temperature": (options or {}).get("temperature", 0.7),
        }

        req = urllib.request.Request(
            url, 
            data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )

        if stream:
            # Return a generator for streaming
            return self._stream_response(req, model)
        else:
            # Non-streaming: return complete response
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                # Normalize OpenAI completion to Ollama format for the Agent
                return {
                    "model": model,
                    "message": {
                        "role": "assistant",
                        "content": result["choices"][0]["message"]["content"]
                    },
                    "done": True
                }

    def _stream_response(self, req, model):
        """
        Handle SSE streaming response from BitNet server.
        Yields tokens one at a time.
        """
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            buffer = ""
            for line in resp:
                line = line.decode("utf-8")
                if line.startswith("data: "):
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        if "choices" in chunk and len(chunk["choices"]) > 0:
                            delta = chunk["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                    except json.JSONDecodeError:
                        continue

    def model_supports_tools(self, model: str) -> bool:
        return False # BitNet models require ReAct fallback in Agent.py
    
    def supports_streaming(self) -> bool:
        """Return True if this client supports streaming."""
        return True