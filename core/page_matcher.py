from __future__ import annotations

from .fingerprint import (
    compute_fingerprint,
    compute_page_fingerprint,
    jaccard_similarity,
    element_matches,
)

# 综合得分超过此阈值才认为匹配
MATCH_THRESHOLD = 0.55

# 权重
W_ACTIVITY = 0.4
W_JACCARD = 0.6


def match_page(activity: str, elements: list, pages: list) -> tuple:
    """
    在已知页面列表中找到最匹配的页面。

    Returns:
        (page_dict, score) — 若无匹配超过阈值，返回 (None, 0.0)
    """
    current_fp = compute_fingerprint(elements)
    best_page = None
    best_score = 0.0

    for page in pages:
        score = _score_page(activity, current_fp, elements, page)
        if score > best_score:
            best_score = score
            best_page = page

    if best_score >= MATCH_THRESHOLD:
        return best_page, best_score
    return None, best_score


def _score_page(activity: str, current_fp: set, elements: list, page: dict) -> float:
    identify = page.get("identify", {})

    # --- Activity 匹配（权重 0.4）---
    page_activity = identify.get("activity", "")
    if page_activity:
        # 只要 activity 包含 page_activity 即可（处理全名 vs 短名）
        activity_score = 1.0 if page_activity in activity else 0.0
        # activity 明确不匹配，直接排除
        if activity_score == 0.0:
            return 0.0
    else:
        activity_score = 0.5  # 无 activity 约束，给中性分

    # --- must_have 检查（硬性条件）---
    for condition in identify.get("must_have", []):
        if not element_matches(elements, condition):
            return 0.0

    # --- Jaccard 相似度（权重 0.6）---
    page_fp = compute_page_fingerprint(page)
    jaccard = jaccard_similarity(current_fp, page_fp)

    return activity_score * W_ACTIVITY + jaccard * W_JACCARD
