from __future__ import annotations

from typing import Any

import httpx

from app.decision.base import DecisionResult
from app.decision.providers import (
    NanoJevProvider,
    RuleBasedProvider,
    TypeSafeJevProvider,
    VonProvider,
)


class DecisionRouter:
    def __init__(
        self,
        *,
        api_key: str | None,
        typesafe_url: str = "https://api.typesafe.ai/v1/systemone",
        typesafe_model: str = "jev-latest",
        nano_url: str = "http://127.0.0.1:9101",
        von_url: str = "http://127.0.0.1:9102",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key = api_key
        self.typesafe_url = typesafe_url
        self.typesafe_model = typesafe_model
        self.nano_url = nano_url
        self.von_url = von_url
        self.transport = transport

    async def evaluate(self, state: dict[str, Any], questions: dict[str, Any]) -> DecisionResult:
        candidates: list[TypeSafeJevProvider | NanoJevProvider | VonProvider] = []
        if self.api_key:
            candidates.append(
                TypeSafeJevProvider(
                    self.typesafe_url,
                    api_key=self.api_key,
                    model=self.typesafe_model,
                    transport=self.transport,
                )
            )
        candidates.extend(
            (
                NanoJevProvider(self.nano_url, transport=self.transport),
                VonProvider(self.von_url, transport=self.transport),
            )
        )
        for provider in candidates:
            try:
                return await provider.evaluate(state, questions)
            except (httpx.HTTPError, ValueError, TypeError):
                continue
        return await RuleBasedProvider().evaluate(state, questions)
