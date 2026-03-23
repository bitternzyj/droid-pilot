"""
测试: ${PAGE_NAME}
页面 ID: ${PAGE_ID}
自动生成 by droid-pilot page_gen
"""
import pytest


class Test${CLASS_NAME}:
    """${PAGE_NAME} 测试"""

    def test_page_loads(self, ${PAGE_ID}_page):
        """验证页面能正确加载和识别"""
        page = ${PAGE_ID}_page
        assert page.verify_on_page(), f"未能识别到页面: {page.PAGE_ID}"

${ROUTE_TESTS}
${CHECKPOINT_TESTS}
