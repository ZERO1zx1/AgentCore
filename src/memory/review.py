"""Review-queue model for interactive memory governance UIs and CLIs."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Mapping, Sequence
from html import escape
import json
from src.memory.governance import MemoryAction, PermissionPolicy


class ReviewDecision(str, Enum):
    USE = "use"
    IGNORE_ONCE = "ignore_once"
    MARK_STALE = "mark_stale"
    RETIRE = "retire"
    SHOW_EVIDENCE = "show_evidence"


@dataclass(frozen=True)
class ReviewCard:
    lesson_id: str
    problem: str
    action: str
    confidence: float
    freshness: float
    reason: str
    evidence: str

    def to_dict(self) -> Dict[str, Any]:
        return {**self.__dict__, "allowed_decisions": [item.value for item in ReviewDecision]}


def apply_review_decision(card: ReviewCard, decision: ReviewDecision | str,
                          role: str = "reviewer") -> Dict[str, Any]:
    selected = ReviewDecision(decision)
    PermissionPolicy.require(
        role,
        MemoryAction.RETIRE if selected in {ReviewDecision.MARK_STALE, ReviewDecision.RETIRE} else MemoryAction.READ,
    )
    return {"lesson_id": card.lesson_id, "decision": selected.value,
            "use_for_current_task": selected == ReviewDecision.USE,
            "requires_transition": selected in {ReviewDecision.MARK_STALE, ReviewDecision.RETIRE},
            "show_evidence": selected == ReviewDecision.SHOW_EVIDENCE}


def render_review_html(cards: Sequence[ReviewCard], title: str = "AgentCore Memory Review") -> str:
    """Return a dependency-free interactive review page; it does not mutate memory."""
    rendered = []
    for card in cards:
        buttons = "".join(
            f'<button type="button" onclick="decide(\'{escape(card.lesson_id)}\',\'{decision.value}\')">{escape(decision.value)}</button>'
            for decision in ReviewDecision
        )
        rendered.append(
            f'<article><h2>{escape(card.problem)}</h2><p>{escape(card.action)}</p>'
            f'<p>Confidence {card.confidence:.2f} · Freshness {card.freshness:.2f}</p>'
            f'<details><summary>Why and evidence</summary><p>{escape(card.reason)}</p>'
            f'<pre>{escape(card.evidence)}</pre></details><div>{buttons}</div></article>'
        )
    initial = json.dumps({}, ensure_ascii=False)
    return ("<!doctype html><html><head><meta charset=\"utf-8\"><title>" + escape(title) +
            "</title><style>body{font:16px system-ui;max-width:900px;margin:2rem auto;padding:0 1rem}"
            "article{border:1px solid #ccd;padding:1rem;margin:1rem 0;border-radius:10px}button{margin:.25rem}</style>"
            "</head><body><h1>" + escape(title) + "</h1>" + "".join(rendered) +
            f"<h2>Decision log</h2><pre id=\"log\">{initial}</pre><script>const decisions={{}};"
            "function decide(id,value){decisions[id]=value;document.getElementById('log').textContent=JSON.stringify(decisions,null,2);}" 
            "</script></body></html>")
