from __future__ import annotations

from .drivers.base import Element


def compute_fingerprint(elements: list) -> set:
    """
    从元素列表提取页面指纹（identity 字符串集合）。
    只取有意义的标识，忽略纯坐标信息。
    """
    fp = set()
    for elem in elements:
        identity = elem.identity() if isinstance(elem, Element) else str(elem)
        if identity:
            fp.add(identity)
    return fp


def compute_page_fingerprint(page: dict) -> set:
    """从知识库 page dict 提取指纹"""
    fp = set()
    for key, info in page.get("elements", {}).items():
        text = info.get("text") or info.get("resource_id") or info.get("content_desc") or key
        if text:
            fp.add(text)
    return fp


def jaccard_similarity(set_a: set, set_b: set) -> float:
    """Jaccard 相似度：交集 / 并集"""
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union


def element_matches(elements: list, condition: dict) -> bool:
    """
    检查元素列表中是否存在满足 condition 的元素。
    condition 示例:
      {"text": "小游戏", "selected": True}
      {"resource_id": "btn_launch"}
    """
    for elem in elements:
        if not isinstance(elem, Element):
            continue
        match = True
        for key, val in condition.items():
            if key == "text" and elem.text != val:
                match = False
                break
            if key == "resource_id" and elem.resource_id != val:
                match = False
                break
            if key == "selected" and elem.selected != val:
                match = False
                break
            if key == "clickable" and elem.clickable != val:
                match = False
                break
        if match:
            return True
    return False
