#!/usr/bin/env python3
"""
页面知识库工具 —— 纯 I/O，不做 AI 分析。
AI 分析由 Claude (Skill) 直接完成。

模式:
  --dump   输出当前页面原始数据（供 Claude 分析）
  --write  接收 Claude 生成的 page dict，写入知识库文件

用法:
  # 1. Claude 调用 dump，获取原始数据
  python page_learn.py --dump -d DEVICE_ID

  # 2. Claude 分析后，调用 write 写入结果
  python page_learn.py --write -p com.xxx.xxx --data '{"id":"home","name":"主页",...}'

  # 也可以从 stdin 读 data
  echo '{...}' | python page_learn.py --write -p com.xxx.xxx
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SKILL_DIR)

from core.drivers.auto_driver import AutoDriver


# ------------------------------------------------------------------
# dump 模式：输出当前页面原始数据
# ------------------------------------------------------------------

def dump(device_id: str = None) -> dict:
    """连接设备，dump 当前页面，返回结构化数据供 Claude 分析"""
    driver = AutoDriver(device_id)

    # 获取包名
    package = ""
    try:
        import uiautomator2 as u2
        d = u2.connect(device_id) if device_id else u2.connect()
        app = d.app_current()
        package = app.get("package", "")
        full_activity = app.get("activity", "")
    except Exception as e:
        return {"error": f"连接失败: {e}"}

    activity = full_activity.split(".")[-1] if "." in full_activity else full_activity
    elements = driver.dump()
    used_driver = driver.driver_type()

    # 已有页面知识库（告诉 Claude 这个 app 已知哪些页面）
    known_pages = _load_known_page_ids(package)

    return {
        "package": package,
        "activity": activity,
        "full_activity": full_activity,
        "driver": used_driver,
        "element_count": len(elements),
        "known_pages": known_pages,
        "elements": [
            {
                k: v for k, v in {
                    "text": elem.text,
                    "resource_id": elem.resource_id,
                    "content_desc": elem.content_desc,
                    "type": elem.type,
                    "clickable": elem.clickable or None,
                    "checkable": elem.checkable or None,
                    "checked": elem.checked if elem.checkable else None,
                    "selected": elem.selected or None,
                    "norm_bounds": [round(v, 3) for v in elem.norm_bounds] if elem.norm_bounds else None,
                }.items() if v is not None and v != "" and v is not False
            }
            for elem in elements
        ],
    }


def _load_known_page_ids(package: str) -> list:
    pages_dir = os.path.join(SKILL_DIR, "knowledge", "pages", package)
    if not os.path.isdir(pages_dir):
        return []
    ids = []
    for fname in os.listdir(pages_dir):
        if fname.startswith("_") or not fname.endswith(".py"):
            continue
        fpath = os.path.join(pages_dir, fname)
        try:
            spec = importlib.util.spec_from_file_location(fname[:-3], fpath)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if hasattr(mod, "page"):
                ids.append(mod.page.get("id", fname[:-3]))
        except Exception:
            pass
    return ids


# ------------------------------------------------------------------
# write 模式：写入 Claude 生成的 page dict
# ------------------------------------------------------------------

def write(package: str, page: dict) -> str:
    """把 Claude 生成的 page dict 写入知识库文件，返回文件路径"""
    pkg_dir = os.path.join(SKILL_DIR, "knowledge", "pages", package)
    os.makedirs(pkg_dir, exist_ok=True)

    page_id = page.get("id")
    if not page_id:
        raise ValueError("page dict 缺少 'id' 字段")

    fpath = os.path.join(pkg_dir, f"{page_id}.py")
    content = _render_page_py(page)
    with open(fpath, "w") as f:
        f.write(content)

    _update_topology(package, page, pkg_dir)
    return fpath


def _to_py_literal(obj) -> str:
    """将 Python 对象转为合法的 Python 字面量字符串"""
    if isinstance(obj, bool):
        return "True" if obj else "False"
    if isinstance(obj, str):
        return json.dumps(obj, ensure_ascii=False)
    if isinstance(obj, (int, float)):
        return str(obj)
    if isinstance(obj, list):
        return "[" + ", ".join(_to_py_literal(v) for v in obj) + "]"
    if isinstance(obj, dict):
        pairs = ", ".join(
            f"{_to_py_literal(k)}: {_to_py_literal(v)}" for k, v in obj.items()
        )
        return "{" + pairs + "}"
    if obj is None:
        return "None"
    return repr(obj)


def _render_page_py(page: dict) -> str:
    lines = ["page = {"]
    lines.append(f'    "id": {_to_py_literal(page["id"])},')
    lines.append(f'    "name": {_to_py_literal(page.get("name", page["id"]))},')
    lines.append(f'    "driver": {_to_py_literal(page.get("driver", "auto"))},')
    lines.append("")
    lines.append('    "identify": {')
    identify = page.get("identify", {})
    if identify.get("activity"):
        lines.append(f'        "activity": {_to_py_literal(identify["activity"])},')
    must_have = identify.get("must_have", [])
    if must_have:
        lines.append('        "must_have": [')
        for cond in must_have:
            lines.append(f'            {_to_py_literal(cond)},')
        lines.append('        ],')
    lines.append('    },')
    lines.append("")
    lines.append('    "elements": {')
    for key, info in page.get("elements", {}).items():
        lines.append(f'        {_to_py_literal(key)}: {_to_py_literal(info)},')
    lines.append('    },')
    lines.append("")
    lines.append('    "overlays": {')
    for key, info in page.get("overlays", {}).items():
        lines.append(f'        {_to_py_literal(key)}: {_to_py_literal(info)},')
    lines.append('    },')
    lines.append("")
    lines.append('    "routes": {')
    for elem_key, target in page.get("routes", {}).items():
        lines.append(f'        {_to_py_literal(elem_key)}: {_to_py_literal(target)},')
    lines.append('    },')
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def _update_topology(package: str, page: dict, pkg_dir: str):
    topo_path = os.path.join(pkg_dir, "_topology.json")
    topo = {"nodes": {}, "edges": []}
    if os.path.exists(topo_path):
        with open(topo_path) as f:
            topo = json.load(f)

    page_id = page["id"]
    topo["nodes"][page_id] = {"name": page.get("name", page_id)}

    # 重建此页面的出边
    topo["edges"] = [e for e in topo["edges"] if e.get("from") != page_id]
    for elem_key, target_id in page.get("routes", {}).items():
        topo["edges"].append({"from": page_id, "element": elem_key, "to": target_id})

    with open(topo_path, "w") as f:
        json.dump(topo, f, ensure_ascii=False, indent=2)


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="页面知识库 I/O 工具")
    sub = parser.add_subparsers(dest="mode", required=True)

    # dump
    p_dump = sub.add_parser("dump", help="dump 当前页面原始数据")
    p_dump.add_argument("--device", "-d", help="设备 ID")

    # write
    p_write = sub.add_parser("write", help="写入 Claude 生成的 page dict")
    p_write.add_argument("--package", "-p", required=True, help="应用包名")
    p_write.add_argument("--data", help="page dict JSON 字符串（不填则从 stdin 读）")

    args = parser.parse_args()

    if args.mode == "dump":
        result = dump(args.device)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.mode == "write":
        raw = args.data if args.data else sys.stdin.read()
        page = json.loads(raw)
        fpath = write(args.package, page)
        print(json.dumps({"success": True, "file": fpath}, ensure_ascii=False))


if __name__ == "__main__":
    main()
