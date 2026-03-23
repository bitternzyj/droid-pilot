from __future__ import annotations

from .base import BaseDriver, Element
from .u2_driver import U2Driver, MEANINGFUL_NODE_THRESHOLD
from .vision_driver import VisionDriver

# poco 可选，未安装时不报错
try:
    from .poco_driver import PocoDriver
    _POCO_AVAILABLE = True
except ImportError:
    _POCO_AVAILABLE = False


class AutoDriver(BaseDriver):
    """
    自动路由驱动：根据页面知识库 hint 或运行时探测，选择合适的底层驱动。
    上层调用方只依赖此类，不感知 u2 / poco / vision 差异。

    驱动选择优先级（无 hint 时）:
      1. u2 dump 节点数 >= 阈值 → U2Driver
      2. poco 可用           → PocoDriver
      3. 兜底                → VisionDriver
    """

    def __init__(self, device_id: str = None):
        self._device_id = device_id

        # 驱动实例常驻，不要每次操作新建
        self._u2 = U2Driver(device_id)
        self._poco = PocoDriver(device_id) if _POCO_AVAILABLE else None
        self._vision = VisionDriver(device_id)

        # page_id → driver_type 缓存，避免每次探测
        self._page_driver_cache: dict[str, str] = {}

        # 当前会话使用的驱动（上次探测结果）
        self._current_driver: BaseDriver = self._u2

    def driver_type(self) -> str:
        return f"auto({self._current_driver.driver_type()})"

    # ------------------------------------------------------------------
    # 核心接口（透传给当前驱动）
    # ------------------------------------------------------------------

    def dump(self) -> list:
        driver = self._resolve_driver()
        return driver.dump()

    def screenshot(self) -> bytes:
        # 截图总是走 u2 或 vision（adb），不走 poco
        if self._u2.is_available():
            return self._u2.screenshot()
        return self._vision.screenshot()

    def tap(self, locator: dict) -> bool:
        return self._current_driver.tap(locator)

    def swipe(self, start: tuple, end: tuple, duration: float = 0.3) -> bool:
        return self._current_driver.swipe(start, end, duration)

    def input_text(self, locator: dict, text: str) -> bool:
        return self._current_driver.input_text(locator, text)

    def current_activity(self) -> str:
        # activity 优先 u2，fallback adb（vision）
        try:
            return self._u2.current_activity()
        except Exception:
            return self._vision.current_activity()

    def back(self) -> bool:
        return self._current_driver.back()

    def home(self) -> bool:
        return self._current_driver.home()

    # ------------------------------------------------------------------
    # 驱动路由
    # ------------------------------------------------------------------

    def set_page_driver(self, page_id: str, driver_type: str):
        """从页面知识库载入 driver hint，供后续操作使用"""
        self._page_driver_cache[page_id] = driver_type

    def use_driver_for_page(self, page_id: str):
        """切换到指定页面的驱动（已知页面时调用）"""
        hint = self._page_driver_cache.get(page_id)
        if hint:
            self._current_driver = self._get_driver_by_type(hint)
        else:
            self._resolve_driver()  # 自动探测

    def _resolve_driver(self) -> BaseDriver:
        """运行时自动探测：dump 节点数决定用哪个驱动"""
        try:
            elements = self._u2.dump()
            if len(elements) >= MEANINGFUL_NODE_THRESHOLD:
                self._current_driver = self._u2
                return self._u2
        except Exception:
            pass

        if self._poco and self._poco.is_available():
            self._current_driver = self._poco
            return self._poco

        self._current_driver = self._vision
        return self._vision

    def _get_driver_by_type(self, driver_type: str) -> BaseDriver:
        if driver_type == "u2":
            return self._u2
        if driver_type == "poco" and self._poco:
            return self._poco
        return self._vision
