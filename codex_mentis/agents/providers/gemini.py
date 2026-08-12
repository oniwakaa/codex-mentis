import json
import logging
from typing import Dict, Any, List, Optional, AsyncIterator, Iterator
import httpx

from codex_mentis.agents.providers.base import BaseProvider, ProviderConfig

logger = logging.getLogger(__name__)

class GeminiProvider(BaseProvider):
    def _get_url(self, endpoint: str = "generateContent") -> str:
        api_key = self.config.api_key or ""
        model = self.config.model or "gemini-1.5-flash"
        
        if self.config.base_url:
            base = self.config.base_url.rstrip("/")
            return f"{base}/models/{model}:{endpoint}"
        else:
            return f"https://generativelanguage.googleapis.com/v1beta/models/{model}:{endpoint}?key={api_key}"

    def _prepare_payload(
        self, 
        messages: List[Dict[str, str]], 
        tools: Optional[List[Dict[str, Any]]] = None, 
        temperature: float = 0.7,
        response_format: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        contents = []
        system_instruction = None
        
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "")
            
            if role == "system":
                system_instruction = {
                    "parts": [{"text": content}]
                }
            else:
                gemini_role = "model" if role == "assistant" else "user"
                # If there are tool calls in this message
                parts = []
                if "tool_calls" in msg and msg["tool_calls"]:
                    for tc in msg["tool_calls"]:
                        parts.append({
                            "functionCall": {
                                "name": tc["name"],
                                "args": tc["arguments"]
                            }
                        })
                # If it's a tool response message
                elif role == "tool" or msg.get("tool_call_id") is not None:
                    # Gemini expects role: "user" and a part with functionResponse
                    gemini_role = "user"
                    parts.append({
                        "functionResponse": {
                            "name": msg.get("name") or "tool",
                            "response": {"result": content}
                        }
                    })
                
                # Add text content if present
                if content:
                    parts.append({"text": content})
                    
                contents.append({
                    "role": gemini_role,
                    "parts": parts
                })

        generation_config: Dict[str, Any] = {
            "temperature": temperature
        }
        if self.config.max_tokens:
            generation_config["maxOutputTokens"] = self.config.max_tokens
            
        if response_format and response_format.get("type") == "json_object":
            generation_config["responseMimeType"] = "application/json"

        # Default standard safety settings to avoid blocking mathematical or general physics questions
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
        ]

        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": generation_config,
            "safetySettings": safety_settings
        }

        if system_instruction:
            payload["systemInstruction"] = system_instruction

        if tools:
            declarations = []
            for tool in tools:
                if tool.get("type") == "function":
                    func = tool.get("function", {})
                    
                    # Convert properties format if needed
                    parameters = func.get("parameters", {"type": "OBJECT", "properties": {}})
                    # Ensure root type is uppercase as expected by Gemini in some strict contexts
                    if "type" in parameters:
                        parameters["type"] = parameters["type"].upper()
                        
                    declarations.append({
                        "name": func.get("name"),
                        "description": func.get("description", ""),
                        "parameters": parameters
                    })
                else:
                    declarations.append(tool)
            payload["tools"] = [{"functionDeclarations": declarations}]

        # Merge extra params
        if self.config.extra_params:
            for k, v in self.config.extra_params.items():
                if k == "safetySettings":
                    payload["safetySettings"] = v
                elif k == "generationConfig":
                    payload["generationConfig"].update(v)
                else:
                    payload[k] = v

        return payload

    def _parse_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        candidates = data.get("candidates", [{}])
        if not candidates:
            return {"content": "", "tool_calls": [], "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}
            
        candidate = candidates[0]
        content_obj = candidate.get("content", {})
        parts = content_obj.get("parts", [])
        
        content = ""
        tool_calls = []
        for part in parts:
            if "text" in part:
                content += part["text"]
            if "functionCall" in part:
                fc = part["functionCall"]
                tool_calls.append({
                    "name": fc.get("name"),
                    "arguments": fc.get("args", {})
                })

        usage_metadata = data.get("usageMetadata", {})
        prompt_tokens = usage_metadata.get("promptTokenCount", 0)
        completion_tokens = usage_metadata.get("candidatesTokenCount", 0)
        
        return {
            "content": content,
            "tool_calls": tool_calls,
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens
            }
        }

    def complete(
        self, 
        messages: List[Dict[str, str]], 
        tools: Optional[List[Dict[str, Any]]] = None, 
        temperature: float = 0.7,
        response_format: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        url = self._get_url()
        payload = self._prepare_payload(messages, tools, temperature, response_format)
        headers = {"Content-Type": "application/json"}

        with httpx.Client(timeout=self.config.timeout) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        parsed = self._parse_response(data)
        
        # Accumulate usage
        usage = parsed["usage"]
        self.token_usage["prompt_tokens"] += usage["prompt_tokens"]
        self.token_usage["completion_tokens"] += usage["completion_tokens"]
        self.token_usage["total_tokens"] += usage["total_tokens"]
        
        return parsed

    async def acomplete(
        self, 
        messages: List[Dict[str, str]], 
        tools: Optional[List[Dict[str, Any]]] = None, 
        temperature: float = 0.7,
        response_format: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        url = self._get_url()
        payload = self._prepare_payload(messages, tools, temperature, response_format)
        headers = {"Content-Type": "application/json"}

        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        parsed = self._parse_response(data)
        
        # Accumulate usage
        usage = parsed["usage"]
        self.token_usage["prompt_tokens"] += usage["prompt_tokens"]
        self.token_usage["completion_tokens"] += usage["completion_tokens"]
        self.token_usage["total_tokens"] += usage["total_tokens"]
        
        return parsed

    def stream(self, messages: List[Dict[str, str]]) -> Iterator[str]:
        url = self._get_url("streamGenerateContent")
        payload = self._prepare_payload(messages, temperature=0.7)
        headers = {"Content-Type": "application/json"}

        with httpx.Client(timeout=self.config.timeout) as client:
            with client.stream("POST", url, headers=headers, json=payload) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("[") or line.startswith(","):
                        line = line[1:].strip()
                    if line.endswith("]"):
                        line = line[:-1].strip()
                    try:
                        chunk = json.loads(line)
                        candidate = chunk.get("candidates", [{}])[0]
                        parts = candidate.get("content", {}).get("parts", [])
                        for part in parts:
                            if "text" in part:
                                yield part["text"]
                    except Exception:
                        continue

    async def astream(self, messages: List[Dict[str, str]]) -> AsyncIterator[str]:
        url = self._get_url("streamGenerateContent")
        payload = self._prepare_payload(messages, temperature=0.7)
        headers = {"Content-Type": "application/json"}

        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("[") or line.startswith(","):
                        line = line[1:].strip()
                    if line.endswith("]"):
                        line = line[:-1].strip()
                    try:
                        chunk = json.loads(line)
                        candidate = chunk.get("candidates", [{}])[0]
                        parts = candidate.get("content", {}).get("parts", [])
                        for part in parts:
                            if "text" in part:
                                yield part["text"]
                    except Exception:
                        continue

    def embed(self, texts: List[str]) -> List[List[float]]:
        api_key = self.config.api_key or ""
        model = self.config.extra_params.get("embedding_model", "text-embedding-004")
        
        if self.config.base_url:
            base = self.config.base_url.rstrip("/")
            url = f"{base}/models/{model}:embedContent"
        else:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:embedContent?key={api_key}"
            
        embeddings = []
        for text in texts:
            payload = {
                "model": f"models/{model}",
                "content": {"parts": [{"text": text}]}
            }
            headers = {"Content-Type": "application/json"}
            with httpx.Client(timeout=self.config.timeout) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                embeddings.append(data["embedding"]["values"])
                
        return embeddings

    async def aembed(self, texts: List[str]) -> List[List[float]]:
        api_key = self.config.api_key or ""
        model = self.config.extra_params.get("embedding_model", "text-embedding-004")
        
        if self.config.base_url:
            base = self.config.base_url.rstrip("/")
            url = f"{base}/models/{model}:embedContent"
        else:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:embedContent?key={api_key}"
            
        embeddings = []
        for text in texts:
            payload = {
                "model": f"models/{model}",
                "content": {"parts": [{"text": text}]}
            }
            headers = {"Content-Type": "application/json"}
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                embeddings.append(data["embedding"]["values"])
                
        return embeddings
