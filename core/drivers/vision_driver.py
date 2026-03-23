from __future__ import annotations

import subprocess

from .base import BaseDriver, Element


class VisionDriver(BaseDriver):
    """
    纯视觉驱动：截图 → AI 分析元素 → adb tap 执行。
    适用于 u2/poco 均无法 dump 的场景（深度自绘 UI）。

    当前状态：截图 + adb 执行已实现；AI 分析部分占位，待接入视觉模型。
    """

    def __init__(self, device_id: str = None):
        self._device_id = device_id

    def driver_type(self) -> str:
        return "vision"

    def is_available(self) -> bool:
        # 视觉驱动只要设备可连就可用（截图用 adb）
        try:
            cmd = ['adb']
            if self._device_id:
                cmd += ['-s', self._device_id]
            cmd += ['shell', 'echo', 'ok']
            out = subprocess.check_output(cmd, timeout=5, text=True)
            return 'ok' in out
        except Exception:
            return False

    # ------------------------------------------------------------------
    # 核心接口
    # ------------------------------------------------------------------

    def dump(self) -> list:
        """
        视觉 dump：截图后交给 AI 分析。
        TODO: 接入视觉模型，返回 Element 列表（含归一坐标）。
        现在返回空列表，由 AutoDriver 决策是否继续。
        """
        # _screenshot_bytes = self.screenshot()
        # elements = ai_analyze(_screenshot_bytes)
        # return elements
        return []

    def screenshot(self) -> bytes:
        cmd = ['adb']
        if self._device_id:
            cmd += ['-s', self._device_id]
        cmd += ['exec-out', 'screencap', '-p']
        return subprocess.check_output(cmd)

    def tap(self, locator: dict) -> bool:
        """
        视觉 tap：优先用 norm_bounds 计算绝对坐标；
        也可接受 {'text': 'xxx'} 并让 AI 在截图中定位。
        """
        norm_bounds = locator.get('norm_bounds')
        if norm_bounds:
            w, h = self._screen_size()
            x = int((norm_bounds[0] + norm_bounds[2]) / 2 * w)
            y = int((norm_bounds[1] + norm_bounds[3]) / 2 * h)
            return self._adb_tap(x, y)

        # TODO: text 定位走 AI 视觉识别
        return False

    def swipe(self, start: tuple, end: tuple, duration: float = 0.3) -> bool:
        w, h = self._screen_size()
        x1, y1 = int(start[0] * w), int(start[1] * h)
        x2, y2 = int(end[0] * w), int(end[1] * h)
        ms = int(duration * 1000)
        return self._adb_swipe(x1, y1, x2, y2, ms)

    def input_text(self, locator: dict, text: str) -> bool:
        # 先 tap 聚焦
        if not self.tap(locator):
            return False
        import time
        time.sleep(0.3)
        # adb input text 不支持中文，这里只处理 ASCII
        safe = text.replace(' ', '%s')
        cmd = ['adb']
        if self._device_id:
            cmd += ['-s', self._device_id]
        cmd += ['shell', 'input', 'text', safe]
        try:
            subprocess.run(cmd, timeout=10, check=True)
            return True
        except Exception:
            return False

    def current_activity(self) -> str:
        cmd = ['adb']
        if self._device_id:
            cmd += ['-s', self._device_id]
        cmd += ['shell', 'dumpsys', 'activity', 'activities']
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
    # 内部
    # ------------------------------------------------------------------

    def _adb(self, args: list) -> bool:
        cmd = ['adb']
        if self._device_id:
            cmd += ['-s', self._device_id]
        cmd += args
        try:
            subprocess.run(cmd, timeout=10, check=True, capture_output=True)
            return True
        except Exception:
            return False

    def _adb_tap(self, x: int, y: int) -> bool:
        return self._adb(['shell', 'input', 'tap', str(x), str(y)])

    def _adb_swipe(self, x1, y1, x2, y2, ms) -> bool:
        return self._adb(['shell', 'input', 'swipe',
                          str(x1), str(y1), str(x2), str(y2), str(ms)])

    def _adb_key(self, key: str) -> bool:
        return self._adb(['shell', 'input', 'keyevent', key])

    def _screen_size(self) -> tuple:
        cmd = ['adb']
        if self._device_id:
            cmd += ['-s', self._device_id]
        cmd += ['shell', 'wm', 'size']
        try:
            out = subprocess.check_output(cmd, text=True, timeout=5)
            size = out.strip().split()[-1]
            w, h = size.split('x')
            return int(w), int(h)
        except Exception:
            return 1080, 1920
