"""
Thin abstraction over the LLM provider so orchestrator.py isn't hard-wired
to one SDK, and so the orchestration logic can be tested deterministically
without a live API key (see FakeLLMClient).
"""
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
    # Exactly one of these is populated: a turn either asks for tool calls
    # or gives a final text answer, never both, never neither.
    tool_calls: list[ToolCall] = field(default_factory=list)
    text: str | None = None

    @property
    def wants_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


class LLMClient(ABC):
    @abstractmethod
    def complete(self, messages: list[dict], tools: list[dict]) -> LLMResponse:
        """Send the conversation + tool specs, get back either tool calls or final text."""


class OpenAILLMClient(LLMClient):
    """Talks to a real OpenAI-compatible function-calling API. Untested in
    this environment — no reachable provider API, no key. Also: OpenAI's API
    is not accessible from Hong Kong directly (geoblocked) — kept here for
    portability (e.g. deploying outside HK, or via Azure OpenAI, which uses
    this same request/response shape) but VertexAILLMClient is the one
    actually configured for this deployment. See app/agent/README.md."""

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


class VertexAILLMClient(LLMClient):
    """Talks to Gemini via Google Cloud (Vertex AI / Gemini Enterprise Agent
    Platform), using the unified `google-genai` SDK — not the older
    `vertexai.generative_models` module, which Google is deprecating (removal
    slated for June 2026). Authenticates via Application Default Credentials,
    not an API key — see app/agent/README.md for gcloud setup.

    Translation notes (the two APIs don't share a wire format):
      - No "system" role in Gemini's Content list — system instructions are
        a separate `system_instruction` config field, extracted from the
        internal message list here rather than sent as a turn.
      - Gemini's roles are "user" and "model", not "user"/"assistant"/"tool".
        Tool-call requests are role="model" content with function_call parts;
        tool results go back as role="user" content with function_response
        parts (matching the pattern in Google's own SDK examples — chat.
        send_message(Part.from_function_response(...)) defaults to "user").
        This specific role choice for function results is NOT verified
        against a live call in this environment; "function" role is also
        accepted client-side by the SDK's types if "user" turns out wrong.
      - FunctionDeclaration accepts a raw JSON schema directly via
        parameters_json_schema — confirmed to construct without error using
        the exact schemas Pydantic emits (including $defs/$ref for the
        nested FilterCondition model), so tool_specs.py's Pydantic-derived
        schemas are reused as-is rather than hand-converted to Gemini's
        native Schema type. Whether the live backend accepts $defs/$ref
        inside parameters_json_schema is the one thing this couldn't verify
        without network access — run the smoke test in agent/README.md
        first.
      - FunctionCall.id may not be populated by the live API (Gemini
        historically correlated by position/name, not always by id, unlike
        OpenAI). A synthetic id is generated when missing, consistent within
        a single turn since this code both produces and consumes it.
    """

    def __init__(self, project: str, location: str, model: str = "gemini-2.5-flash"):
        from google import genai

        self._client = genai.Client(vertexai=True, project=project, location=location)
        self._model = model

    def complete(self, messages: list[dict], tools: list[dict]) -> LLMResponse:
        from google.genai import types

        system_instruction, contents = self._to_gemini_contents(messages)
        gemini_tools = [self._to_gemini_tool(t) for t in tools]

        response = self._client.models.generate_content(
            model=self._model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                tools=gemini_tools,
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

        for msg in messages:
            role = msg["role"]

            if role == "system":
                system_instruction = msg["content"]

            elif role == "user":
                contents.append(types.Content(role="user", parts=[types.Part(text=msg["content"])]))

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

            elif role == "tool":
                try:
                    response_obj = json.loads(msg["content"])
                except (json.JSONDecodeError, TypeError):
                    response_obj = {"result": msg["content"]}
                contents.append(
                    types.Content(
                        role="user",
                        parts=[
                            types.Part(
                                function_response=types.FunctionResponse(
                                    id=msg.get("tool_call_id"),
                                    name=msg.get("name", "unknown_tool"),
                                    response=response_obj,
                                )
                            )
                        ],
                    )
                )

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


class FakeLLMClient(LLMClient):
    """Returns a pre-scripted sequence of responses, one per call to
    complete(), regardless of what's actually in `messages`. This is what
    lets the orchestration loop (dispatch, message threading, max-iteration
    guard, error recovery) be tested deterministically without any real
    model — the thing being tested is our code, not the LLM's judgment."""

    def __init__(self, scripted_responses: list[LLMResponse]):
        self._responses = list(scripted_responses)
        self.call_count = 0
        self.received_messages: list[list[dict]] = []

    def complete(self, messages: list[dict], tools: list[dict]) -> LLMResponse:
        self.received_messages.append(messages)
        if self.call_count >= len(self._responses):
            raise AssertionError(
                f"FakeLLMClient ran out of scripted responses after {self.call_count} calls — "
                "the orchestrator called complete() more times than the test expected."
            )
        response = self._responses[self.call_count]
        self.call_count += 1
        return response

