from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path
from typing import Any


class InventoryShortage(ValueError):
    pass


DIFFICULTY_PRESET_QUOTAS = {
    "foundation": {
        ("L1", "single_choice"): 15,
        ("L1", "fill_blank"): 5,
        ("L2", "single_choice"): 12,
        ("L2", "fill_blank"): 4,
        ("L3", "single_choice"): 3,
        ("L3", "fill_blank"): 1,
    },
    "standard": {
        ("L1", "single_choice"): 9,
        ("L1", "fill_blank"): 3,
        ("L2", "single_choice"): 15,
        ("L2", "fill_blank"): 5,
        ("L3", "single_choice"): 6,
        ("L3", "fill_blank"): 2,
    },
    "intensive": {
        ("L1", "single_choice"): 5,
        ("L1", "fill_blank"): 1,
        ("L2", "single_choice"): 15,
        ("L2", "fill_blank"): 5,
        ("L3", "single_choice"): 10,
        ("L3", "fill_blank"): 4,
    },
    "hard": {
        ("L1", "single_choice"): 2,
        ("L1", "fill_blank"): 0,
        ("L2", "single_choice"): 10,
        ("L2", "fill_blank"): 4,
        ("L3", "single_choice"): 18,
        ("L3", "fill_blank"): 6,
    },
}

# Backward-compatible name for callers and documentation referring to the standard preset.
DIFFICULTY_TYPE_QUOTAS = DIFFICULTY_PRESET_QUOTAS["standard"]

TEMPLATE_DOMAINS = {
    "exam-a-sde": {"sde": 40},
    "exam-d-mle": {"mle": 40},
    "exam-g-mixed": {"sde": 20, "mle": 20},
}

TEMPLATE_TOPIC_QUOTAS = {
    "exam-a-sde": {
        "data_structures_algorithms": 12,
        "operating_systems": 7,
        "networks": 7,
        "databases": 7,
        "backend_systems": 7,
    },
    "exam-d-mle": {
        "math_statistics": 12,
        "classical_ml": 9,
        "mlops_evaluation": 10,
        "deep_learning": 9,
    },
    "exam-g-mixed": {
        "data_structures_algorithms": 6,
        "operating_systems": 3,
        "networks": 2,
        "databases": 3,
        "backend_systems": 6,
        "math_statistics": 2,
        "classical_ml": 3,
        "mlops_evaluation": 2,
        "deep_learning": 3,
        "pytorch_training": 2,
        "transformer_llm": 5,
        "ml_systems_inference": 3,
    },
}


QUALITY_STYLES = {
    "concept", "scenario", "code_reasoning", "debugging", "system_design", "tradeoff", "calculation"
}


def is_quality_question(question: dict[str, Any]) -> bool:
    """True for the append-only v2 inventory used for new practice papers."""
    return (
        question.get("version", 1) >= 2
        and question.get("selection_status", "active") == "active"
        and question.get("source_kind") in {"curated", "imported"}
        and question.get("question_style") in QUALITY_STYLES
    )


def _quality_paper(
    questions: list[dict[str, Any]], template_id: str, locale: str, seed: int,
    difficulty_preset: str, difficulty_quotas: dict[str, int] | None,
    topic_weights: dict[str, float],
) -> list[dict[str, Any]] | None:
    """Deterministic greedy selector for the modern, non-template question bank.

    It deliberately treats the legacy generated bank as fallback only.  A paper has
    no family repetition, keeps arithmetic as a small minority, and spreads across
    interview reasoning styles.  Review papers never call this function.
    """
    required_domains = TEMPLATE_DOMAINS[template_id]
    candidates = [q for q in questions if q.get("verified") and locale in q.get("content_i18n", {}) and is_quality_question(q)]
    if len(candidates) < 40 or any(sum(q.get("domain") == d for q in candidates) < n for d, n in required_domains.items()):
        return None
    targets = difficulty_quotas or {
        "foundation": {"L1": 20, "L2": 16, "L3": 4}, "standard": {"L1": 6, "L2": 20, "L3": 14},
        "intensive": {"L1": 6, "L2": 20, "L3": 14}, "hard": {"L1": 2, "L2": 14, "L3": 24},
    }[difficulty_preset]
    # The quality contract is intentionally stronger than a preset if stock permits.
    if sum(q.get("difficulty") == "L3" for q in candidates) >= 14:
        targets = {**targets, "L3": max(14, targets.get("L3", 0))}
        overflow = sum(targets.values()) - 40
        if overflow:
            for level in ("L2", "L1"):
                take = min(overflow, targets.get(level, 0))
                targets[level] -= take; overflow -= take
                if not overflow: break
    rng = random.Random(seed)
    shuffled = candidates[:]; rng.shuffle(shuffled)
    style_seen: Counter[str] = Counter()
    type_seen: Counter[str] = Counter()
    family_seen: set[str] = set(); selected: list[dict[str, Any]] = []
    domain_left = Counter(required_domains); level_left = Counter(targets)
    def score(q: dict[str, Any]) -> tuple[float, float, float, str]:
        style = str(q.get("question_style"))
        style_need = 4.0 if style_seen[style] == 0 and style != "calculation" else 0.0
        difficulty_need = 2.0 if level_left[q.get("difficulty")] > 0 else -2.0
        topic = str(q.get("topic")); weighted = float(topic_weights.get(topic, topic_weights.get(str(q.get("concept")), 0.0)))
        return (difficulty_need + style_need + weighted, float(domain_left[q.get("domain")]), -style_seen[style], q["id"])
    while len(selected) < 40:
        remaining = 40 - len(selected)
        permitted = []
        for q in shuffled:
            if q in selected or q.get("question_family_id") in family_seen: continue
            if domain_left[q.get("domain")] <= 0: continue
            if q.get("question_style") == "calculation" and style_seen["calculation"] >= 6: continue
            if q.get("type") == "single_choice" and type_seen["single_choice"] >= 30: continue
            if q.get("type") == "fill_blank" and type_seen["fill_blank"] >= 10: continue
            # Do not consume a needed domain slot with a wrong difficulty while a matching option exists.
            permitted.append(q)
        if not permitted: return None
        matching = [q for q in permitted if level_left[q.get("difficulty")] > 0]
        pool = matching or permitted
        pool.sort(key=score, reverse=True)
        chosen = pool[0]
        selected.append(chosen); family_seen.add(str(chosen.get("question_family_id")))
        domain_left[chosen["domain"]] -= 1; level_left[chosen["difficulty"]] -= 1
        style_seen[str(chosen.get("question_style"))] += 1
        type_seen[str(chosen.get("type"))] += 1
    # A malformed external import must not quietly degrade a full paper.
    if (
        len({q.get("question_style") for q in selected}) < 5
        or style_seen["calculation"] > 6
        or type_seen["single_choice"] != 30
        or type_seen["fill_blank"] != 10
    ):
        return None
    return [_localize(q, locale) for q in selected]


def load_questions(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    questions: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, 1):
            if not line.strip():
                continue
            try:
                question = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL at line {line_number}") from exc
            if question.get("verified") is True:
                questions.append(question)
    return questions


def _localize(question: dict[str, Any], locale: str) -> dict[str, Any]:
    content = question.get("content_i18n", {}).get(locale)
    if not content:
        raise InventoryShortage(f"question {question.get('id')} is missing locale {locale}")
    snapshot = {key: value for key, value in question.items() if key != "content_i18n"}
    snapshot.update(content)
    snapshot["locale"] = locale
    return snapshot


def build_standard_paper(
    questions: list[dict[str, Any]],
    template_id: str,
    locale: str,
    seed: int,
    difficulty_preset: str = "standard",
    *,
    difficulty_quotas: dict[str, int] | None = None,
    topic_weights: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    if template_id not in TEMPLATE_DOMAINS:
        raise ValueError(f"unknown template: {template_id}")
    if difficulty_preset not in DIFFICULTY_PRESET_QUOTAS:
        raise ValueError(f"unknown difficulty preset: {difficulty_preset}")
    rng = random.Random(seed)
    cell_quotas = (
        _difficulty_type_quotas(difficulty_quotas)
        if difficulty_quotas is not None
        else DIFFICULTY_PRESET_QUOTAS[difficulty_preset]
    )
    topic_weights = topic_weights or {}
    quality = _quality_paper(
        questions, template_id, locale, seed, difficulty_preset, difficulty_quotas, topic_weights
    )
    if quality is not None:
        return quality
    eligible = [q for q in questions if q.get("verified") and locale in q.get("content_i18n", {})]
    required_domains = TEMPLATE_DOMAINS[template_id]
    if any(
        sum(q.get("domain") == domain for q in eligible) < count
        for domain, count in required_domains.items()
    ):
        raise InventoryShortage(f"not enough verified questions for {template_id}")

    blueprint = TEMPLATE_TOPIC_QUOTAS[template_id]
    if (
        difficulty_preset == "standard"
        and difficulty_quotas is None
        and not topic_weights
        and all(any(q.get("topic") == topic for q in eligible) for topic in blueprint)
    ):
        selected = _select_blueprint_questions(
            eligible,
            blueprint,
            cell_quotas,
            rng,
        )
        choice = [q for q in selected if q["type"] == "single_choice"]
        fill = [q for q in selected if q["type"] == "fill_blank"]
        rng.shuffle(choice)
        rng.shuffle(fill)
        return [_localize(q, locale) for q in choice + fill]

    # Solve the small cell/domain allocation exactly before sampling questions.
    cells = list(cell_quotas.items())
    domains = list(required_domains)

    def allocations(quota: int, limits: dict[str, int], index: int = 0) -> list[dict[str, int]]:
        if index == len(domains) - 1:
            value = quota
            return [{domains[index]: value}] if 0 <= value <= limits[domains[index]] else []
        domain = domains[index]
        possibilities: list[dict[str, int]] = []
        for value in range(min(quota, limits[domain]) + 1):
            for rest in allocations(quota - value, limits, index + 1):
                possibilities.append({domain: value, **rest})
        return possibilities

    def solve(index: int, remaining: Counter[str]) -> list[dict[str, int]] | None:
        if index == len(cells):
            return [] if not any(remaining.values()) else None
        (difficulty, qtype), quota = cells[index]
        limits = {
            domain: min(
                remaining[domain],
                sum(
                    q.get("domain") == domain
                    and q.get("difficulty") == difficulty
                    and q.get("type") == qtype
                    for q in eligible
                ),
            )
            for domain in domains
        }
        options = allocations(quota, limits)
        rng.shuffle(options)
        for option in options:
            after = remaining.copy()
            after.subtract(option)
            suffix = solve(index + 1, after)
            if suffix is not None:
                return [option, *suffix]
        return None

    plan = solve(0, Counter(required_domains))
    if plan is None:
        raise InventoryShortage("domain distribution cannot satisfy all hard constraints")
    selected: list[dict[str, Any]] = []
    for ((difficulty, qtype), _), allocation in zip(cells, plan, strict=True):
        for domain, count in allocation.items():
            pool = [
                q
                for q in eligible
                if q.get("difficulty") == difficulty
                and q.get("type") == qtype
                and q.get("domain") == domain
            ]
            rng.shuffle(pool)
            pool.sort(
                key=lambda question: (
                    -float(
                        topic_weights.get(
                            str(question.get("topic")),
                            topic_weights.get(str(question.get("concept")), 0.0),
                        )
                    )
                )
            )
            selected.extend(pool[:count])
    choice = [q for q in selected if q["type"] == "single_choice"]
    fill = [q for q in selected if q["type"] == "fill_blank"]
    rng.shuffle(choice)
    rng.shuffle(fill)
    return [_localize(q, locale) for q in choice + fill]


def _difficulty_type_quotas(difficulty_quotas: dict[str, int]) -> dict[tuple[str, str], int]:
    """Turn Jev's 40-question difficulty decision into the fixed 30/10 type split."""
    normalized = {level: int(difficulty_quotas.get(level, 0)) for level in ("L1", "L2", "L3")}
    if any(value < 0 for value in normalized.values()) or sum(normalized.values()) != 40:
        raise ValueError("adaptive difficulty quotas must contain exactly 40 questions")
    fill = {level: value // 4 for level, value in normalized.items()}
    remainder = 10 - sum(fill.values())
    ranked = sorted(
        normalized,
        key=lambda level: (normalized[level] % 4, normalized[level]),
        reverse=True,
    )
    for level in ranked[:remainder]:
        fill[level] += 1
    return {(level, "single_choice"): normalized[level] - fill[level] for level in normalized} | {
        (level, "fill_blank"): fill[level] for level in normalized
    }


def _select_blueprint_questions(
    eligible: list[dict[str, Any]],
    topic_quotas: dict[str, int],
    cell_quotas: dict[tuple[str, str], int],
    rng: random.Random,
) -> list[dict[str, Any]]:
    """Solve topic and difficulty/type quotas as an integral max-flow problem."""
    source = ("source",)
    sink = ("sink",)
    topics = list(topic_quotas)
    cells = list(cell_quotas)
    rng.shuffle(topics)
    rng.shuffle(cells)
    adjacency: dict[tuple[str, ...], list[tuple[str, ...]]] = {}
    residual: dict[tuple[tuple[str, ...], tuple[str, ...]], int] = {}

    def add_edge(left: tuple[str, ...], right: tuple[str, ...], capacity: int) -> None:
        adjacency.setdefault(left, []).append(right)
        adjacency.setdefault(right, []).append(left)
        residual[(left, right)] = capacity
        residual[(right, left)] = 0

    for topic in topics:
        topic_node = ("topic", topic)
        add_edge(source, topic_node, topic_quotas[topic])
        for difficulty, qtype in cells:
            cell_node = ("cell", difficulty, qtype)
            capacity = sum(
                q.get("topic") == topic
                and q.get("difficulty") == difficulty
                and q.get("type") == qtype
                for q in eligible
            )
            add_edge(topic_node, cell_node, capacity)
    for difficulty, qtype in cells:
        add_edge(("cell", difficulty, qtype), sink, cell_quotas[(difficulty, qtype)])

    flow = 0
    while True:
        parent: dict[tuple[str, ...], tuple[str, ...] | None] = {source: None}
        queue = [source]
        for node in queue:
            for neighbor in adjacency.get(node, []):
                if neighbor not in parent and residual[(node, neighbor)] > 0:
                    parent[neighbor] = node
                    queue.append(neighbor)
                    if neighbor == sink:
                        break
            if sink in parent:
                break
        if sink not in parent:
            break
        increment = 40
        node = sink
        while parent[node] is not None:
            increment = min(increment, residual[(parent[node], node)])
            node = parent[node]
        node = sink
        while parent[node] is not None:
            previous = parent[node]
            residual[(previous, node)] -= increment
            residual[(node, previous)] += increment
            node = previous
        flow += increment

    if flow != sum(topic_quotas.values()):
        raise InventoryShortage("topic blueprint cannot satisfy difficulty and type constraints")
    selected: list[dict[str, Any]] = []
    for topic in topic_quotas:
        for difficulty, qtype in cell_quotas:
            count = residual[(("cell", difficulty, qtype), ("topic", topic))]
            pool = [
                q
                for q in eligible
                if q.get("topic") == topic
                and q.get("difficulty") == difficulty
                and q.get("type") == qtype
            ]
            rng.shuffle(pool)
            selected.extend(pool[:count])
    if len(selected) != 40:
        raise InventoryShortage("topic blueprint produced an incomplete paper")
    return selected
