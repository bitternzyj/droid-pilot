#!/usr/bin/env python3
"""
项目脚手架 —— 生成自动化测试项目结构。

子命令:
  init    -p PKG --dir PROJECT_DIR   创建 tests/ pages/ 目录，生成 conftest.py 和 base_page.py
  status  --dir PROJECT_DIR          检查已有结构，返回 JSON
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from string import Template

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(SKILL_DIR, "templates")


def _read_template(name: str) -> str:
    """读取模板文件"""
    path = os.path.join(TEMPLATES_DIR, name)
    with open(path, "r") as f:
        return f.read()


def init(package: str, project_dir: str) -> dict:
    """创建项目结构，不覆盖已有文件"""
    project_dir = os.path.abspath(project_dir)
    created = []
    skipped = []

    # 创建目录
    for d in ["tests", "pages", "reports"]:
        dp = os.path.join(project_dir, d)
        os.makedirs(dp, exist_ok=True)

    # 生成 pages/__init__.py
    init_path = os.path.join(project_dir, "pages", "__init__.py")
    if not os.path.exists(init_path):
        with open(init_path, "w") as f:
            f.write("")
        created.append("pages/__init__.py")
    else:
        skipped.append("pages/__init__.py")

    # 生成 base_page.py
    base_page_path = os.path.join(project_dir, "pages", "base_page.py")
    if not os.path.exists(base_page_path):
        content = _read_template("base_page.py.tpl")
        with open(base_page_path, "w") as f:
            f.write(content)
        created.append("pages/base_page.py")
    else:
        skipped.append("pages/base_page.py")

    # 生成 conftest.py
    conftest_path = os.path.join(project_dir, "tests", "conftest.py")
    if not os.path.exists(conftest_path):
        tpl = _read_template("conftest.py.tpl")
        content = Template(tpl).safe_substitute(
            PACKAGE=package,
            PAGE_FIXTURES="# Page fixtures will be added by page_gen.py\n",
        )
        with open(conftest_path, "w") as f:
            f.write(content)
        created.append("tests/conftest.py")
    else:
        skipped.append("tests/conftest.py")

    # 生成 tests/__init__.py
    tests_init = os.path.join(project_dir, "tests", "__init__.py")
    if not os.path.exists(tests_init):
        with open(tests_init, "w") as f:
            f.write("")
        created.append("tests/__init__.py")
    else:
        skipped.append("tests/__init__.py")

    return {
        "success": True,
        "project_dir": project_dir,
        "package": package,
        "created": created,
        "skipped": skipped,
    }


def status(project_dir: str) -> dict:
    """检查项目结构状态"""
    project_dir = os.path.abspath(project_dir)

    checks = {
        "tests_dir": os.path.isdir(os.path.join(project_dir, "tests")),
        "pages_dir": os.path.isdir(os.path.join(project_dir, "pages")),
        "reports_dir": os.path.isdir(os.path.join(project_dir, "reports")),
        "base_page": os.path.isfile(os.path.join(project_dir, "pages", "base_page.py")),
        "conftest": os.path.isfile(os.path.join(project_dir, "tests", "conftest.py")),
    }

    # 列出已有的 page objects 和测试文件
    page_files = []
    pages_dir = os.path.join(project_dir, "pages")
    if os.path.isdir(pages_dir):
        page_files = [f[:-3] for f in os.listdir(pages_dir)
                      if f.endswith(".py") and f not in ("__init__.py", "base_page.py")]

    test_files = []
    tests_dir = os.path.join(project_dir, "tests")
    if os.path.isdir(tests_dir):
        test_files = [f[:-3] for f in os.listdir(tests_dir)
                      if f.startswith("test_") and f.endswith(".py")]

    report_dirs = []
    reports_dir = os.path.join(project_dir, "reports")
    if os.path.isdir(reports_dir):
        report_dirs = sorted([d for d in os.listdir(reports_dir)
                              if os.path.isdir(os.path.join(reports_dir, d))])

    initialized = all(checks.values())

    return {
        "project_dir": project_dir,
        "initialized": initialized,
        "checks": checks,
        "page_objects": page_files,
        "test_files": test_files,
        "reports": report_dirs,
    }


def main():
    parser = argparse.ArgumentParser(description="项目脚手架")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="初始化项目结构")
    p_init.add_argument("--package", "-p", required=True, help="应用包名")
    p_init.add_argument("--dir", required=True, help="项目目录")

    p_status = sub.add_parser("status", help="检查项目结构")
    p_status.add_argument("--dir", required=True, help="项目目录")

    args = parser.parse_args()

    if args.cmd == "init":
        result = init(args.package, args.dir)
    elif args.cmd == "status":
        result = status(args.dir)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
