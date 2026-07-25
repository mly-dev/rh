"""Fournisseur Anthropic (API Claude, via le SDK officiel)."""
import anthropic

from app.core.config import settings
from app.rag.provider import LLMProvider, LLMResponse, ToolCall


class AnthropicProvider(LLMProvider):
    def __init__(self) -> None:
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = settings.anthropic_model

    def complete(
        self, system: str, messages: list[dict], tools: list[dict]
    ) -> LLMResponse:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=system,
            messages=messages,
            tools=tools,
        )
        if response.stop_reason == "refusal":
            return LLMResponse(
                text="Je ne peux pas répondre à cette question.",
                raw_content=response.content,
            )
        text = ""
        tool_calls: list[ToolCall] = []
        for block in response.content:
            if block.type == "text":
                text += block.text
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(id=block.id, name=block.name, input=dict(block.input))
                )
        return LLMResponse(text=text, tool_calls=tool_calls, raw_content=response.content)
