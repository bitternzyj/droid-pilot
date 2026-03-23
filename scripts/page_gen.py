#!/usr/bin/env python3
"""
Page Object 生成器 —— 从知识库生成 Page Object 类和测试骨架。

子命令:
  list      -p PKG                              列出知识库中所有已知页面
  generate  -p PKG --dir PROJECT_DIR [--page PAGE_ID] [--force]  生成 Page Object + 测试骨架
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from string import Template

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(SKILL_DIR, "templates")


def _load_pages(package: str) -> list:
    """从知识库加载所有 page dict"""
    pages_dir = os.path.join(SKILL_DIR, "knowledge", "pages", package)
    if not os.path.isdir(pages_dir):
        return []
    pages = []
    for fname in sorted(os.listdir(pages_dir)):
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


def _to_class_name(page_id: str) -> str:
    """page_id → ClassName: home_game_tab → HomeGameTabPage"""
    return "".join(w.capitalize() for w in page_id.split("_")) + "Page"


def _read_template(name: str) -> str:
    path = os.path.join(TEMPLATES_DIR, name)
    with open(path, "r") as f:
        return f.read()


def list_pages(package: str) -> dict:
    """列出知识库中所有已知页面"""
    pages = _load_pages(package)
    return {
        "package": package,
        "page_count": len(pages),
        "pages": [
            {
                "id": p["id"],
                "name": p.get("name", p["id"]),
                "driver": p.get("driver", "auto"),
                "element_count": len(p.get("elements", {})),
                "route_count": len(p.get("routes", {})),
                "checkpoint_count": sum(
                    1 for e in p.get("elements", {}).values()
                    if e.get("checkpoint")
                ),
            }
            for p in pages
        ],
    }


def _gen_elements_def(elements: dict) -> str:
    """生成 Elements 类的属性定义"""
    lines = []
    for key, info in elements.items():
        locator = {k: v for k, v in info.items()
                   if k in ("text", "resource_id", "content_desc", "norm_bounds")}
        lines.append(f"        {key} = {json.dumps(locator, ensure_ascii=False)}")
    return "\n".join(lines) if lines else "        pass"


def _gen_methods(elements: dict) -> str:
    """根据元素类型生成操作方法"""
    lines = []
    for key, info in elements.items():
        elem_type = info.get("type", "")
        locator = {k: v for k, v in info.items()
                   if k in ("text", "resource_id", "content_desc", "norm_bounds")}
        locator_str = json.dumps(locator, ensure_ascii=False)

        if elem_type in ("button", "tab"):
            method_name = f"tap_{key}"
            lines.append(f"    def {method_name}(self) -> dict:")
            lines.append(f'        """点击 {info.get("text", key)}"""')
            lines.append(f"        return self.tap_element(\"{key}\", {locator_str})")
            lines.append("")

        elif elem_type == "input":
            method_name = f"input_{key}"
            lines.append(f"    def {method_name}(self, text: str) -> dict:")
            lines.append(f'        """输入到 {info.get("text", key)}"""')
            lines.append(f"        return self.input_element(\"{key}\", {locator_str}, text)")
            lines.append("")

        if info.get("checkpoint"):
            method_name = f"get_{key}"
            lines.append(f"    def {method_name}(self) -> dict:")
            lines.append(f'        """获取 {info.get("text", key)} 的文本"""')
            lines.append(f"        return self.get_element_text(\"{key}\", {locator_str})")
            lines.append("")

    return "\n".join(lines) if lines else "    pass\n"


def _gen_route_tests(page_id: str, routes: dict) -> str:
    """生成路由测试骨架"""
    lines = []
    for elem_key, target_page in routes.items():
        test_name = f"test_route_{elem_key}"
        lines.append(f"    def {test_name}(self, {page_id}_page):")
        lines.append(f'        """测试路由: {elem_key} → {target_page}"""')
        lines.append(f"        page = {page_id}_page")
        lines.append(f"        # TODO: 点击 {elem_key} 后验证是否到达 {target_page}")
        lines.append(f"        # page.tap_{elem_key}()")
        lines.append(f'        # assert page.identify_page().get("page_id") == "{target_page}"')
        lines.append(f"        pass")
        lines.append("")
    return "\n".join(lines)


def _gen_checkpoint_tests(page_id: str, elements: dict) -> str:
    """生成验证点测试骨架"""
    lines = []
    for key, info in elements.items():
        if not info.get("checkpoint"):
            continue
        test_name = f"test_checkpoint_{key}"
        lines.append(f"    def {test_name}(self, {page_id}_page):")
        lines.append(f'        """验证点: {info.get("text", key)}"""')
        lines.append(f"        page = {page_id}_page")
        lines.append(f"        # TODO: 验证 {key} 的状态/文本")
        lines.append(f"        # result = page.get_{key}()")
        lines.append(f'        # assert result.get("success"), f"{key} 不可见"')
        lines.append(f"        pass")
        lines.append("")
    return "\n".join(lines)


def _gen_fixture(page_id: str, class_name: str) -> str:
    """生成页面 fixture"""
    return (
        f"@pytest.fixture\n"
        f"def {page_id}_page(device, package):\n"
        f'    """创建 {class_name} 实例"""\n'
        f"    from pages.{page_id} import {class_name}\n"
        f"    return {class_name}(device, package)\n"
    )


def generate(package: str, project_dir: str, page_id: str = None, force: bool = False) -> dict:
    """从知识库生成 Page Object 和测试骨架"""
    project_dir = os.path.abspath(project_dir)
    pages = _load_pages(package)

    if not pages:
        return {"success": False, "error": f"知识库中没有 {package} 的页面数据"}

    if page_id:
        pages = [p for p in pages if p["id"] == page_id]
        if not pages:
            return {"success": False, "error": f"未找到页面: {page_id}"}

    generated = []
    skipped = []
    fixtures = []

    page_obj_tpl = _read_template("page_object.py.tpl")
    test_tpl = _read_template("test_skeleton.py.tpl")

    for page in pages:
        pid = page["id"]
        class_name = _to_class_name(pid)
        elements = page.get("elements", {})
        routes = page.get("routes", {})
        checkpoints = {k: v for k, v in elements.items() if v.get("checkpoint")}

        # 生成 Page Object
        po_path = os.path.join(project_dir, "pages", f"{pid}.py")
        if not os.path.exists(po_path) or force:
            content = Template(page_obj_tpl).safe_substitute(
                PAGE_NAME=page.get("name", pid),
                PAGE_ID=pid,
                CLASS_NAME=class_name,
                ELEMENTS_DEF=_gen_elements_def(elements),
                CHECKPOINTS=json.dumps(list(checkpoints.keys()), ensure_ascii=False),
                ROUTES=json.dumps(routes, ensure_ascii=False),
                METHODS=_gen_methods(elements),
            )
            with open(po_path, "w") as f:
                f.write(content)
            generated.append(f"pages/{pid}.py")
        else:
            skipped.append(f"pages/{pid}.py")

        # 生成测试骨架
        test_path = os.path.join(project_dir, "tests", f"test_{pid}.py")
        if not os.path.exists(test_path) or force:
            content = Template(test_tpl).safe_substitute(
                PAGE_NAME=page.get("name", pid),
                PAGE_ID=pid,
                CLASS_NAME=class_name,
                ROUTE_TESTS=_gen_route_tests(pid, routes),
                CHECKPOINT_TESTS=_gen_checkpoint_tests(pid, elements),
            )
            with open(test_path, "w") as f:
                f.write(content)
            generated.append(f"tests/test_{pid}.py")
        else:
            skipped.append(f"tests/test_{pid}.py")

        # 收集 fixture
        fixtures.append(_gen_fixture(pid, class_name))

    # 更新 conftest.py 中的 fixtures
    conftest_path = os.path.join(project_dir, "tests", "conftest.py")
    if os.path.exists(conftest_path):
        with open(conftest_path, "r") as f:
            conftest_content = f.read()

        # 替换 fixture 占位符或追加
        fixture_block = "\n\n".join(fixtures)
        marker = "# Page fixtures will be added by page_gen.py"
        if marker in conftest_content:
            conftest_content = conftest_content.replace(marker, fixture_block)
        else:
            # 如果已有 fixture，先移除旧的再追加
            conftest_content = conftest_content.rstrip() + "\n\n\n" + fixture_block + "\n"

        with open(conftest_path, "w") as f:
            f.write(conftest_content)
        generated.append("tests/conftest.py (fixtures updated)")

    return {
        "success": True,
        "package": package,
        "generated": generated,
        "skipped": skipped,
    }


def main():
    parser = argparse.ArgumentParser(description="Page Object 生成器")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="列出知识库中的页面")
    p_list.add_argument("--package", "-p", required=True, help="应用包名")

    p_gen = sub.add_parser("generate", help="生成 Page Object 和测试骨架")
    p_gen.add_argument("--package", "-p", required=True, help="应用包名")
    p_gen.add_argument("--dir", required=True, help="项目目录")
    p_gen.add_argument("--page", help="指定页面 ID（不指定则生成全部）")
    p_gen.add_argument("--force", action="store_true", help="强制覆盖已有文件")

    args = parser.parse_args()

    if args.cmd == "list":
        result = list_pages(args.package)
    elif args.cmd == "generate":
        result = generate(args.package, args.dir, args.page, args.force)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
