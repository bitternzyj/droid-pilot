# Droid Pilot

Android UI 自动化 Agent，基于 Claude Code Skill。通过自然语言对话，完成应用页面探索、知识库构建、测试框架搭建、测试执行和报告生成。

## 快速开始

### 1. 安装

两种使用方式：

**方式 A：作为 Claude Skill（推荐）**

将 `droid-pilot` 复制到项目的 `.claude/skills/` 下，生成的测试代码会自动放在项目根目录：

```bash
mkdir -p /path/to/your-project/.claude/skills
cp -r droid-pilot /path/to/your-project/.claude/skills/
```

```
your-project/
├── .claude/skills/droid-pilot/   ← 工具在这里
├── pages/                        ← 生成的 Page Object
├── tests/                        ← 生成的测试用例
└── reports/                      ← 测试报告
```

**方式 B：独立使用**

直接在任意目录运行 droid-pilot 脚本，通过 `--dir` 参数指定测试代码输出目录：

```bash
python droid-pilot/scripts/scaffold.py init -p com.xxx --dir /path/to/your-project
```

### 2. 环境依赖

- Python 3.8+
- ADB（Android Debug Bridge）
- `uiautomator2`：`pip install uiautomator2`
- `pytest`：`pip install pytest`（测试执行时需要）
- Poco（可选，游戏类应用）：`pip install pocoui`

### 3. 连接设备

确保 Android 设备已连接并开启 USB 调试：

```bash
adb devices
```

### 4. 开始对话

在项目目录下启动 Claude Code，直接用自然语言交流：

```
> 帮我探索一下这个应用，包名是 com.example.myapp
> 这是首页
> 帮我搭建自动化框架
> 测全部
> 看测试报告
```

## 工作流程

```
探索页面 → 构建知识库 → 搭建框架 → 执行测试 → 生成报告
Phase 1-3      ↑          Phase 4     Phase 5     Phase 6
              共创
```

### Phase 1-3：探索 & 知识库

Claude 自动（或与你共创）遍历应用页面，为每个页面记录：
- 页面标识和识别条件
- 所有可交互元素及其定位方式
- 页面间的跳转关系（路由）

**共创模式**：你可以手动操作手机导航到某个页面，告诉 Claude "这是xx页面"，Claude 会自动 dump 并录入，比纯自动探索更快。

### Phase 4：框架搭建

基于知识库自动生成：

```
your-project/
├── pages/
│   ├── base_page.py          # 基类，封装所有操作
│   ├── home_page.py          # Page Object（自动生成方法）
│   └── settings_page.py
├── tests/
│   ├── conftest.py           # fixtures（设备、包名、页面实例、应用重启）
│   ├── test_home.py          # 测试骨架（页面加载、路由、验证点）
│   └── test_settings.py
└── reports/                  # 测试报告输出目录
```

每个 Page Object 自动包含：
- 元素定位信息（`Elements` 类）
- 按元素类型生成的操作方法（`tap_btn_xxx()`、`input_xxx(text)`、`get_xxx()`）
- 页面验证方法（`verify_on_page()`）

### Phase 5：测试执行

Claude 驱动模式 —— Claude 读取测试代码，逐步执行操作，每步截图并判断 pass/fail：

1. 每个测试前 force-stop + 重启应用（保证隔离）
2. 逐步执行 UI 操作
3. 截图 + dump 上下文 → Claude 判断结果
4. 累积所有测试结果

### Phase 6：测试报告

生成结构化报告：
- `report.json` —— 完整数据（每步操作、截图路径、Claude 判断）
- `summary.md` —— 人类可读摘要（通过率、失败详情）

## 使用技巧

### 提供包名

Claude 会主动询问包名。如果不知道，可以：
- 把应用打开 → 告诉 Claude "帮我查一下当前应用包名"
- 告诉 Claude 应用名字 → Claude 通过 `pm list packages` 搜索

### 提供便捷登录

如果你的应用支持以下任何一种方式，提前告诉 Claude 可以大幅提升效率：

```bash
# broadcast 注入
adb shell am broadcast -a com.xxx.LOGIN --es token "test_token"

# intent 参数
adb shell am start -n com.xxx/.LoginActivity --es account "test"

# GM 命令
# 任何可以跳过 UI 登录的方式
```

### 游戏类应用（Poco）

游戏引擎需要时间初始化，告诉 Claude 启动到可操作需要多久，会自动调整等待时间。

## 目录结构

```
droid-pilot/
├── SKILL.md              # Claude 行为指引（触发条件、执行流程）
├── README.md             # 本文件
├── core/                 # 驱动层
│   ├── drivers/
│   │   ├── base.py       #   Element 数据类 + BaseDriver 抽象类
│   │   ├── u2_driver.py  #   UIAutomator2 驱动
│   │   ├── poco_driver.py#   Poco 驱动（Unity/Cocos）
│   │   ├── vision_driver.py # 纯视觉驱动（截图+坐标）
│   │   └── auto_driver.py#   自动路由（u2→poco→vision）
│   ├── page_matcher.py   #   页面匹配引擎
│   └── fingerprint.py    #   页面指纹 & Jaccard 相似度
├── scripts/              # 工具脚本（I/O only，不做决策）
│   ├── explore.py        #   探索状态管理
│   ├── page_learn.py     #   页面知识 dump/write
│   ├── page_identify.py  #   页面识别
│   ├── execute_action.py #   执行 UI 操作
│   ├── screen_context.py #   屏幕上下文
│   ├── scaffold.py       #   项目脚手架
│   ├── page_gen.py       #   Page Object 生成
│   ├── test_runner.py    #   测试运行
│   └── report.py         #   报告生成
├── knowledge/            # 知识库
│   ├── apps/             #   应用级文档
│   └── pages/{package}/  #   页面 dict + 拓扑 + 探索状态
└── templates/            # 代码生成模板
    ├── base_page.py.tpl
    ├── conftest.py.tpl
    ├── page_object.py.tpl
    └── test_skeleton.py.tpl
```

## 设计原则

1. **Claude 做决策，脚本做 I/O** —— 所有分析、命名、判断由 Claude 完成，脚本只负责数据读写
2. **Page Object 通过 subprocess 调用脚本** —— 保持解耦，不直接 import core 模块
3. **Claude-as-Judge** —— 每步截图 + dump 上下文，Claude 判断 pass/fail，比硬编码 assert 更灵活
4. **知识库在 skill 中，生成代码在项目中** —— 知识可复用，测试代码跟项目走
5. **不引入外部模板引擎** —— 用 `string.Template` 保持零外部依赖
