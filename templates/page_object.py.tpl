"""
Page Object: ${PAGE_NAME}
页面 ID: ${PAGE_ID}
自动生成 by droid-pilot page_gen
"""
from pages.base_page import BasePage


class ${CLASS_NAME}(BasePage):
    """${PAGE_NAME}"""

    PAGE_ID = "${PAGE_ID}"

    class Elements:
        """元素定位信息"""
${ELEMENTS_DEF}

    # 验证点
    CHECKPOINTS = ${CHECKPOINTS}

    # 路由（导航到其他页面）
    ROUTES = ${ROUTES}

    # ---- 元素操作方法 ----
${METHODS}

    def verify_on_page(self) -> bool:
        """验证当前是否在本页面"""
        result = self.identify_page()
        return result.get("matched_page") == self.PAGE_ID or result.get("status") == "matched"
