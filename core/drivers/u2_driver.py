from __future__ import annotations

import re
import time

from .base import BaseDriver, Element

DUMP_TIMEOUT = 10
MEANINGFUL_NODE_THRESHOLD = 8  # dump 节点数低于此值认为是自绘 UI


def _parse_bounds(bounds_str: str) -> list:
    match = re.findall(r'\[(\d+),(\d+)\]', bounds_str)
    if len(match) == 2:
        return [int(match[0][0]), int(match[0][1]), int(match[1][0]), int(match[1][1])]
    return []


def _infer_type(cls: str, checkable: bool) -> str:
    if 'Button' in cls:
        return 'button'
    if 'CheckBox' in cls or checkable:
        return 'checkbox'
    if 'EditText' in cls:
        return 'input'
    if 'TextView' in cls:
        return 'text'
    if 'ImageView' in cls:
        return 'image'
    if 'RecyclerView' in cls or 'ListView' in cls:
        return 'list'
    if 'ScrollView' in cls:
        return 'scroll'
    return 'view'


class U2Driver(BaseDriver):
    """基于 uiautomator2 的驱动。实例长生命周期，不要每次操作新建。"""

    def __init__(self, device_id: str = None):
        self._device_id = device_id
        self._d = None

    # ------------------------------------------------------------------
    # 连接管理
    # ------------------------------------------------------------------

    def _ensure_connected(self):
        if self._d is not None:
            return
        try:
            import uiautomator2 as u2
            self._d = u2.connect(self._device_id) if self._device_id else u2.connect()
        except Exception as e:
            raise RuntimeError(f"u2 连接失败: {e}") from e

    def is_available(self) -> bool:
        try:
            self._ensure_connected()
            self._d.info  # 简单探活
            return True
        except Exception:
            self._d = None
            return False

    def driver_type(self) -> str:
        return "u2"

    # ------------------------------------------------------------------
    # 核心接口
    # ------------------------------------------------------------------

    def dump(self) -> list:
        import xml.etree.ElementTree as ET

        self._ensure_connected()
        current_app = self._d.app_current()
        package = current_app.get('package', '')

        xml = self._d.dump_hierarchy(timeout=DUMP_TIMEOUT)
        root = ET.fromstring(xml)

        screen_w = self._d.info.get('displayWidth', 1080)
        screen_h = self._d.info.get('displayHeight', 1920)

        elements = []
        for node in root.iter('node'):
            pkg = node.get('package', '')
            if package and pkg and pkg != package:
                continue

            text = (node.get('text') or '').strip()
            content_desc = (node.get('content-desc') or '').strip()
            resource_id = node.get('resource-id') or ''
            clickable = node.get('clickable') == 'true'
            checkable = node.get('checkable') == 'true'
            checked = node.get('checked') == 'true'
            selected = node.get('selected') == 'true'
            bounds_str = node.get('bounds') or ''
            cls = node.get('class') or ''

            has_identity = bool(text or content_desc or resource_id)
            if not (has_identity or clickable or checkable):
                continue

            bounds = _parse_bounds(bounds_str)
            norm_bounds = []
            if bounds and screen_w and screen_h:
                norm_bounds = [
                    bounds[0] / screen_w, bounds[1] / screen_h,
                    bounds[2] / screen_w, bounds[3] / screen_h,
                ]

            elem = Element(
                text=text,
                resource_id=resource_id.split('/')[-1] if '/' in resource_id else resource_id,
                content_desc=content_desc,
                type=_infer_type(cls, checkable),
                bounds=bounds,
                norm_bounds=norm_bounds,
                clickable=clickable,
                checkable=checkable,
                checked=checked,
                selected=selected,
                source="u2",
            )
            elements.append(elem)

        return elements

    def screenshot(self) -> bytes:
        self._ensure_connected()
        return self._d.screenshot(format='png')

    def tap(self, locator: dict) -> bool:
        self._ensure_connected()
        elem = self._resolve_element(locator)
        if elem is None:
            return False
        x, y = elem.center()
        if x == 0 and y == 0:
            return False
        self._d.click(x, y)
        return True

    def swipe(self, start: tuple, end: tuple, duration: float = 0.3) -> bool:
        self._ensure_connected()
        self._d.swipe(start[0], start[1], end[0], end[1], duration=duration)
        return True

    def input_text(self, locator: dict, text: str) -> bool:
        self._ensure_connected()
        elem = self._resolve_element(locator)
        if elem is None:
            return False
        x, y = elem.center()
        self._d.click(x, y)
        time.sleep(0.3)
        self._d.send_keys(text)
        return True

    def current_activity(self) -> str:
        self._ensure_connected()
        info = self._d.app_current()
        activity = info.get('activity', '')
        return activity.split('.')[-1] if '.' in activity else activity

    def back(self) -> bool:
        self._ensure_connected()
        self._d.press('back')
        return True

    def home(self) -> bool:
        self._ensure_connected()
        self._d.press('home')
        return True

    # ------------------------------------------------------------------
    # 内部：元素定位
    # ------------------------------------------------------------------

    def _resolve_element(self, locator: dict) -> Element | None:
        """从 locator 找到匹配的 Element（通过 dump + 过滤）"""
        prefer = locator.get('prefer')
        if prefer:
            for loc in prefer:
                elem = self._find_one(loc)
                if elem:
                    return elem
            return None
        return self._find_one(locator)

    def _find_one(self, locator: dict) -> Element | None:
        elements = self.dump()
        text = locator.get('text')
        resource_id = locator.get('resource_id')
        for elem in elements:
            if text and elem.text == text:
                return elem
            if resource_id and elem.resource_id == resource_id:
                return elem
        return None
