#!/usr/bin/env python3
"""
测试运行器 —— 用例收集/执行/截图。

Claude 驱动模式：Claude 读测试代码 → 理解步骤 → 逐步调用脚本 → 每步截图判断。

子命令:
  collect         --dir PROJECT_DIR                    列出所有测试用例
  run             --dir PROJECT_DIR --test TEST_ID -d DEVICE  运行单个测试
  screenshot      -d DEVICE --out PATH                 截图保存
  assert-screen   -d DEVICE --dir PROJECT_DIR --run RUN_ID --step STEP  截图+dump供Claude判断
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import subprocess
import sys
import time
from datetime import datetime

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def collect(project_dir: str) -> dict:
    """用 ast 模块解析 test_*.py，列出所有测试（不 import）"""
    project_dir = os.path.abspath(project_dir)
    tests_dir = os.path.join(project_dir, "tests")

    if not os.path.isdir(tests_dir):
        return {"success": False, "error": f"tests/ 目录不存在: {tests_dir}"}

    tests = []
    for fname in sorted(os.listdir(tests_dir)):
        if not fname.startswith("test_") or not fname.endswith(".py"):
            continue

        fpath = os.path.join(tests_dir, fname)
        try:
            with open(fpath, "r") as f:
                tree = ast.parse(f.read(), filename=fname)
        except SyntaxError:
            continue

        module_name = fname[:-3]  # test_home_game_tab

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
                class_name = node.name
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name.startswith("test_"):
                        test_id = f"{module_name}::{class_name}::{item.name}"
                        docstring = ast.get_docstring(item) or ""
                        tests.append({
                            "id": test_id,
                            "file": fname,
                            "class": class_name,
                            "method": item.name,
                            "doc": docstring,
                            "line": item.lineno,
                        })

            # 模块级 test_ 函数
            elif isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                if not any(isinstance(parent, ast.ClassDef) for parent in ast.walk(tree)):
                    test_id = f"{module_name}::{node.name}"
                    docstring = ast.get_docstring(node) or ""
                    tests.append({
                        "id": test_id,
                        "file": fname,
                        "class": None,
                        "method": node.name,
                        "doc": docstring,
                        "line": node.lineno,
                    })

    return {
        "success": True,
        "project_dir": project_dir,
        "test_count": len(tests),
        "tests": tests,
    }


def run(project_dir: str, test_id: str, device: str = None) -> dict:
    """用 pytest subprocess 运行单个测试"""
    project_dir = os.path.abspath(project_dir)

    env = os.environ.copy()
    env["DROID_PILOT_SKILL_DIR"] = SKILL_DIR
    if device:
        env["DEVICE_ID"] = device

    # 转换 test_id 格式: test_home::TestHome::test_x → tests/test_home.py::TestHome::test_x
    parts = test_id.split("::")
    test_file = parts[0]
    if not test_file.endswith(".py"):
        test_file += ".py"
    pytest_id = os.path.join("tests", test_file)
    if len(parts) > 1:
        pytest_id += "::" + "::".join(parts[1:])

    cmd = [
        sys.executable, "-m", "pytest",
        pytest_id,
        "-v", "--tb=short", "--no-header",
        "-x",  # 遇到失败立即停止
    ]

    start = time.time()
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=project_dir,
        env=env,
        timeout=120,
    )
    duration = round(time.time() - start, 3)

    return {
        "success": result.returncode == 0,
        "test_id": test_id,
        "exit_code": result.returncode,
        "duration": duration,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def screenshot(device: str, out_path: str) -> dict:
    """截图保存"""
    out_path = os.path.abspath(out_path)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    cmd = ["adb"]
    if device:
        cmd += ["-s", device]
    cmd += ["exec-out", "screencap", "-p"]

    result = subprocess.run(cmd, capture_output=True, timeout=10)
    if result.returncode != 0:
        return {"success": False, "error": "screencap failed"}

    with open(out_path, "wb") as f:
        f.write(result.stdout)

    return {
        "success": True,
        "path": out_path,
        "size": len(result.stdout),
    }


def assert_screen(device: str, project_dir: str, run_id: str, step: str) -> dict:
    """截图 + dump 上下文，供 Claude 判断 pass/fail"""
    project_dir = os.path.abspath(project_dir)

    # 创建截图目录
    screenshots_dir = os.path.join(project_dir, "reports", run_id, "screenshots")
    os.makedirs(screenshots_dir, exist_ok=True)

    # 截图
    screenshot_path = os.path.join(screenshots_dir, f"{step}.png")
    shot_result = screenshot(device, screenshot_path)

    # dump 上下文
    ctx_cmd = [sys.executable, os.path.join(SKILL_DIR, "scripts", "screen_context.py"),
               "-f", "json", "-c"]
    if device:
        ctx_cmd += ["-d", device]

    ctx_result = subprocess.run(ctx_cmd, capture_output=True, text=True, timeout=30)
    context = {}
    if ctx_result.returncode == 0:
        try:
            context = json.loads(ctx_result.stdout)
        except json.JSONDecodeError:
            pass

    return {
        "success": True,
        "step": step,
        "screenshot": screenshot_path if shot_result.get("success") else None,
        "context": context,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def main():
    parser = argparse.ArgumentParser(description="测试运行器")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_collect = sub.add_parser("collect", help="收集测试用例")
    p_collect.add_argument("--dir", required=True, help="项目目录")

    p_run = sub.add_parser("run", help="运行单个测试")
    p_run.add_argument("--dir", required=True, help="项目目录")
    p_run.add_argument("--test", required=True, help="测试 ID")
    p_run.add_argument("--device", "-d", help="设备 ID")

    p_shot = sub.add_parser("screenshot", help="截图")
    p_shot.add_argument("--device", "-d", help="设备 ID")
    p_shot.add_argument("--out", required=True, help="输出路径")

    p_assert = sub.add_parser("assert-screen", help="截图+dump供Claude判断")
    p_assert.add_argument("--device", "-d", help="设备 ID")
    p_assert.add_argument("--dir", required=True, help="项目目录")
    p_assert.add_argument("--run", required=True, help="运行 ID")
    p_assert.add_argument("--step", required=True, help="步骤名")

    args = parser.parse_args()

    if args.cmd == "collect":
        result = collect(args.dir)
    elif args.cmd == "run":
        result = run(args.dir, args.test, args.device)
    elif args.cmd == "screenshot":
        result = screenshot(args.device, args.out)
    elif args.cmd == "assert-screen":
        result = assert_screen(args.device, args.dir, args.run, args.step)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
