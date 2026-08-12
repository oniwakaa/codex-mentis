import json
import logging
import os
import asyncio
from typing import Dict, Any, List, Optional, AsyncIterator, Iterator
import httpx

from codex_mentis.agents.providers.base import BaseProvider, ProviderConfig

logger = logging.getLogger(__name__)

try:
    import llama_cpp
    LLAMA_CPP_AVAILABLE = True
except ImportError:
    LLAMA_CPP_AVAILABLE = False

class LocalProvider(BaseProvider):
    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.llm = None
        
        # Load local GGUF if path exists and library is available
        if LLAMA_CPP_AVAILABLE and self.config.model and os.path.exists(self.config.model):
            try:
                self.llm = llama_cpp.Llama(
                    model_path=self.config.model,
                    n_ctx=self.config.extra_params.get("n_ctx", 4096),
                    n_gpu_layers=self.config.extra_params.get("n_gpu_layers", -1),
                    verbose=False
                )
                logger.info(f"Loaded local model from {self.config.model}")
            except Exception as e:
                logger.error(f"Failed to load local model: {e}")
                self.llm = None

    def _convert_to_chatml(self, messages: List[Dict[str, str]]) -> str:
        prompt = ""
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            prompt += f"<|im_start|>{role}\n{content}<|im_end|>\n"
        prompt += "<|im_start|>assistant\n"
        return prompt

    def _complete_gguf(self, messages: List[Dict[str, str]], temperature: float) -> Dict[str, Any]:
        if not self.llm:
            raise ValueError("llama-cpp model is not initialized.")
        prompt = self._convert_to_chatml(messages)
        res = self.llm(
            prompt,
            max_tokens=self.config.max_tokens or 1024,
            temperature=temperature,
            stop=["<|im_end|>", "<|im_start|>"]
        )
        text = res["choices"][0]["text"]
        return {"content": text, "tool_calls": []}

    def complete(
        self, 
        messages: List[Dict[str, str]], 
        tools: Optional[List[Dict[str, Any]]] = None, 
        temperature: float = 0.7,
        response_format: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if self.llm:
            return self._complete_gguf(messages, temperature)

        # Fallback to local server (Ollama or Llama.cpp / vLLM OpenAI compatible)
        # Check if Ollama endpoint or OpenAI-compatible endpoint
        base_url = self.config.base_url or "http://localhost:11434"
        
        # Determine if we should use native Ollama API or OpenAI compatibility
        is_ollama_native = "11434" in base_url and "/v1" not in base_url

        if is_ollama_native:
            url = f"{base_url.rstrip('/')}/api/chat"
            payload = {
                "model": self.config.model or "llama3",
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature
                }
            }
            if self.config.max_tokens:
                payload["options"]["num_predict"] = self.config.max_tokens
            if response_format and response_format.get("type") == "json_object":
                payload["format"] = "json"
                
            with httpx.Client(timeout=self.config.timeout) as client:
                res = client.post(url, json=payload)
                res.raise_for_status()
                data = res.json()
                content = data.get("message", {}).get("content", "")
                
                # Check for prompt/completion tokens if returned
                p_tokens = data.get("prompt_eval_count", 0)
                c_tokens = data.get("eval_count", 0)
                
                return {
                    "content": content,
                    "tool_calls": [],
                    "usage": {
                        "prompt_tokens": p_tokens,
                        "completion_tokens": c_tokens,
                        "total_tokens": p_tokens + c_tokens
                    }
                }
        else:
            # Llama.cpp server or vLLM / Ollama OpenAI compatibility
            # Make URL OpenAI compliant
            url = base_url.rstrip("/")
            if not url.endswith("/v1") and not url.endswith("/v1/chat/completions"):
                url = f"{url}/v1/chat/completions"
            elif url.endswith("/v1"):
                url = f"{url}/chat/completions"

            headers = {"Content-Type": "application/json"}
            if self.config.api_key:
                headers["Authorization"] = f"Bearer {self.config.api_key}"

            payload = {
                "model": self.config.model or "local-model",
                "messages": messages,
                "temperature": temperature,
                "stream": False
            }
            if self.config.max_tokens:
                payload["max_tokens"] = self.config.max_tokens
            if tools:
                payload["tools"] = tools
            if response_format:
                payload["response_format"] = response_format

            with httpx.Client(timeout=self.config.timeout) as client:
                res = client.post(url, headers=headers, json=payload)
                res.raise_for_status()
                data = res.json()
                
            choice = data.get("choices", [{}])[0]
            message = choice.get("message", {})
            content = message.get("content") or ""
            
            tool_calls = []
            raw_tool_calls = message.get("tool_calls") or []
            for tc in raw_tool_calls:
                if tc.get("type") == "function":
                    func = tc.get("function", {})
                    try:
                        args = json.loads(func.get("arguments", "{}"))
                    except Exception:
                        args = func.get("arguments", {})
                    tool_calls.append({
                        "name": func.get("name"),
                        "arguments": args
                    })

            usage = data.get("usage", {})
            return {
                "content": content,
                "tool_calls": tool_calls,
                "usage": {
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0)
                }
            }

    async def acomplete(
        self, 
        messages: List[Dict[str, str]], 
        tools: Optional[List[Dict[str, Any]]] = None, 
        temperature: float = 0.7,
        response_format: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if self.llm:
            return await asyncio.to_thread(self._complete_gguf, messages, temperature)

        base_url = self.config.base_url or "http://localhost:11434"
        is_ollama_native = "11434" in base_url and "/v1" not in base_url

        if is_ollama_native:
            url = f"{base_url.rstrip('/')}/api/chat"
            payload = {
                "model": self.config.model or "llama3",
                "messages": messages,
                "stream": False,
                "options": {"temperature": temperature}
            }
            if self.config.max_tokens:
                payload["options"]["num_predict"] = self.config.max_tokens
            if response_format and response_format.get("type") == "json_object":
                payload["format"] = "json"

            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                res = await client.post(url, json=payload)
                res.raise_for_status()
                data = res.json()
                content = data.get("message", {}).get("content", "")
                p_tokens = data.get("prompt_eval_count", 0)
                c_tokens = data.get("eval_count", 0)
                
                return {
                    "content": content,
                    "tool_calls": [],
                    "usage": {
                        "prompt_tokens": p_tokens,
                        "completion_tokens": c_tokens,
                        "total_tokens": p_tokens + c_tokens
                    }
                }
        else:
            url = base_url.rstrip("/")
            if not url.endswith("/v1") and not url.endswith("/v1/chat/completions"):
                url = f"{url}/v1/chat/completions"
            elif url.endswith("/v1"):
                url = f"{url}/chat/completions"

            headers = {"Content-Type": "application/json"}
            if self.config.api_key:
                headers["Authorization"] = f"Bearer {self.config.api_key}"

            payload = {
                "model": self.config.model or "local-model",
                "messages": messages,
                "temperature": temperature,
                "stream": False
            }
            if self.config.max_tokens:
                payload["max_tokens"] = self.config.max_tokens
            if tools:
                payload["tools"] = tools
            if response_format:
                payload["response_format"] = response_format

            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                res = await client.post(url, headers=headers, json=payload)
                res.raise_for_status()
                data = res.json()
                
            choice = data.get("choices", [{}])[0]
            message = choice.get("message", {})
            content = message.get("content") or ""
            
            tool_calls = []
            raw_tool_calls = message.get("tool_calls") or []
            for tc in raw_tool_calls:
                if tc.get("type") == "function":
                    func = tc.get("function", {})
                    try:
                        args = json.loads(func.get("arguments", "{}"))
                    except Exception:
                        args = func.get("arguments", {})
                    tool_calls.append({
                        "name": func.get("name"),
                        "arguments": args
                    })

            usage = data.get("usage", {})
            return {
                "content": content,
                "tool_calls": tool_calls,
                "usage": {
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0)
                }
            }

    def stream(self, messages: List[Dict[str, str]]) -> Iterator[str]:
        if self.llm:
            prompt = self._convert_to_chatml(messages)
            stream_gen = self.llm(
                prompt,
                max_tokens=self.config.max_tokens or 1024,
                temperature=0.7,
                stop=["<|im_end|>", "<|im_start|>"],
                stream=True
            )
            for chunk in stream_gen:
                yield chunk["choices"][0]["text"]
            return

        base_url = self.config.base_url or "http://localhost:11434"
        is_ollama_native = "11434" in base_url and "/v1" not in base_url

        if is_ollama_native:
            url = f"{base_url.rstrip('/')}/api/chat"
            payload = {
                "model": self.config.model or "llama3",
                "messages": messages,
                "stream": True
            }
            with httpx.Client(timeout=self.config.timeout) as client:
                with client.stream("POST", url, json=payload) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            chunk = json.loads(line)
                            content = chunk.get("message", {}).get("content", "")
                            if content:
                                yield content
                        except Exception:
                            continue
        else:
            url = base_url.rstrip("/")
            if not url.endswith("/v1") and not url.endswith("/v1/chat/completions"):
                url = f"{url}/v1/chat/completions"
            elif url.endswith("/v1"):
                url = f"{url}/chat/completions"

            headers = {"Content-Type": "application/json"}
            payload = {
                "model": self.config.model or "local-model",
                "messages": messages,
                "stream": True
            }
            with httpx.Client(timeout=self.config.timeout) as client:
                with client.stream("POST", url, headers=headers, json=payload) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        line = line.strip()
                        if not line:
                            continue
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)
                                content = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                if content:
                                    yield content
                            except Exception:
                                continue

    async def astream(self, messages: List[Dict[str, str]]) -> AsyncIterator[str]:
        if self.llm:
            prompt = self._convert_to_chatml(messages)
            def run_sync_stream():
                return self.llm(
                    prompt,
                    max_tokens=self.config.max_tokens or 1024,
                    temperature=0.7,
                    stop=["<|im_end|>", "<|im_start|>"],
                    stream=True
                )
            stream_gen = await asyncio.to_thread(run_sync_stream)
            for chunk in stream_gen:
                yield chunk["choices"][0]["text"]
            return

        base_url = self.config.base_url or "http://localhost:11434"
        is_ollama_native = "11434" in base_url and "/v1" not in base_url

        if is_ollama_native:
            url = f"{base_url.rstrip('/')}/api/chat"
            payload = {
                "model": self.config.model or "llama3",
                "messages": messages,
                "stream": True
            }
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                async with client.stream("POST", url, json=payload) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            chunk = json.loads(line)
                            content = chunk.get("message", {}).get("content", "")
                            if content:
                                yield content
                        except Exception:
                            continue
        else:
            url = base_url.rstrip("/")
            if not url.endswith("/v1") and not url.endswith("/v1/chat/completions"):
                url = f"{url}/v1/chat/completions"
            elif url.endswith("/v1"):
                url = f"{url}/chat/completions"

            headers = {"Content-Type": "application/json"}
            payload = {
                "model": self.config.model or "local-model",
                "messages": messages,
                "stream": True
            }
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                async with client.stream("POST", url, headers=headers, json=payload) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line:
                            continue
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)
                                content = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                if content:
                                    yield content
                            except Exception:
                                continue

    def embed(self, texts: List[str]) -> List[List[float]]:
        base_url = self.config.base_url or "http://localhost:11434"
        is_ollama_native = "11434" in base_url and "/v1" not in base_url

        if is_ollama_native:
            url = f"{base_url.rstrip('/')}/api/embeddings"
            embeddings = []
            for text in texts:
                payload = {
                    "model": self.config.extra_params.get("embedding_model", "nomic-embed-text"),
                    "prompt": text
                }
                with httpx.Client(timeout=self.config.timeout) as client:
                    res = client.post(url, json=payload)
                    res.raise_for_status()
                    data = res.json()
                    embeddings.append(data["embedding"])
            return embeddings
        else:
            url = f"{base_url.rstrip('/')}/v1/embeddings"
            headers = {"Content-Type": "application/json"}
            payload = {
                "model": self.config.extra_params.get("embedding_model", "text-embedding-3-small"),
                "input": texts
            }
            with httpx.Client(timeout=self.config.timeout) as client:
                res = client.post(url, headers=headers, json=payload)
                res.raise_for_status()
                data = res.json()
            return [item["embedding"] for item in data.get("data", [])]

    async def aembed(self, texts: List[str]) -> List[List[float]]:
        base_url = self.config.base_url or "http://localhost:11434"
        is_ollama_native = "11434" in base_url and "/v1" not in base_url

        if is_ollama_native:
            url = f"{base_url.rstrip('/')}/api/embeddings"
            embeddings = []
            for text in texts:
                payload = {
                    "model": self.config.extra_params.get("embedding_model", "nomic-embed-text"),
                    "prompt": text
                }
                async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                    res = await client.post(url, json=payload)
                    res.raise_for_status()
                    data = res.json()
                    embeddings.append(data["embedding"])
            return embeddings
        else:
            url = f"{base_url.rstrip('/')}/v1/embeddings"
            headers = {"Content-Type": "application/json"}
            payload = {
                "model": self.config.extra_params.get("embedding_model", "text-embedding-3-small"),
                "input": texts
            }
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                res = await client.post(url, headers=headers, json=payload)
                res.raise_for_status()
                data = res.json()
            return [item["embedding"] for item in data.get("data", [])]
