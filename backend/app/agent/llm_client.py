# abstraction over the LLM provider to test orchestration logic without live API key
# orchestrator.py not tied to one SDK
import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    # a turn either asks for tool calls or gives a final text answer, never both or neither
    tool_calls: list[ToolCall] = field(default_factory=list)
    text: str | None = None

    @property
    def wants_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


class LLMClient(ABC):
    @abstractmethod
    def complete(self, messages: list[dict], tools: list[dict]) -> LLMResponse:
        """Send the conversation + tool specs, get back either tool calls or final text."""

# talks to OpenAI client, for deployment in areas where OpenAI is available
class OpenAILLMClient(LLMClient):
    
    def __init__(self, model: str = "gpt-4o-mini", api_key: str | None = None):
        try:
            from openai import OpenAI
        except ImportError as e:
            raise ImportError("The 'openai' package is required for OpenAILLMClient. pip install openai") from e

        self._client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self._model = model

    def complete(self, messages: list[dict], tools: list[dict]) -> LLMResponse:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )
        choice = response.choices[0].message

        if choice.tool_calls:
            calls = [
                ToolCall(id=tc.id, name=tc.function.name, arguments=json.loads(tc.function.arguments))
                for tc in choice.tool_calls
            ]
            return LLMResponse(tool_calls=calls)

        return LLMResponse(text=choice.content or "")

# talks to Gemini via Google Cloud (Vertex AI/Gemini Enterprise Agent Platform)
class VertexAILLMClient(LLMClient):
    """
    Translation notes:
      - system instructions are a separate `system_instruction` config field that are extracted from internal message list
      - tool-call requests are role="model" content with function_call parts
      - tool results go back as role="user" content with function_response parts. 
      - FunctionDeclaration accepts a raw JSON schema directly via parameters_json_schema
      - FunctionCall.id may not be populated by the live API so a synthetic id is generated when missing
    """

    def __init__(self, project: str, location: str, model: str = "gemini-2.5-pro", thinking_budget: int | None = None, thinking_level: str | None = None,):
        from google import genai

        self._client = genai.Client(vertexai=True, project=project, location=location)
        self._model = model
        self._thinking_budget = thinking_budget
        self._thinking_level = thinking_level

    def complete(self, messages: list[dict], tools: list[dict]) -> LLMResponse:
        from google.genai import types

        system_instruction, contents = self._to_gemini_contents(messages)
        gemini_tools = [self._to_gemini_tool(t) for t in tools]

        thinking_config = None
        if self._thinking_budget is not None or self._thinking_level is not None:
            thinking_config = types.ThinkingConfig(
                thinking_budget=self._thinking_budget,
                thinking_level=self._thinking_level
            )
        
        response = self._client.models.generate_content(
            model=self._model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                tools=gemini_tools,
                thinking_config=thinking_config,
            ),
        )
        return self._from_gemini_response(response)

    @staticmethod
    def _to_gemini_tool(openai_style_spec: dict):
        from google.genai import types

        fn = openai_style_spec["function"]
        return types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name=fn["name"],
                    description=fn["description"],
                    parameters_json_schema=fn["parameters"],
                )
            ]
        )

    @staticmethod
    def _to_gemini_contents(messages: list[dict]):
        from google.genai import types

        system_instruction = None
        contents = []
        i = 0

        while i < len(messages):
            msg = messages[i]
            role = msg["role"]

            if role == "system":
                system_instruction = msg["content"]
                i += 1

            elif role == "user":
                contents.append(types.Content(role="user", parts=[types.Part(text=msg["content"])]))
                i += 1

            elif role == "assistant":
                if msg.get("tool_calls"):
                    parts = [
                        types.Part(
                            function_call=types.FunctionCall(
                                id=tc["id"],
                                name=tc["function"]["name"],
                                args=json.loads(tc["function"]["arguments"]),
                            )
                        )
                        for tc in msg["tool_calls"]
                    ]
                    contents.append(types.Content(role="model", parts=parts))
                else:
                    contents.append(types.Content(role="model", parts=[types.Part(text=msg.get("content") or "")]))
                i += 1

            elif role == "tool":
                # Gemini requires every function_response answering a given
                # function_call turn to arrive bundled into ONE Content, not
                # as separate turns. Consecutive "tool" messages in the
                # internal format always answer one such turn (see
                # orchestrator.py's dispatch loop), so they're grouped back
                # into a single Content here rather than one per message.
                parts = []
                while i < len(messages) and messages[i]["role"] == "tool":
                    tool_msg = messages[i]
                    try:
                        response_obj = json.loads(tool_msg["content"])
                    except (json.JSONDecodeError, TypeError):
                        response_obj = {"result": tool_msg["content"]}
                    parts.append(
                        types.Part(
                            function_response=types.FunctionResponse(
                                id=tool_msg.get("tool_call_id"),
                                name=tool_msg.get("name", "unknown_tool"),
                                response=response_obj,
                            )
                        )
                    )
                    i += 1
                contents.append(types.Content(role="user", parts=parts))

            else:
                i += 1

        return system_instruction, contents

    @staticmethod
    def _from_gemini_response(response) -> LLMResponse:
        function_calls = response.function_calls or []
        if function_calls:
            calls = [
                ToolCall(
                    id=fc.id or f"call_{i}",
                    name=fc.name,
                    arguments=dict(fc.args or {}),
                )
                for i, fc in enumerate(function_calls)
            ]
            return LLMResponse(tool_calls=calls)

        return LLMResponse(text=response.text or "")