from __future__ import annotations

import httpx
import pytest

from app.decision.router import DecisionRouter


@pytest.mark.anyio
async def test_provider_failover_uses_nano_then_von_then_rules() -> None:
    calls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if request.url.port == 9101:
            return httpx.Response(503)
        if request.url.port == 9102:
            return httpx.Response(
                200, json={"template_id": "exam-d-mle", "difficulty": {"L1": 12, "L2": 20, "L3": 8}}
            )
        return httpx.Response(500)

    router = DecisionRouter(
        api_key=None,
        nano_url="http://127.0.0.1:9101",
        von_url="http://127.0.0.1:9102",
        transport=httpx.MockTransport(handler),
    )
    result = await router.evaluate({}, {})
    assert result.provider == "von"
    assert [":9101" in calls[0], ":9102" in calls[1]] == [True, True]


@pytest.mark.anyio
async def test_provider_key_is_header_only_and_never_in_result() -> None:
    seen: httpx.Request | None = None

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen
        seen = request
        return httpx.Response(
            200,
            json={
                "model": "jev-1.13.0",
                "answers": {
                    "template_id": {
                        "type": "choice",
                        "choice": "exam-g-mixed",
                        "confidence": 1.0,
                    },
                    "difficulty_preset": {
                        "type": "choice",
                        "choice": "intensive",
                        "confidence": 0.91,
                    },
                },
            },
        )

    router = DecisionRouter(
        api_key="test-provider-key",
        typesafe_url="https://jev.invalid",
        transport=httpx.MockTransport(handler),
    )
    result = await router.evaluate({}, {})
    assert result.provider == "typesafe-jev"
    assert result.template_id == "exam-g-mixed"
    assert result.difficulty == {"L1": 6, "L2": 20, "L3": 14}
    assert result.confidence == 0.91
    assert seen is not None and seen.headers["authorization"] == "Bearer test-provider-key"
    assert seen.url.path == "/"
    request_body = __import__("json").loads(seen.content)
    assert request_body["model"] == "jev-latest"
    assert "template_id" not in request_body["questions"]
    assert request_body["questions"]["difficulty_preset"]["type"] == "choice"
    assert "test-provider-key" not in result.model_dump_json()


@pytest.mark.anyio
async def test_provider_falls_back_to_weighted_rules() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    router = DecisionRouter(
        api_key=None,
        transport=httpx.MockTransport(handler),
    )
    result = await router.evaluate(
        {
            "weak_domain": "mle",
            "recent_accuracy": 0.9,
            "recent_wrong_topics": ["attention"],
            "mastery": {"attention": 0.2, "sql": 0.8},
            "uncovered_topics": ["cuda"],
            "mastered_topics": ["arrays"],
            "core_topics": ["metrics"],
        },
        {},
    )
    assert result.provider == "rule-based"
    assert result.template_id == "exam-d-mle"
    assert result.difficulty == {"L1": 6, "L2": 20, "L3": 14}
    assert result.topic_weights["attention"] > result.topic_weights["cuda"]
