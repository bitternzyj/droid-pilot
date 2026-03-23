#!/usr/bin/env python3
"""
探索状态管理 —— 纯 I/O，不做决策。
决策由 Claude (Skill) 完成。

职责：
  - 维护探索进度（已访问页面、已阻塞路由）
  - 输出当前状态供 Claude 决策
  - 记录 Claude 指令的执行结果

子命令:
  status    -d DEVICE -p PACKAGE   当前状态（我在哪，下一步探哪）
  visited   -p PACKAGE --page ID   标记页面为已访问
  blocked   -p PACKAGE --page ID --route ELEM --reason "xxx"  标记路由阻塞
  reset     -p PACKAGE             清空探索进度

状态文件: knowledge/pages/{package}/_explore_state.json
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from datetime import datetime

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SKILL_DIR)

from core.drivers.auto_driver import AutoDriver
from core.page_matcher import match_page


# ------------------------------------------------------------------
# 状态文件 I/O
# ------------------------------------------------------------------

def _state_path(package: str) -> str:
    return os.path.join(SKILL_DIR, "knowledge", "pages", package, "_explore_state.json")


def _load_state(package: str) -> dict:
    path = _state_path(package)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {
        "package": package,
        "visited": [],          # 已访问的 page_id 列表
        "blocked_routes": [],   # [{"from": page_id, "element": key, "reason": "..."}]
        "sessions": [],
    }


def _save_state(package: str, state: dict):
    path = _state_path(package)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ------------------------------------------------------------------
# 知识库加载
# ------------------------------------------------------------------

def _load_topology(package: str) -> dict:
    topo_path = os.path.join(SKILL_DIR, "knowledge", "pages", package, "_topology.json")
    if os.path.exists(topo_path):
        with open(topo_path) as f:
            return json.load(f)
    return {"nodes": {}, "edges": []}


def _load_pages(package: str) -> list:
    pages_dir = os.path.join(SKILL_DIR, "knowledge", "pages", package)
    if not os.path.isdir(pages_dir):
        return []
    pages = []
    for fname in os.listdir(pages_dir):
        if fname.startswith("_") or not fname.endswith(".py"):
            continue
        fpath = os.path.join(pages_dir, fname)
        try:
            spec = importlib.util.spec_from_file_location(fname[:-3], fpath)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if hasattr(mod, "page"):
                pages.append(mod.page)
        except Exception:
            pass
    return pages


# ------------------------------------------------------------------
# status：当前探索状态
# ------------------------------------------------------------------

def status(device_id: str, package: str) -> dict:
    """
    返回当前探索状态，供 Claude 决策下一步。
    输出结构：
      current_page: 当前匹配到的页面（或 null）
      is_known: 当前页面是否已在知识库中
      next_routes: 建议探索的路由列表（未访问、未阻塞）
      coverage: 已访问/总节点 比例
      blocked_routes: 已标记阻塞的路由
      suggestion: Claude 应该做什么（explore/learn/blocked/done）
    """
    state = _load_state(package)
    topo = _load_topology(package)
    pages = _load_pages(package)

    # 获取当前页面
    driver = AutoDriver(device_id)
    activity = driver.current_activity()
    elements = driver.dump()

    matched, score = match_page(activity, elements, pages)
    current_page_id = matched["id"] if matched else None

    # 计算未探索路由
    visited = set(state["visited"])
    blocked = {(r["from"], r["element"]) for r in state["blocked_routes"]}

    next_routes = []
    if current_page_id:
        for edge in topo.get("edges", []):
            if edge["from"] != current_page_id:
                continue
            target = edge["to"]
            elem_key = edge["element"]
            if target in visited:
                continue
            if (current_page_id, elem_key) in blocked:
                continue
            # 找到这个元素的定位方式
            elem_info = (matched or {}).get("elements", {}).get(elem_key, {})
            next_routes.append({
                "element_key": elem_key,
                "target_page": target,
                "locator": {k: v for k, v in elem_info.items()
                            if k in ("text", "resource_id", "norm_bounds")},
            })

    # 总节点数（知识库中已知 + 拓扑中占位的）
    all_nodes = set(topo.get("nodes", {}).keys())
    coverage = f"{len(visited)}/{len(all_nodes)}" if all_nodes else "0/0"

    # 给 Claude 的行动建议
    if not matched:
        suggestion = "learn"  # 当前页面未知，先学习
    elif next_routes:
        suggestion = "explore"  # 有未探索路由，继续走
    elif len(visited) < len(all_nodes):
        suggestion = "navigate_back"  # 当前页面路由都探完了，需要回退找其他路径
    else:
        suggestion = "done"

    return {
        "package": package,
        "current_page": current_page_id,
        "current_page_name": (matched or {}).get("name"),
        "current_activity": activity,
        "is_known": matched is not None,
        "match_score": round(score, 3),
        "element_count": len(elements),
        "next_routes": next_routes,
        "visited": sorted(visited),
        "coverage": coverage,
        "blocked_routes": state["blocked_routes"],
        "suggestion": suggestion,
    }


# ------------------------------------------------------------------
# visited / blocked / reset
# ------------------------------------------------------------------

def mark_visited(package: str, page_id: str) -> dict:
    state = _load_state(package)
    if page_id not in state["visited"]:
        state["visited"].append(page_id)
    _save_state(package, state)
    return {"success": True, "visited": state["visited"]}


def mark_blocked(package: str, from_page: str, element: str, reason: str) -> dict:
    state = _load_state(package)
    entry = {"from": from_page, "element": element, "reason": reason,
             "time": datetime.now().strftime("%Y-%m-%d %H:%M")}
    # 去重
    state["blocked_routes"] = [
        r for r in state["blocked_routes"]
        if not (r["from"] == from_page and r["element"] == element)
    ]
    state["blocked_routes"].append(entry)
    _save_state(package, state)
    return {"success": True, "blocked": entry}


def reset(package: str) -> dict:
    state = {
        "package": package,
        "visited": [],
        "blocked_routes": [],
        "sessions": [],
    }
    _save_state(package, state)
    return {"success": True, "message": f"{package} 探索进度已清空"}


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="探索状态管理")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_status = sub.add_parser("status", help="当前探索状态")
    p_status.add_argument("--device", "-d", required=True)
    p_status.add_argument("--package", "-p", required=True)

    p_visited = sub.add_parser("visited", help="标记页面已访问")
    p_visited.add_argument("--package", "-p", required=True)
    p_visited.add_argument("--page", required=True)

    p_blocked = sub.add_parser("blocked", help="标记路由阻塞")
    p_blocked.add_argument("--package", "-p", required=True)
    p_blocked.add_argument("--page", required=True, help="来源页面 id")
    p_blocked.add_argument("--route", required=True, help="元素 key")
    p_blocked.add_argument("--reason", default="未知原因")

    p_reset = sub.add_parser("reset", help="清空探索进度")
    p_reset.add_argument("--package", "-p", required=True)

    args = parser.parse_args()

    if args.cmd == "status":
        print(json.dumps(status(args.device, args.package), ensure_ascii=False, indent=2))
    elif args.cmd == "visited":
        print(json.dumps(mark_visited(args.package, args.page), ensure_ascii=False))
    elif args.cmd == "blocked":
        print(json.dumps(mark_blocked(args.package, args.page, args.route, args.reason), ensure_ascii=False))
    elif args.cmd == "reset":
        print(json.dumps(reset(args.package), ensure_ascii=False))


if __name__ == "__main__":
    main()
