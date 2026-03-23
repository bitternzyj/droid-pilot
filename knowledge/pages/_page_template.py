# 页面知识库模板
# 复制此文件到 knowledge/pages/{package}/{page_id}.py 并填写

page = {
    # ---- 基本信息 ----
    "id": "page_id",           # 唯一标识，小写下划线
    "name": "页面名称",         # 人类可读名称
    "driver": "auto",          # "u2" | "poco" | "vision" | "auto"

    # ---- 页面识别条件（用于 page_matcher）----
    "identify": {
        "activity": "ActivityName",    # Activity 短名，不含包名；不确定可留空
        "must_have": [
            # 必须存在的元素，全部满足才算匹配
            # {"text": "某文字"},
            # {"resource_id": "某id"},
            # {"text": "某文字", "selected": True},
        ],
        # 视觉模式专用
        # "phash": "",                   # 参考截图感知哈希
        # "must_have_visual": [],        # 截图中必须出现的文字
    },

    # ---- 元素定义 ----
    # key: 元素语义名（供操作时引用）
    # value: 定位方式 + 元数据
    "elements": {
        # 示例（u2/poco 模式）：
        # "btn_confirm": {
        #     "text": "确认",
        #     "type": "button",
        #     "checkpoint": False,    # True 表示这是验证点，测试时需断言
        # },
        # "tab_home": {
        #     "text": "首页",
        #     "type": "tab",
        # },
        # "input_search": {
        #     "resource_id": "et_search",
        #     "type": "input",
        # },

        # 示例（vision 模式，使用归一坐标）：
        # "btn_pause": {
        #     "desc": "暂停按钮（右上角）",
        #     "type": "button",
        #     "norm_bounds": [0.85, 0.02, 0.98, 0.10],
        #     "checkpoint": True,
        # },
    },

    # ---- 弹框/覆盖层（不建新 page 节点，挂在当前页）----
    "overlays": {
        # "dialog_update": {
        #     "contains": ["更新", "立即更新"],
        #     "auto_dismiss": "取消",    # 自动点击哪个按钮关闭
        # },
    },

    # ---- 页面跳转关系（用于拓扑图）----
    # key: 触发跳转的元素 key（对应 elements 中的 key）
    # value: 跳转后的 page_id
    "routes": {
        # "btn_settings": "settings_main",
        # "tab_profile":  "profile_main",
    },

    # ---- 视觉模式：参考截图路径（相对于当前 package 目录）----
    # "screenshot": "screenshots/page_id.png",
}
