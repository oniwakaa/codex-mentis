import asyncio
import json
import logging
import random
import re
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable, Type, Union, AsyncIterator
from pydantic import BaseModel, ValidationError

from codex_mentis.agents.providers.base import BaseProvider

logger = logging.getLogger(__name__)

@dataclass
class AgentResponse:
    content: str
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

class EventEmitter:
    def __init__(self):
        self._listeners: Dict[str, List[Callable]] = {}

    def on(self, event: str, listener: Callable) -> None:
        if event not in self._listeners:
            self._listeners[event] = []
        self._listeners[event].append(listener)

    def off(self, event: str, listener: Callable) -> None:
        if event in self._listeners:
            try:
                self._listeners[event].remove(listener)
            except ValueError:
                pass

    async def emit(self, event: str, *args: Any, **kwargs: Any) -> None:
        if event in self._listeners:
            for listener in self._listeners[event]:
                try:
                    if asyncio.iscoroutinefunction(listener):
                        await listener(*args, **kwargs)
                    else:
                        listener(*args, **kwargs)
                except Exception as e:
                    logger.error(f"Error in listener for event {event}: {e}")

def validate_json_schema(schema: Dict[str, Any], data: Any) -> List[str]:
    """
    Validate data against a simple JSON schema.
    Returns a list of error messages. If empty, validation succeeded.
    """
    errors = []
    if not isinstance(schema, dict):
        return errors

    t = schema.get("type", "object")
    
    if t == "object":
        if not isinstance(data, dict):
            errors.append(f"Expected object, got {type(data).__name__}")
            return errors
        
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        
        for req in required:
            if req not in data:
                errors.append(f"Missing required property: '{req}'")
        
        for k, v in data.items():
            if k in properties:
                prop_errors = validate_json_schema(properties[k], v)
                for pe in prop_errors:
                    errors.append(f"Property '{k}': {pe}")
            elif schema.get("additionalProperties") is False:
                errors.append(f"Additional property '{k}' not allowed")
                
    elif t == "array":
        if not isinstance(data, list):
            errors.append(f"Expected list/array, got {type(data).__name__}")
            return errors
        
        items_schema = schema.get("items")
        if items_schema:
            for idx, item in enumerate(data):
                item_errors = validate_json_schema(items_schema, item)
                for ie in item_errors:
                    errors.append(f"Item at index {idx}: {ie}")
                    
    elif t == "string":
        if not isinstance(data, str):
            errors.append(f"Expected string, got {type(data).__name__}")
            
    elif t in ("number", "integer"):
        if t == "integer" and (not isinstance(data, int) or isinstance(data, bool)):
            errors.append(f"Expected integer, got {type(data).__name__}")
        elif t == "number" and (not isinstance(data, (int, float)) or isinstance(data, bool)):
            errors.append(f"Expected number, got {type(data).__name__}")
            
    elif t == "boolean":
        if not isinstance(data, bool):
            errors.append(f"Expected boolean, got {type(data).__name__}")
            
    return errors

class BaseAgent:
    def __init__(
        self,
        name: str,
        role: str,
        provider: BaseProvider,
        system_prompt: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        max_history_len: int = 40
    ):
        self.name = name
        self.role = role
        self.provider = provider
        self.system_prompt = system_prompt
        self.tools = tools or []
        self.tool_handlers: Dict[str, Callable] = {}
        self.tool_schemas: Dict[str, Dict[str, Any]] = {}
        self.history: List[Dict[str, Any]] = []
        self.max_history_len = max_history_len
        self.events = EventEmitter()
        
        # Token usage accumulated across all agent operations
        self.token_usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }

        # Initialize tools
        if tools:
            for t in tools:
                if t.get("type") == "function":
                    func = t.get("function", {})
                    name = func.get("name")
                    if name:
                        self.tool_schemas[name] = func.get("parameters", {})

    def register_tool(self, name: str, schema: Dict[str, Any], handler: Callable) -> None:
        """
        Registers a tool schema and its corresponding execution handler.
        """
        # Ensure OpenAI format wrapper
        if "type" in schema and schema["type"] == "function":
            self.tools.append(schema)
            func_schema = schema.get("function", {})
            self.tool_schemas[name] = func_schema.get("parameters", {})
        else:
            self.tools.append({
                "type": "function",
                "function": schema
            })
            self.tool_schemas[name] = schema.get("parameters", {})
            
        self.tool_handlers[name] = handler

    def add_message(
        self, 
        role: str, 
        content: str, 
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        name: Optional[str] = None,
        tool_call_id: Optional[str] = None
    ) -> None:
        """
        Add a message to history. Prunes conversation history if it exceeds max_history_len.
        """
        msg: Dict[str, Any] = {"role": role, "content": content}
        if tool_calls is not None:
            msg["tool_calls"] = tool_calls
        if name is not None:
            msg["name"] = name
        if tool_call_id is not None:
            msg["tool_call_id"] = tool_call_id
            
        self.history.append(msg)
        
        # Enforce history limit while retaining system context if possible
        if len(self.history) > self.max_history_len:
            # Try to keep the first message if it is system
            if self.history[0].get("role") == "system":
                self.history = [self.history[0]] + self.history[-(self.max_history_len - 1):]
            else:
                self.history = self.history[-self.max_history_len:]

    def clear_history(self) -> None:
        self.history = []

    def get_history(self) -> List[Dict[str, Any]]:
        return self.history

    def _validate_tool_args(self, tool_name: str, args: Dict[str, Any]) -> Optional[str]:
        """
        Validates tool arguments against the registered schema.
        Returns None if valid, or an error string if invalid.
        """
        schema = self.tool_schemas.get(tool_name)
        if not schema:
            return None  # No schema found to validate against
        
        errors = validate_json_schema(schema, args)
        if errors:
            return f"Validation failed for tool '{tool_name}': " + "; ".join(errors)
        return None

    def with_tool(self, tool_name: str, args: Dict[str, Any]) -> Any:
        """
        Execute a registered tool synchronously by name with arguments, with schema validation.
        """
        validation_error = self._validate_tool_args(tool_name, args)
        if validation_error:
            return validation_error

        handler = getattr(self, f"tool_{tool_name}", None) or self.tool_handlers.get(tool_name)
        if handler:
            try:
                # If the handler is async, run in a loop
                if asyncio.iscoroutinefunction(handler):
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # We are inside an running event loop, we must run it in a thread or task
                        import nest_asyncio
                        nest_asyncio.apply()
                    return asyncio.run(handler(**args))
                return handler(**args)
            except Exception as e:
                return f"Error executing tool {tool_name}: {str(e)}"
        return f"Error: Tool {tool_name} is not registered on agent {self.name}."

    async def awith_tool(self, tool_name: str, args: Dict[str, Any]) -> Any:
        """
        Execute a registered tool asynchronously by name with arguments, with schema validation.
        """
        await self.events.emit("tool_start", tool_name, args)
        
        validation_error = self._validate_tool_args(tool_name, args)
        if validation_error:
            await self.events.emit("tool_end", tool_name, validation_error, False)
            return validation_error

        handler = getattr(self, f"tool_{tool_name}", None) or self.tool_handlers.get(tool_name)
        if handler:
            try:
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(**args)
                else:
                    result = handler(**args)
                await self.events.emit("tool_end", tool_name, result, True)
                return result
            except Exception as e:
                err_msg = f"Error executing tool {tool_name}: {str(e)}"
                await self.events.emit("tool_end", tool_name, err_msg, False)
                return err_msg
        
        err_msg = f"Error: Tool {tool_name} is not registered on agent {self.name}."
        await self.events.emit("tool_end", tool_name, err_msg, False)
        return err_msg

    def think(self, prompt: str, context: Optional[str] = None) -> AgentResponse:
        """
        Sends the prompt and optional context to the LLM provider synchronously.
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import nest_asyncio
                nest_asyncio.apply()
            return asyncio.run(self.athink(prompt, context))
        except Exception:
            # Fallback to pure synchronous complete
            messages = [{"role": "system", "content": self.system_prompt}]
            user_content = f"--- CONTEXT ---\n{context}\n---------------\n\n{prompt}" if context else prompt
            messages.append({"role": "user", "content": user_content})
            
            raw_response = self.provider.complete(messages=messages, tools=self.tools, temperature=0.7)
            content = raw_response.get("content", "")
            tool_calls = raw_response.get("tool_calls", [])
            
            return AgentResponse(
                content=content,
                tool_calls=tool_calls,
                confidence=self._calculate_confidence(content, raw_response),
                metadata={"agent_name": self.name, "agent_role": self.role}
            )

    async def athink(self, prompt: str, context: Optional[str] = None) -> AgentResponse:
        """
        Sends the prompt and optional context to the LLM provider asynchronously, 
        managing history, retries, events, and token counting.
        """
        await self.events.emit("think_start", prompt)
        
        # Build messages including history
        messages = []
        if not self.history or self.history[0].get("role") != "system":
            messages.append({"role": "system", "content": self.system_prompt})
        
        messages.extend(self.history)
        
        user_content = ""
        if context:
            user_content += f"--- CONTEXT ---\n{context}\n---------------\n\n"
        user_content += prompt
        
        messages.append({"role": "user", "content": user_content})
        
        # Exponential backoff retry logic
        max_retries = self.provider.config.max_retries
        initial_backoff = self.provider.config.initial_backoff
        backoff_factor = self.provider.config.backoff_factor
        
        raw_response = None
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                await self.events.emit("status_change", f"Querying provider (attempt {attempt+1}/{max_retries+1})...")
                raw_response = await self.provider.acomplete(
                    messages=messages,
                    tools=self.tools if self.tools else None,
                    temperature=0.7
                )
                break
            except Exception as e:
                last_error = e
                if attempt == max_retries:
                    break
                sleep_time = initial_backoff * (backoff_factor ** attempt) + random.uniform(0, 0.1)
                await self.events.emit("status_change", f"Provider error: {e}. Retrying in {sleep_time:.2f}s...")
                await asyncio.sleep(sleep_time)

        if not raw_response:
            err_msg = f"Failed after {max_retries+1} attempts: {last_error}"
            await self.events.emit("error", err_msg)
            return AgentResponse(
                content=f"Error during execution: {err_msg}",
                tool_calls=[],
                confidence=0.0,
                metadata={"error": err_msg}
            )

        content = raw_response.get("content") or ""
        tool_calls = raw_response.get("tool_calls") or []
        
        # Parse token usage
        usage = raw_response.get("usage") or {}
        p_tok = usage.get("prompt_tokens", 0)
        c_tok = usage.get("completion_tokens", 0)
        t_tok = usage.get("total_tokens", p_tok + c_tok)
        
        self.token_usage["prompt_tokens"] += p_tok
        self.token_usage["completion_tokens"] += c_tok
        self.token_usage["total_tokens"] += t_tok
        
        # Save messages to conversation history
        self.add_message("user", user_content)
        self.add_message("assistant", content, tool_calls=tool_calls)

        confidence = self._calculate_confidence(content, raw_response)
        
        metadata = {
            "agent_name": self.name,
            "agent_role": self.role,
            "model": getattr(self.provider.config, "model", "unknown"),
            "token_usage_step": usage,
            "token_usage_total": self.token_usage.copy()
        }
        
        response = AgentResponse(
            content=content,
            tool_calls=tool_calls,
            confidence=confidence,
            metadata=metadata
        )
        
        await self.events.emit("think_end", response)
        return response

    async def athink_structured(
        self, 
        prompt: str, 
        response_model: Type[BaseModel], 
        context: Optional[str] = None
    ) -> BaseModel:
        """
        Sends the prompt to the provider and guarantees structured output matching the response_model.
        Uses schema descriptions to instruct the model, and automatically parses/validates output.
        """
        schema_json = json.dumps(response_model.model_json_schema(), indent=2)
        
        structured_prompt = (
            f"{prompt}\n\n"
            f"IMPORTANT: You MUST return a JSON object that strictly conforms to the following JSON schema:\n"
            f"```json\n{schema_json}\n```\n"
            f"Do not include any text outside the JSON block. Return ONLY valid raw JSON."
        )
        
        # Run with JSON schema response_format if provider supports it
        # Try to parse response content as response_model
        max_attempts = 3
        last_exception = None
        
        for attempt in range(max_attempts):
            response = await self.athink(
                prompt=structured_prompt,
                context=context
            )
            
            content = response.content.strip()
            
            # Clean possible markdown wrap
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            try:
                obj = json.loads(content)
                validated_model = response_model.model_validate(obj)
                return validated_model
            except (json.JSONDecodeError, ValidationError) as e:
                last_exception = e
                # Adjust prompt to notify LLM of the syntax or validation failure
                structured_prompt = (
                    f"{prompt}\n\n"
                    f"Your previous output failed validation: {e}\n"
                    f"Please output a valid JSON object matching the schema:\n"
                    f"```json\n{schema_json}\n```"
                )
                
        raise ValueError(f"Failed to generate structured output conforming to {response_model.__name__}: {last_exception}")

    def _calculate_confidence(self, content: str, raw_response: Dict[str, Any]) -> float:
        confidence = 1.0
        if "confidence" in raw_response:
            try:
                confidence = float(raw_response["confidence"])
            except ValueError:
                pass
        else:
            # Try parsing from text content
            conf_match = re.search(r"<confidence>\s*(0\.\d+|1\.0|1)\s*</confidence>", content, re.IGNORECASE)
            if conf_match:
                try:
                    confidence = float(conf_match.group(1))
                except ValueError:
                    pass
            elif any(word in content.lower() for word in ["unsure", "not certain", "maybe", "hypothesize"]):
                confidence = 0.7
            elif any(word in content.lower() for word in ["cannot determine", "insufficient information", "contradiction"]):
                confidence = 0.4
        return confidence
