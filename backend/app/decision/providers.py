from __future__ import annotations

from collections import defaultdict
from typing import Any

import httpx

from app.decision.base import DecisionResult


class HttpDecisionProvider:
    name = "http"

    def __init__(
        self,
        url: str,
        *,
        api_key: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.url = url
        self.api_key = api_key
        self.transport = transport

    async def evaluate(self, state: dict[str, Any], questions: dict[str, Any]) -> DecisionResult:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        async with httpx.AsyncClient(transport=self.transport, timeout=1.5) as client:
            response = await client.post(
                self.url,
                json={"state": state, "questions": questions},
                headers=headers,
            )
            response.raise_for_status()
        payload = response.json()
        payload.pop("provider", None)
        return DecisionResult(provider=self.name, **payload)


class TypeSafeJevProvider(HttpDecisionProvider):
    name = "typesafe-jev"

    def __init__(
        self,
        url: str,
        *,
        api_key: str,
        model: str = "jev-latest",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        super().__init__(url, api_key=api_key, transport=transport)
        self.model = model

    async def evaluate(self, state: dict[str, Any], questions: dict[str, Any]) -> DecisionResult:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {
            "model": self.model,
            "state": {"learner": state, "question_inventory": questions},
            "questions": {
                "difficulty_preset": {
                    "type": "choice",
                    "instructions": "Choose the most useful difficulty mix for the next exam.",
                    "criteria": {
                        "foundation": "Mostly foundational questions for a struggling learner.",
                        "standard": "Balanced foundational, intermediate, and advanced questions.",
                        "intensive": "Emphasize intermediate and advanced questions.",
                        "hard": "Use mostly advanced questions for a strong learner.",
                    },
                },
            },
        }
        async with httpx.AsyncClient(transport=self.transport, timeout=5.0) as client:
            response = await client.post(self.url, json=payload, headers=headers)
            response.raise_for_status()
        answers = response.json()["answers"]
        difficulty_answer = answers["difficulty_preset"]
        presets = {
            "foundation": {"L1": 20, "L2": 16, "L3": 4},
            "standard": {"L1": 12, "L2": 20, "L3": 8},
            "intensive": {"L1": 6, "L2": 20, "L3": 14},
            "hard": {"L1": 2, "L2": 14, "L3": 24},
        }
        preset = str(difficulty_answer["choice"])
        if preset not in presets:
            raise ValueError(f"unknown Jev difficulty preset: {preset}")
        local_weights = await RuleBasedProvider().evaluate(state, questions)
        return DecisionResult(
            provider=self.name,
            template_id=str(state.get("requested_template", "exam-g-mixed")),
            difficulty=presets[preset],
            topic_weights=local_weights.topic_weights,
            confidence=float(difficulty_answer.get("confidence", 0.0)),
        )


class NanoJevProvider(HttpDecisionProvider):
    name = "nanojev"


class VonProvider(HttpDecisionProvider):
    name = "von"


class RuleBasedProvider:
    name = "rule-based"

    async def evaluate(self, state: dict[str, Any], questions: dict[str, Any]) -> DecisionResult:
        del questions
        weights: defaultdict[str, float] = defaultdict(float)
        groups = (
            (state.get("recent_wrong_topics", []), 0.40),
            (_lowest_mastery(state.get("mastery", {})), 0.25),
            (state.get("uncovered_topics", []), 0.20),
            (state.get("mastered_topics", []), 0.10),
        )
        for topics, budget in groups:
            unique = list(dict.fromkeys(topics))
            for topic in unique:
                weights[str(topic)] += budget / len(unique)

        weak = state.get("weak_domain")
        template = state.get("requested_template") or (
            "exam-d-mle" if weak == "mle" else "exam-a-sde" if weak == "sde" else "exam-g-mixed"
        )
        accuracy = float(state.get("recent_accuracy", 0.7))
        presets = {
            "foundation": {"L1": 20, "L2": 16, "L3": 4},
            "standard": {"L1": 12, "L2": 20, "L3": 8},
            "intensive": {"L1": 6, "L2": 20, "L3": 14},
            "hard": {"L1": 2, "L2": 14, "L3": 24},
        }
        requested_difficulty = state.get("requested_difficulty")
        difficulty = presets.get(str(requested_difficulty)) or (
            presets["intensive"]
            if accuracy >= 0.85
            else presets["foundation"]
            if accuracy < 0.55
            else presets["standard"]
        )
        return DecisionResult(
            provider=self.name,
            template_id=template,
            difficulty=difficulty,
            topic_weights=dict(weights),
        )


def _lowest_mastery(mastery: dict[str, Any]) -> list[str]:
    if not mastery:
        return []
    ordered = sorted(mastery, key=lambda topic: float(mastery[topic]))
    return ordered[: max(1, len(ordered) // 4)]
