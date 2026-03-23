from __future__ import annotations

import time

from .base import BaseDriver, Element

IDLE_TIMEOUT = 300      # 5 分钟无操作后主动断开
MAX_RECONNECT = 1       # 最多重连 1 次，不循环


class PocoDriver(BaseDriver):
    """
    基于 poco 的驱动，适用于游戏引擎自绘 UI（Unity / Cocos）。

    关键设计：实例长生命周期，不要频繁 connect/disconnect。
    poco server 频繁重连会导致卡死，所以：
      - _poco 实例复用，只在真正报错时重建（最多 1 次）
      - 超过 IDLE_TIMEOUT 无操作时主动断开（比被动断更干净）
    """

    def __init__(self, device_id: str = None, poco_type: str = "unity3d"):
        self._device_id = device_id
        self._poco_type = poco_type  # "unity3d" | "cocos2dx" | "android"
        self._poco = None
        self._last_active = 0.0
        self._reconnect_count = 0

    # ------------------------------------------------------------------
    # 连接管理
    # ------------------------------------------------------------------

    def _ensure_connected(self):
        # 超过 idle 阈值，主动断开后重建（主动断比被动断干净）
        if self._poco is not None:
            if time.time() - self._last_active > IDLE_TIMEOUT:
                self._disconnect()

        if self._poco is None:
            self._connect()

    def _connect(self):
        try:
            self._poco = self._do_connect()
            self._last_active = time.time()
            self._reconnect_count = 0
        except Exception as e:
            self._poco = None
            raise RuntimeError(f"poco 连接失败: {e}") from e

    def _disconnect(self):
        try:
            if self._poco is not None:
                # poco 没有显式 disconnect，置 None 让 GC 处理
                self._poco = None
        except Exception:
            pass
        finally:
            self._poco = None

    def _do_connect(self):
        """实际建立 poco 连接，子类可覆盖以支持不同 poco 类型"""
        if self._poco_type == "unity3d":
            from poco.drivers.unity3d import UnityPoco
            return UnityPoco()
        elif self._poco_type == "android":
            from poco.drivers.android.uiautomation import AndroidUiautomationPoco
            return AndroidUiautomationPoco()
        else:
            raise ValueError(f"不支持的 poco_type: {self._poco_type}")

    def _call_with_retry(self, fn):
        """执行 fn，失败时重连一次再试，超过限制则抛出"""
        try:
            self._ensure_connected()
            result = fn()
            self._last_active = time.time()
            return result
        except Exception as e:
            if self._reconnect_count < MAX_RECONNECT:
                self._reconnect_count += 1
                self._disconnect()
                self._connect()
                result = fn()
                self._last_active = time.time()
                return result
            # 超过重连次数，标记断开并向上抛
            self._disconnect()
            raise RuntimeError(f"poco 操作失败（重连后仍失败）: {e}") from e

    def is_available(self) -> bool:
        try:
            self._ensure_connected()
            # 做一个轻量探活（dump 根节点）
            self._call_with_retry(lambda: self._poco.agent.hierarchy.dump())
            return True
        except Exception:
            return False

    def driver_type(self) -> str:
        return "poco"

    # ------------------------------------------------------------------
    # 核心接口
    # ------------------------------------------------------------------

    def dump(self) -> list:
        def _do():
            # poco dump 返回树状结构，这里打平为 Element 列表
            nodes = self._poco.agent.hierarchy.dump()
            return self._flatten(nodes)

        return self._call_with_retry(_do)

    def screenshot(self) -> bytes:
        # poco 本身不截图，借用 adb
        import subprocess
        cmd = ['adb']
        if self._device_id:
            cmd += ['-s', self._device_id]
        cmd += ['exec-out', 'screencap', '-p']
        return subprocess.check_output(cmd)

    def tap(self, locator: dict) -> bool:
        def _do():
            node = self._find_node(locator)
            if node is None:
                return False
            node.click()
            return True

        return self._call_with_retry(_do)

    def swipe(self, start: tuple, end: tuple, duration: float = 0.3) -> bool:
        def _do():
            self._poco.swipe(start, end, duration=duration)
            return True

        return self._call_with_retry(_do)

    def input_text(self, locator: dict, text: str) -> bool:
        def _do():
            node = self._find_node(locator)
            if node is None:
                return False
            node.set_text(text)
            return True

        return self._call_with_retry(_do)

    def current_activity(self) -> str:
        # poco 不直接提供 activity，走 adb
        import subprocess
        cmd = ['adb']
        if self._device_id:
            cmd += ['-s', self._device_id]
        cmd += ['shell', 'dumpsys', 'activity', 'activities']
        try:
            out = subprocess.check_output(cmd, text=True, timeout=5)
            for line in out.splitlines():
                if 'mResumedActivity' in line or 'mCurrentFocus' in line:
                    parts = line.strip().split('/')
                    if len(parts) >= 2:
                        return parts[-1].rstrip('}').split('.')[-1]
        except Exception:
            pass
        return ""

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _flatten(self, node, result=None) -> list:
        """递归打平 poco 节点树为 Element 列表"""
        if result is None:
            result = []
        if node is None:
            return result

        try:
            name = node.get_name() or ""
            pos = node.get_position()       # [x, y] 归一化 0~1
            size = node.get_size()          # [w, h] 归一化
            clickable = node.attr('clickable') or False

            if name or clickable:
                x1 = pos[0] - size[0] / 2
                y1 = pos[1] - size[1] / 2
                x2 = pos[0] + size[0] / 2
                y2 = pos[1] + size[1] / 2
                result.append(Element(
                    text=name,
                    type='button' if clickable else 'view',
                    norm_bounds=[x1, y1, x2, y2],
                    clickable=clickable,
                    source="poco",
                ))

            for child in node.children():
                self._flatten(child, result)
        except Exception:
            pass

        return result

    def _find_node(self, locator: dict):
        text = locator.get('text')
        if text:
            node = self._poco(text=text)
            return node if node.exists() else None
        return None
