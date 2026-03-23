#!/usr/bin/env python3
"""
识别当前页面：连接设备 → dump → 匹配知识库 → 输出结果

用法:
    python page_identify.py -d DEVICE_ID
    python page_identify.py -d DEVICE_ID --package com.example.myapp
    python page_identify.py -d DEVICE_ID --format json
"""
import argparse
import importlib.util
import json
import os
import sys

# 让 core 包可以 import
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SKILL_DIR)

from core.drivers.auto_driver import AutoDriver
from core.page_matcher import match_page, MATCH_THRESHOLD


# ------------------------------------------------------------------
# 知识库加载
# ------------------------------------------------------------------

def load_pages(package: str) -> list:
    """从 knowledge/pages/{package}/ 加载所有 page dict"""
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
                page = mod.page
                page["_file"] = fpath
                # 注册驱动 hint（供后续 AutoDriver 使用）
                pages.append(page)
        except Exception as e:
            print(f"  [warn] 加载 {fname} 失败: {e}", file=sys.stderr)

    return pages


def load_all_packages() -> dict:
    """加载所有应用的页面，返回 {package: [pages]}"""
    pages_root = os.path.join(SKILL_DIR, "knowledge", "pages")
    if not os.path.isdir(pages_root):
        return {}
    result = {}
    for pkg in os.listdir(pages_root):
        pkg_dir = os.path.join(pages_root, pkg)
        if os.path.isdir(pkg_dir):
            pages = load_pages(pkg)
            if pages:
                result[pkg] = pages
    return result


# ------------------------------------------------------------------
# 主流程
# ------------------------------------------------------------------

def identify(device_id: str = None, package: str = None) -> dict:
    driver = AutoDriver(device_id)

    # 获取当前状态
    activity = driver.current_activity()
    elements = driver.dump()
    used_driver = driver.driver_type()

    # 确定要搜索的 package
    if not package:
        # 从 u2 获取当前包名
        try:
            import uiautomator2 as u2
            d = u2.connect(device_id) if device_id else u2.connect()
            package = d.app_current().get("package", "")
        except Exception:
            package = ""

    result = {
        "package": package,
        "activity": activity,
        "element_count": len(elements),
        "driver": used_driver,
        "matched_page": None,
        "score": 0.0,
        "status": "unknown",
    }

    # 加载知识库
    if package:
        pages = load_pages(package)
    else:
        # 未知包名，搜全部
        all_pages = load_all_packages()
        pages = [p for ps in all_pages.values() for p in ps]

    if not pages:
        result["status"] = "no_knowledge"
        return result

    # 匹配
    matched, score = match_page(activity, elements, pages)
    result["score"] = round(score, 3)

    if matched:
        result["matched_page"] = matched.get("id")
        result["matched_name"] = matched.get("name", "")
        result["matched_driver_hint"] = matched.get("driver", "auto")
        result["status"] = "matched"
    else:
        result["status"] = "new_page"

    return result


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="识别当前页面")
    parser.add_argument("--device", "-d", help="设备 ID")
    parser.add_argument("--package", "-p", help="应用包名（不填则自动检测）")
    parser.add_argument("--format", "-f", choices=["text", "json"], default="text")
    args = parser.parse_args()

    result = identify(args.device, args.package)

    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    # 文本格式
    status = result["status"]
    pkg = result["package"] or "?"
    act = result["activity"] or "?"
    drv = result["driver"]
    elem_count = result["element_count"]

    print(f"Package  : {pkg}")
    print(f"Activity : {act}")
    print(f"Driver   : {drv}  ({elem_count} elements)")

    if status == "matched":
        page_id = result["matched_page"]
        name = result.get("matched_name", "")
        score = result["score"]
        hint = result.get("matched_driver_hint", "auto")
        print(f"Page     : [{page_id}] {name}  (score: {score}, driver_hint: {hint})")
    elif status == "new_page":
        score = result["score"]
        print(f"Page     : [UNKNOWN] 未匹配已知页面 (best_score: {score})")
        print(f"           建议运行 page_learn.py 学习此页面")
    elif status == "no_knowledge":
        print(f"Page     : [NO KNOWLEDGE] 该应用暂无知识库")
        print(f"           建议运行 page_learn.py 初始化")
    else:
        print(f"Page     : [ERROR] {status}")


if __name__ == "__main__":
    main()
