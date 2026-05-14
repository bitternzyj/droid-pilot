from __future__ import annotations

import base64
import json
import os
import re
import subprocess

import requests

from .base import BaseDriver, Element

# Ollama 服务地址，可通过环境变量覆盖
OLLAMA_URL = os.environ.get("DROID_PILOT_OLLAMA_URL", "http://localhost:11434")

# 推荐模型：gelab-zero-4b
# 经调研对比（Qwen2-VL, CogAgent, SeeClick, gelab-zero 等），
# gelab-zero-4b 在移动端 UI 元素定位场景的准确率和推理速度综合最优：
#   - 4B 参数量，单卡 8G 显存可运行
#   - 支持 0-1000 归一化坐标输出，天然适配移动端
#   - 中文 UI 文本识别能力强
MODEL = os.environ.get("DROID_PILOT_VISION_MODEL", "gelab-zero-4b")


class VisionDriver(BaseDriver):
    """
    纯视觉驱动：截图 → 本地视觉模型分析 → adb 执行。

    适用于 u2/poco 均无法 dump 的场景（游戏自绘 UI、WebView、深度自定义控件）。

    依赖：
    - Ollama 服务运行中，已拉取视觉模型
    - 设备通过 adb 连接

    配置（环境变量）：
    - DROID_PILOT_OLLAMA_URL: Ollama 地址，默认 http://localhost:11434
    - DROID_PILOT_VISION_MODEL: 模型名，默认 gelab-zero-4b
    """

    def __init__(self, device_id: str = None):
        self._device_id = device_id
        self._timeout = 60

    def driver_type(self) -> str:
        return "vision"

    def is_available(self) -> bool:
        try:
            cmd = self._adb_prefix() + ['shell', 'echo', 'ok']
            out = subprocess.check_output(cmd, timeout=5, text=True)
            return 'ok' in out
        except Exception:
            return False

    # ------------------------------------------------------------------
    # 视觉模型调用
    # ------------------------------------------------------------------

    def _chat(self, prompt: str, img_base64: str) -> str:
        resp = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": MODEL,
                "messages": [{
                    "role": "user",
                    "content": prompt,
                    "images": [img_base64]
                }],
                "stream": False
            },
            timeout=self._timeout
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"]

    def _screenshot_base64(self) -> str:
        png_bytes = self.screenshot()
        return base64.b64encode(png_bytes).decode()

    def _parse_point(self, content: str):
        """解析模型返回的坐标点，返回 (x, y) 归一化坐标 0-1000"""
        try:
            match = re.search(r'\{.*?\}', content, re.DOTALL)
            if match:
                data = json.loads(match.group())
                point = data.get("point")
                if point and len(point) == 2:
                    return int(point[0]), int(point[1])
        except (json.JSONDecodeError, ValueError):
            pass
        return None

    # ------------------------------------------------------------------
    # 核心接口
    # ------------------------------------------------------------------

    def dump(self) -> list:
        """
        视觉 dump：截图后让模型描述页面上的可交互元素。
        返回 Element 列表（含归一坐标）。
        """
        img_b64 = self._screenshot_base64()
        prompt = (
            "列出屏幕上所有可交互的 UI 元素（按钮、输入框、标签页、图标等），"
            "每个元素用 JSON 表示：{\"text\": \"元素文本\", \"type\": \"button|input|tab|icon|text\", "
            "\"point\": [x, y]}，坐标范围 0-1000。"
            "返回一个 JSON 数组，不要其他内容。"
        )
        response = self._chat(prompt, img_b64)

        elements = []
        try:
            match = re.search(r'\[.*\]', response, re.DOTALL)
            if match:
                items = json.loads(match.group())
                w, h = self._screen_size()
                for item in items:
                    point = item.get("point", [500, 500])
                    nx, ny = point[0] / 1000.0, point[1] / 1000.0
                    cx, cy = int(nx * w), int(ny * h)
                    size = 20
                    elements.append(Element(
                        text=item.get("text", ""),
                        type=item.get("type", "view"),
                        bounds=[cx - size, cy - size, cx + size, cy + size],
                        norm_bounds=[nx - 0.02, ny - 0.02, nx + 0.02, ny + 0.02],
                        clickable=True,
                        source="vision"
                    ))
        except (json.JSONDecodeError, ValueError):
            pass

        return elements

    def screenshot(self) -> bytes:
        cmd = self._adb_prefix() + ['exec-out', 'screencap', '-p']
        return subprocess.check_output(cmd)

    def tap(self, locator: dict) -> bool:
        """
        视觉 tap：
        - norm_bounds → 直接计算绝对坐标点击
        - text → 截图让模型定位后点击
        """
        norm_bounds = locator.get('norm_bounds')
        if norm_bounds:
            w, h = self._screen_size()
            x = int((norm_bounds[0] + norm_bounds[2]) / 2 * w)
            y = int((norm_bounds[1] + norm_bounds[3]) / 2 * h)
            return self._adb_tap(x, y)

        text = locator.get('text') or locator.get('content_desc')
        if text:
            return self._locate_and_tap(text)

        return False

    def swipe(self, start: tuple, end: tuple, duration: float = 0.3) -> bool:
        w, h = self._screen_size()
        x1, y1 = int(start[0] * w), int(start[1] * h)
        x2, y2 = int(end[0] * w), int(end[1] * h)
        ms = int(duration * 1000)
        return self._adb_swipe(x1, y1, x2, y2, ms)

    def input_text(self, locator: dict, text: str) -> bool:
        if not self.tap(locator):
            return False
        import time
        time.sleep(0.3)
        safe = text.replace(' ', '%s')
        cmd = self._adb_prefix() + ['shell', 'input', 'text', safe]
        try:
            subprocess.run(cmd, timeout=10, check=True)
            return True
        except Exception:
            return False

    def current_activity(self) -> str:
        cmd = self._adb_prefix() + ['shell', 'dumpsys', 'activity', 'activities']
        try:
            out = subprocess.check_output(cmd, text=True, timeout=5)
            for line in out.splitlines():
                if 'mResumedActivity' in line:
                    parts = line.strip().split('/')
                    if len(parts) >= 2:
                        return parts[-1].rstrip('}').split('.')[-1]
        except Exception:
            pass
        return ""

    def back(self) -> bool:
        return self._adb_key('BACK')

    def home(self) -> bool:
        return self._adb_key('HOME')

    # ------------------------------------------------------------------
    # 扩展能力（利用视觉模型）
    # ------------------------------------------------------------------

    def locate(self, element: str) -> tuple | None:
        """
        定位元素，返回绝对像素坐标 (x, y)，失败返回 None。
        """
        img_b64 = self._screenshot_base64()
        prompt = f'定位"{element}"，返回 {{"action_type": "CLICK", "point": [x, y]}}，坐标范围 0-1000'
        response = self._chat(prompt, img_b64)
        point = self._parse_point(response)
        if point:
            w, h = self._screen_size()
            return int(point[0] / 1000 * w), int(point[1] / 1000 * h)
        return None

    def describe(self) -> str:
        """描述当前屏幕内容"""
        img_b64 = self._screenshot_base64()
        return self._chat("简要描述当前屏幕的主要内容，包括页面类型和主要元素。", img_b64)

    def check_exists(self, element: str) -> bool:
        """检查元素是否存在"""
        img_b64 = self._screenshot_base64()
        prompt = f'屏幕上是否存在"{element}"？只回答 yes 或 no。'
        response = self._chat(prompt, img_b64)
        answer = response.strip().lower()
        return "yes" in answer or "是" in answer or "存在" in answer

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _locate_and_tap(self, text: str) -> bool:
        """通过视觉模型定位文本元素并点击"""
        coords = self.locate(text)
        if coords:
            return self._adb_tap(coords[0], coords[1])
        return False

    def _adb_prefix(self) -> list:
        cmd = ['adb']
        if self._device_id:
            cmd += ['-s', self._device_id]
        return cmd

    def _adb_tap(self, x: int, y: int) -> bool:
        return self._run_adb(['shell', 'input', 'tap', str(x), str(y)])

    def _adb_swipe(self, x1, y1, x2, y2, ms) -> bool:
        return self._run_adb(['shell', 'input', 'swipe',
                              str(x1), str(y1), str(x2), str(y2), str(ms)])

    def _adb_key(self, key: str) -> bool:
        return self._run_adb(['shell', 'input', 'keyevent', key])

    def _run_adb(self, args: list) -> bool:
        cmd = self._adb_prefix() + args
        try:
            subprocess.run(cmd, timeout=10, check=True, capture_output=True)
            return True
        except Exception:
            return False

    def _screen_size(self) -> tuple:
        cmd = self._adb_prefix() + ['shell', 'wm', 'size']
        try:
            out = subprocess.check_output(cmd, text=True, timeout=5)
            size = out.strip().split()[-1]
            w, h = size.split('x')
            return int(w), int(h)
        except Exception:
            return 1080, 1920
