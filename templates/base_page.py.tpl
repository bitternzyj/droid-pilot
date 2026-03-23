"""
BasePage —— 所有 Page Object 的基类。
通过 subprocess 调用 droid-pilot 脚本，保持与 core 模块解耦。
"""
import json
import os
import subprocess
import time


SKILL_DIR = os.environ.get("DROID_PILOT_SKILL_DIR", "")


def _run_script(script: str, args: list) -> dict:
    """调用 droid-pilot 脚本并返回 JSON 结果"""
    cmd = ["python", os.path.join(SKILL_DIR, "scripts", script)] + args
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        return {"success": False, "error": result.stderr.strip()}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"success": False, "error": f"Invalid JSON: {result.stdout[:200]}"}


class BasePage:
    """Page Object 基类，封装 droid-pilot 脚本调用"""

    PAGE_ID = ""
    DEVICE = ""
    PACKAGE = ""

    def __init__(self, device: str, package: str):
        self.DEVICE = device
        self.PACKAGE = package

    def _device_args(self) -> list:
        args = []
        if self.DEVICE:
            args += ["-d", self.DEVICE]
        return args

    # ---- 元素操作 ----

    def tap_element(self, key: str, locator: dict) -> dict:
        """点击元素"""
        target = json.dumps(locator, ensure_ascii=False)
        return _run_script("execute_action.py",
                           self._device_args() + ["-a", "click", "-t", target])

    def input_element(self, key: str, locator: dict, text: str) -> dict:
        """输入文本"""
        target = json.dumps(locator, ensure_ascii=False)
        return _run_script("execute_action.py",
                           self._device_args() + ["-a", "input", "-t", target, "-v", text])

    def get_element_text(self, key: str, locator: dict) -> dict:
        """获取元素文本（通过 screen_context 查找）"""
        ctx = _run_script("screen_context.py", self._device_args() + ["-f", "json"])
        if "error" in ctx:
            return ctx
        for elem in ctx.get("elements", []):
            for k in ("text", "resource_id", "content_desc"):
                if k in locator and locator[k] == elem.get(k):
                    return {"success": True, "text": elem.get("text", ""), "element": elem}
        return {"success": False, "error": f"Element '{key}' not found"}

    # ---- 页面操作 ----

    def identify_page(self) -> dict:
        """识别当前页面"""
        args = self._device_args() + ["-f", "json"]
        if self.PACKAGE:
            args += ["-p", self.PACKAGE]
        return _run_script("page_identify.py", args)

    def screenshot(self, path: str) -> bool:
        """截图保存到指定路径"""
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        cmd = ["adb"]
        if self.DEVICE:
            cmd += ["-s", self.DEVICE]
        cmd += ["exec-out", "screencap", "-p"]
        result = subprocess.run(cmd, capture_output=True, timeout=10)
        if result.returncode == 0:
            with open(path, "wb") as f:
                f.write(result.stdout)
            return True
        return False

    def dump_context(self) -> dict:
        """dump 当前页面上下文"""
        return _run_script("screen_context.py", self._device_args() + ["-f", "json"])

    # ---- 导航操作 ----

    def go_back(self) -> dict:
        """按返回键"""
        return _run_script("execute_action.py",
                           self._device_args() + ["-a", "back"])

    def swipe(self, from_pos: list, to_pos: list) -> dict:
        """滑动操作"""
        target = json.dumps({"from": from_pos, "to": to_pos})
        return _run_script("execute_action.py",
                           self._device_args() + ["-a", "swipe", "-t", target])

    def wait(self, seconds: float = 1) -> dict:
        """等待"""
        return _run_script("execute_action.py",
                           self._device_args() + ["-a", "wait", "-v", str(seconds)])

    # ---- 页面验证 ----

    def verify_on_page(self) -> bool:
        """验证当前是否在本页面（子类可覆盖）"""
        result = self.identify_page()
        return result.get("matched_page") == self.PAGE_ID or result.get("status") == "matched"
