from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Element:
    text: str = ""
    resource_id: str = ""
    content_desc: str = ""
    type: str = "view"
    bounds: list = field(default_factory=list)       # [x1,y1,x2,y2] 绝对坐标
    norm_bounds: list = field(default_factory=list)  # [0~1] 归一坐标（视觉驱动用）
    clickable: bool = False
    checkable: bool = False
    checked: bool = False
    selected: bool = False
    source: str = ""  # "u2" | "poco" | "vision"

    def identity(self) -> str:
        """主要标识，用于指纹计算"""
        return self.text or self.resource_id or self.content_desc

    def center(self) -> tuple:
        """返回元素中心坐标"""
        if len(self.bounds) == 4:
            return (
                (self.bounds[0] + self.bounds[2]) // 2,
                (self.bounds[1] + self.bounds[3]) // 2,
            )
        return (0, 0)


class BaseDriver(ABC):
    """所有驱动的统一接口。调用方只依赖此接口，不感知底层实现。"""

    @abstractmethod
    def dump(self) -> list:
        """获取当前页面元素列表，返回 list[Element]"""

    @abstractmethod
    def screenshot(self) -> bytes:
        """截图，返回 PNG bytes"""

    @abstractmethod
    def tap(self, locator: dict) -> bool:
        """
        点击元素。locator 格式:
          {"text": "xxx"}
          {"resource_id": "xxx"}
          {"norm_bounds": [x1,y1,x2,y2]}   # 视觉驱动用
          {"prefer": [{"text": "xxx"}, {"resource_id": "yyy"}]}  # 按顺序尝试
        """

    @abstractmethod
    def swipe(self, start: tuple, end: tuple, duration: float = 0.3) -> bool:
        """
        滑动。start/end 为归一化坐标 (0~1, 0~1) 或绝对坐标，
        由 normalized 参数区分。
        """

    @abstractmethod
    def input_text(self, locator: dict, text: str) -> bool:
        """聚焦元素并输入文字"""

    @abstractmethod
    def current_activity(self) -> str:
        """返回当前 Activity 短名（不含包名）"""

    @abstractmethod
    def driver_type(self) -> str:
        """返回 'u2' | 'poco' | 'vision'"""

    # ------------------------------------------------------------------
    # 非抽象：子类可选覆盖
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """检查驱动是否可用（连接正常、库已安装等）"""
        return True

    def back(self) -> bool:
        """按返回键"""
        return False

    def home(self) -> bool:
        """按 Home 键"""
        return False
