---
name: droid-pilot
description: "Android UI 自动化 Agent —— 探索应用页面、构建知识库、搭建测试框架、执行测试、生成报告"
disabled: false
---

# Droid Pilot

Android UI 自动化 Agent。通过对话驱动，完成从页面探索到测试执行的全流程。

## Trigger

当用户表达以下意图时触发：

| 用户意图 | 对应阶段 |
|---------|---------|
| 探索 xxx 应用 / 学习 xxx 的页面 / 帮我把页面录下来 | Phase 1 → 2 → 3 |
| 帮我搭建 xxx 的自动化框架 | Phase 4 |
| 测 xxx / 测全部 / 运行测试 | Phase 5 |
| 看测试报告 / 报告 | Phase 6 |

---

## 目录约定

droid-pilot 是一个**自包含工具**，不应与用户项目代码混在一起。

**两种使用方式**：

1. **作为 Claude Skill 使用**（推荐）：用户将 `droid-pilot/` 复制到项目的 `.claude/skills/` 下
2. **独立使用**：用户直接在 droid-pilot 所在目录运行

**`$PROJECT_DIR` 推断规则**（Claude 必须遵循）：

1. 如果 droid-pilot 位于 `{某路径}/.claude/skills/droid-pilot/`，则 `$PROJECT_DIR` = `{某路径}`（项目根目录）
2. 如果 droid-pilot 不在 `.claude/skills/` 下，则 `$PROJECT_DIR` = 用户当前工作目录（`$CWD`）
3. 用户显式指定了 `--dir` 参数时，以用户指定为准

**生成的文件始终放在 `$PROJECT_DIR` 下**，不放在 droid-pilot 内部：
```
$PROJECT_DIR/
├── pages/          # Page Object
├── tests/          # 测试用例
└── reports/        # 测试报告
```

**脚本路径变量**：
```bash
# 根据 droid-pilot 位置确定
SKILL=.claude/skills/droid-pilot       # 方式 1
SKILL=/path/to/droid-pilot             # 方式 2
```

---

## 工具脚本

所有脚本位于 `scripts/`，**只做 I/O，不做决策**。决策、分析、命名全部由 Claude 完成。

```bash
python $SKILL/scripts/<script> <subcommand> [args]
```

### 探索阶段脚本

| 脚本 | 用途 |
|------|------|
| `explore.py status -d DEVICE -p PKG` | 当前探索状态（我在哪、下一步探哪） |
| `explore.py visited -p PKG --page ID` | 标记页面已访问 |
| `explore.py blocked -p PKG --page ID --route ELEM --reason "xxx"` | 标记路由阻塞 |
| `explore.py reset -p PKG` | 清空探索进度 |
| `page_learn.py dump -d DEVICE` | dump 当前页面原始元素 |
| `page_learn.py write -p PKG --data '{...}'` | 写入 Claude 生成的 page dict |
| `page_identify.py -d DEVICE -p PKG` | 识别当前页面（已知/未知） |
| `execute_action.py -d DEVICE -a ACTION -t TARGET [-v VALUE]` | 执行 UI 操作 |
| `screen_context.py -d DEVICE [-f json\|text]` | 获取当前屏幕上下文 |

### 框架 & 测试阶段脚本

| 脚本 | 用途 |
|------|------|
| `scaffold.py init -p PKG --dir DIR` | 初始化项目结构（tests/pages/reports） |
| `scaffold.py status --dir DIR` | 检查项目结构状态 |
| `page_gen.py list -p PKG` | 列出知识库中所有已知页面 |
| `page_gen.py generate -p PKG --dir DIR [--page ID] [--force]` | 生成 Page Object + 测试骨架 |
| `test_runner.py collect --dir DIR` | 收集所有测试用例（ast 解析，不 import） |
| `test_runner.py run --dir DIR --test TEST_ID -d DEVICE` | pytest 运行单个测试 |
| `test_runner.py screenshot -d DEVICE --out PATH` | 截图保存 |
| `test_runner.py assert-screen -d DEVICE --dir DIR --run RUN_ID --step STEP` | 截图 + dump 上下文供 Claude 判断 |
| `report.py generate --dir DIR --data JSON` | 生成 report.json + summary.md |
| `report.py view --dir DIR [--run RUN_ID]` | 查看报告内容 |
| `report.py list --dir DIR` | 列出所有历史报告 |

---

## Phase 1：初始化

### 1.1 检查设备

```bash
adb devices
```
- 无设备 → 告知用户，等待连接
- 多设备 → 让用户选择，记录 DEVICE_ID

### 1.2 确认包名

**必须主动向用户确认包名**，不要依赖自动检测。

- 用户已提供包名 → 直接使用
- 用户不知道包名 → 协助定位：
  1. 让用户把目标应用打开到前台
  2. `adb -s $DEVICE shell dumpsys window | grep mCurrentFocus`
  3. 或用关键词搜索：`adb -s $DEVICE shell pm list packages | grep 关键词`
  4. 列出候选包名，让用户确认

### 1.3 确认登录方式

**主动引导用户提供便捷登录手段**，告知可以大幅加快测试进度：

> "你的应用有没有便捷的登录方式？比如 adb broadcast 注入 token、GM 命令、测试环境免登录开关等。
> 有的话可以省掉每次 UI 登录，测试跑得更快更稳定。"

常见方式（举例给用户参考）：
- `adb shell am broadcast -a com.xxx.LOGIN --es token "xxx"`
- GM 命令 / 后台接口写入登录态
- `adb shell am start -n com.xxx/.LoginActivity --es account "test"`
- SharedPreferences / 配置文件写入 token
- 测试环境免登录开关

用户提供后 → 记录到 `conftest.py` 的 `restart_app` fixture 中。
用户没有 → 退回 UI 登录流程。

### 1.4 确认驱动和启动等待

如果应用使用 Poco（游戏类应用），需要确认启动等待时间：

> "这个游戏从启动到进入可操作画面大概需要多久？Poco 需要等引擎初始化完成才能连接。"

- Poco 应用重启后需等待引擎初始化（通常 3-5 秒，重度游戏可能更久）
- Poco dump 返回空或连接失败 → 优先怀疑初始化时机，等一等再重试
- 将等待时间记录到 `conftest.py` 的 `restart_app` fixture 中

### 1.5 检查应用状态

```bash
adb -s $DEVICE shell dumpsys activity activities | grep mResumedActivity
```
- 应用不在前台 → 启动：`adb -s $DEVICE shell monkey -p $PKG -c android.intent.category.LAUNCHER 1`
- 包名不存在 → 请用户确认包名

### 1.6 加载已有知识

```bash
python $SKILL/scripts/explore.py status -d $DEVICE -p $PKG
```
读取 `suggestion` 字段：
- `"learn"` → 进入 Phase 2（当前页面未知）
- `"explore"` → 进入 Phase 2（有未探索路由）
- `"done"` → 告知用户知识库已完整，询问是否重置或进入 Phase 4

---

## Phase 2：探索循环

### 共创模式

进入探索前，**主动告知用户可以共创**：

> "你也可以自己在手机上打开某个页面，然后告诉我'这是xx页面'，我来帮你快速录入。
> 自动探索和手动录入可以混着来，怎么方便怎么来。"

用户说"这是xx页面"时：
1. `page_learn.py dump` 获取当前屏幕
2. 用用户提供的名称作为页面名
3. Claude 分析 + 生成 page dict
4. `page_learn.py write` 写入知识库
5. `explore.py visited` 标记已访问

### Step A：了解当前状态

```bash
python $SKILL/scripts/explore.py status -d $DEVICE -p $PKG
```
关注：`suggestion`（决定下一步）、`current_page`（null = 未知）、`next_routes`（可探索路由）

### Step B：学习未知页面（suggestion = "learn"）

1. `page_learn.py dump -d $DEVICE`
2. Claude 分析 dump 结果，生成 page dict（语义命名、checkpoint 标记、identify 条件）
3. `page_learn.py write -p $PKG --data '...'`
4. `explore.py visited -p $PKG --page $PAGE_ID`

### Step C：导航探索（suggestion = "explore"）

取 `next_routes[0]`，执行点击，等待 1-2 秒，再 `explore.py status` 验证页面变化。

### Step D：阻塞处理

| 情况 | 处理 |
|------|------|
| 元素找不到 | 询问用户，页面可能有变化 |
| 点击后页面不变 | 询问前置条件 |
| 遇到登录页 | 请求测试账号 |
| 遇到权限弹窗 | 询问允许/拒绝 |
| 遇到付费弹窗 | 询问是否跳过 |
| 全部路由阻塞 | 回退到上一页 |

---

## Phase 3：探索完成

`suggestion = "done"` 时：
1. 输出探索报告（页面列表、拓扑摘要、阻塞路由）
2. 询问用户 → 搭建框架（Phase 4）或结束

---

## Phase 4：框架搭建

### 4.1 检查知识库

```bash
python $SKILL/scripts/page_gen.py list -p $PKG
```
无页面 → 引导先探索（Phase 1-3）

### 4.2 初始化项目结构

```bash
python $SKILL/scripts/scaffold.py init -p $PKG --dir $PROJECT_DIR
```

### 4.3 生成 Page Object 和测试骨架

```bash
python $SKILL/scripts/page_gen.py generate -p $PKG --dir $PROJECT_DIR
```

### 4.4 告知用户

列出生成的文件，建议补充测试逻辑。支持 `--page ID` 单页生成、`--force` 覆盖。

---

## Phase 5：测试执行（Claude 驱动）

### 5.1 收集用例

```bash
python $SKILL/scripts/test_runner.py collect --dir $PROJECT_DIR
```

### 5.2 逐步执行

对每个测试：
1. **隔离**：`adb shell am force-stop $PKG` + 重启
2. **读测试源码**：Claude 理解每个步骤
3. **执行 + 断言**：`execute_action.py` → `test_runner.py assert-screen` → Claude 判断 pass/fail
4. **记录**：action、target、result、screenshot、claude_judgment

### 5.3 自愈机制（批量运行时必须启用）

操作失败时，**先判断失败原因属于哪一类**，再决定如何处理：

#### 类型 A：环境噪音（与用例无关）

与测试逻辑无关的外部干扰，处理后直接继续，**不需要修改用例**。

| 优先级 | 异常情况 | 自愈动作 |
|--------|---------|---------|
| 1 | 系统弹窗（更新、权限请求） | dump 当前屏幕，找到"取消"/"跳过"/"稍后"按钮点击关闭 |
| 2 | 应用内弹窗（广告、引导、公告） | 找到关闭按钮或按返回键 dismiss |
| 3 | 不在目标应用（被拉起其他应用） | `adb shell am force-stop` 其他应用 + 返回 |
| 4 | 应用崩溃 / 不在前台 | `force-stop $PKG` + 重启应用 |
| 5 | 页面状态不可恢复 | **skip 当前 case**，记录原因，继续下一个 |
| 6 | 设备断连 | **中断整个批次**，这是唯一允许中断的情况 |

#### 类型 B：用例缺陷（测试代码写得不对）

失败原因是用例本身的问题，处理后还要在**批次结束后自动修复用例代码**。

常见用例缺陷判断标准：
- 元素定位器失效（resource_id / text 已变更、拼写错误）
- 步骤前置假设错误（操作了不在当前状态的元素）
- 路由目标页面变了（页面跳转路径发生变化）
- 等待时机不对（操作太快，页面还未渲染完成）

修复规则：
- **最小改动**：只改失败的那一步，不重写整个用例
- **改定位器**：优先用 text 替换 resource_id（text 更稳定）；若 text 也变了，用 screen_context.py dump 找到正确值
- **改路由**：更新 `routes` 字典中的目标页面 id
- **加等待**：在操作前插入 `time.sleep(1)` 或重试逻辑
- 修改后在报告中记录：`"case_fix": {"file": "...", "reason": "...", "change": "..."}`

#### 统一自愈流程

```
操作失败 → screen_context.py dump 当前屏幕
  → Claude 判断：环境噪音 还是 用例缺陷？
  ↓ 环境噪音                    ↓ 用例缺陷
  执行对应处理                   记录缺陷，跳过当前步骤
  重试原操作（最多 1 次）         继续后续步骤（尽量完成 case）
  仍失败 → skip case             批次结束后修复对应用例代码
```

**关键原则**：
- 自愈过程中的操作也要记录到报告中（标记为 `"type": "self_heal"`）
- 单个 case 失败不影响后续 case 执行
- 每个 case 开始都是 force-stop 重启，所以上一个 case 的异常不会污染下一个
- 用例修复只在批次全部跑完后执行，不在运行中途修改文件

### 5.4 累积结果 → Phase 6

---

## Phase 6：报告生成

```bash
echo '$RESULTS_JSON' | python $SKILL/scripts/report.py generate --dir $PROJECT_DIR
```

Claude 读取 `summary.md`，向用户汇报通过率、失败分析、改进建议。

---

## page dict 规范

```json
{
  "id": "snake_case_页面标识",
  "name": "中文页面名称",
  "driver": "u2 | poco | vision | auto",
  "identify": {
    "activity": "ActivityShortName",
    "must_have": [{"text": "最有区分度的文字"}]
  },
  "elements": {
    "btn_xxx": {"text": "确认", "type": "button", "checkpoint": true},
    "tab_xxx": {"text": "首页", "type": "tab"},
    "input_xxx": {"resource_id": "et_name", "type": "input"}
  },
  "overlays": {
    "dialog_ad": {"contains": ["广告"], "auto_dismiss": "关闭"}
  },
  "routes": {
    "btn_xxx": "target_page_id"
  }
}
```

**元素命名**：`btn_` 按钮 | `tab_` Tab | `input_` 输入框 | `chk_` 复选框 | `lbl_` 文字 | `list_` 列表

**checkpoint 标准**：核心功能按钮、状态文字、分数/数值展示、关键开关

---

## 目录结构

```
droid-pilot/                         # 工具本体（自包含，不放用户代码）
├── SKILL.md                         # 本文件：Claude 行为指引
├── README.md                        # 用户使用说明
├── core/                            # 驱动层（u2/poco/vision/auto）
├── scripts/                         # 工具脚本（I/O only）
├── knowledge/                       # 知识库（页面/拓扑/探索状态）
│   ├── apps/{package}.md
│   └── pages/{package}/*.py
└── templates/                       # 代码生成模板

$PROJECT_DIR/                        # 用户项目根目录（生成到这里）
├── .claude/skills/droid-pilot/      # 工具放在这里（方式 1）
├── pages/
│   ├── base_page.py                 # BasePage 基类
│   └── {page_id}.py                 # Page Object
├── tests/
│   ├── conftest.py                  # pytest fixtures
│   └── test_{page_id}.py            # 测试用例
└── reports/{run_id}/                # 测试报告
    ├── report.json
    ├── summary.md
    └── screenshots/
```
