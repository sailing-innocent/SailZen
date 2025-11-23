# -*- coding: utf-8 -*-
# @file llm_mock_service.py
# @brief Mock entity extraction service using regex and simple heuristics (MVP)

from typing import List, Dict
import re
import random
import hashlib


ENTITY_TYPES = [
    "character",
    "location",
    "item",
    "organization",
    "concept",
]


def _stable_rand_choices(seed_text: str, count: int) -> List[str]:
    h = hashlib.sha256(seed_text.encode("utf-8")).hexdigest()
    rnd = random.Random(h)
    return [rnd.choice(ENTITY_TYPES) for _ in range(count)]


def extract_entities_mock(text: str, max_items: int = 20) -> List[Dict]:
    """Naive mock extraction: CJK 2-5 chars and Capitalized English phrases.
    Returns list of suggestions dicts.
    """
    if not text:
        return []

    cjk_matches = re.findall(r"[\u4e00-\u9fff]{2,5}", text)
    en_matches = [
        m.group(1)
        for m in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b", text)
    ]

    # Deduplicate while preserving order
    seen = set()
    candidates: List[str] = []
    for token in cjk_matches + en_matches:
        if token not in seen:
            seen.add(token)
            candidates.append(token)

    candidates = candidates[:max_items]
    types = _stable_rand_choices(text, len(candidates))

    suggestions: List[Dict] = []
    for idx, name in enumerate(candidates):
        etype = types[idx]
        start = text.find(name)
        end = start + len(name) if start >= 0 else None
        aliases = []
        # simple alias heuristic: substring or suffixed version
        if len(name) > 2:
            aliases.append(name[:2])
        if len(name) > 3:
            aliases.append(f"{name}·X")
        suggestions.append(
            {
                "canonical_name": name,
                "entity_type": etype,
                "aliases": aliases,
                "first_mention_text": name,
                "start_char": start if start >= 0 else None,
                "end_char": end if end is not None else None,
            }
        )

    return suggestions
