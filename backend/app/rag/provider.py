"""Abstraction du fournisseur LLM.

Le backend garde la main sur l'exécution : le LLM ne reçoit que des
« fonctions de requête » restreintes (voir nl2query.py) et ne génère
jamais de SQL. Deux implémentations : Anthropic (production) et Mock
(développement/démonstration sans clé API).
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ToolCall:
    id: str
    name: str
    input: dict


@dataclass
class LLMResponse:
    """Réponse d'un tour de conversation : texte et/ou appels d'outils."""

    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    # blocs de contenu bruts de l'assistant, à renvoyer tels quels au tour
    # suivant (exigence de l'API pour les blocs thinking/tool_use)
    raw_content: object = None


class LLMProvider(ABC):
    @abstractmethod
    def complete(
        self, system: str, messages: list[dict], tools: list[dict]
    ) -> LLMResponse:
        """Un tour de conversation. `messages` suit le format Anthropic
        (role user/assistant, content texte ou blocs tool_result)."""


def get_provider() -> LLMProvider:
    from app.core.config import settings

    if settings.llm_provider == "anthropic" and settings.anthropic_api_key:
        from app.rag.anthropic_provider import AnthropicProvider

        return AnthropicProvider()
    from app.rag.mock_provider import MockProvider

    return MockProvider()
