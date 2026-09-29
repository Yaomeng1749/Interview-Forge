from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field


class DecisionResult(BaseModel):
    provider: str
    template_id: str = "exam-g-mixed"
    difficulty: dict[str, int] = Field(default_factory=lambda: {"L1": 12, "L2": 20, "L3": 8})
    topic_weights: dict[str, float] = Field(default_factory=dict)
    confidence: float = 1.0


class DecisionProvider(Protocol):
    async def evaluate(
        self, state: dict[str, Any], questions: dict[str, Any]
    ) -> DecisionResult: ...
