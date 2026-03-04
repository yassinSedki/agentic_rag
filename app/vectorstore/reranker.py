"""Reranker utilities — Reciprocal Rank Fusion (RRF).

Used to combine results from dense vector search and sparse BM25 keyword
search into a single ranked list.

Reference:
    Cormack, G. V., Clarke, C.L., and Buettcher, S. (2009).
    "Reciprocal rank fusion outperforms condorcet and individual rank
    learning methods."  SIGIR '09.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ScoredItem:
    """A generic item with a score from a ranking source."""

    item_id: str
    content: str
    metadata: dict[str, Any]
    score: float = 0.0


def reciprocal_rank_fusion(
    *ranked_lists: list[ScoredItem],
    k: int = 60,
) -> list[ScoredItem]:
    """Combine multiple ranked lists using Reciprocal Rank Fusion.

    Parameters
    ----------
    *ranked_lists:
        One or more lists of ``ScoredItem``, each ordered by relevance
        (most relevant first).
    k:
        RRF constant.  Higher values reduce the influence of rank position.
        The default ``60`` is common in the literature.

    Returns
    -------
    list[ScoredItem]
        Merged list sorted by fused score (descending).
    """
    fused_scores: dict[str, float] = {}
    item_map: dict[str, ScoredItem] = {}

    for ranked_list in ranked_lists:
        for rank, item in enumerate(ranked_list, start=1):
            fused_scores[item.item_id] = fused_scores.get(item.item_id, 0.0) + 1.0 / (
                k + rank
            )
            # Keep the entry with highest original score
            if item.item_id not in item_map or item.score > item_map[item.item_id].score:
                item_map[item.item_id] = item

    # Build final list with fused scores
    result: list[ScoredItem] = []
    for item_id, fused_score in sorted(
        fused_scores.items(), key=lambda x: x[1], reverse=True
    ):
        entry = item_map[item_id]
        entry.score = fused_score
        result.append(entry)

    return result


def weighted_score_fusion(
    dense_results: list[ScoredItem],
    sparse_results: list[ScoredItem],
    dense_weight: float = 0.7,
    sparse_weight: float = 0.3,
) -> list[ScoredItem]:
    """Combine dense and sparse results using weighted score fusion.

    Parameters
    ----------
    dense_results:
        Results from dense (embedding) search, scored 0–1.
    sparse_results:
        Results from sparse (BM25) search, scored 0–1.
    dense_weight:
        Weight for the dense scores (default 0.7).
    sparse_weight:
        Weight for the sparse scores (default 0.3).

    Returns
    -------
    list[ScoredItem]
        Merged list sorted by weighted score (descending).
    """
    combined: dict[str, ScoredItem] = {}

    for item in dense_results:
        combined[item.item_id] = ScoredItem(
            item_id=item.item_id,
            content=item.content,
            metadata=item.metadata,
            score=item.score * dense_weight,
        )

    for item in sparse_results:
        if item.item_id in combined:
            combined[item.item_id].score += item.score * sparse_weight
        else:
            combined[item.item_id] = ScoredItem(
                item_id=item.item_id,
                content=item.content,
                metadata=item.metadata,
                score=item.score * sparse_weight,
            )

    return sorted(combined.values(), key=lambda x: x.score, reverse=True)
