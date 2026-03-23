# Droid Pilot

Android UI automation agent powered by Claude Code Skill. Through natural language conversation, complete the full workflow: page exploration, knowledge base building, test framework scaffolding, test execution, and report generation — no prior automation experience needed.

## How It Works

```
Explore pages → Build knowledge base → Scaffold framework → Run tests → Generate report
  Phase 1-3            ↑                   Phase 4          Phase 5      Phase 6
                  Co-creation
```

Claude acts as the decision-maker. Scripts handle only I/O. Every action step is verified via screenshot + screen dump — Claude judges pass/fail rather than relying on hardcoded assertions.

## Quick Start

### 1. Install

**Option A: As a Claude Code Skill (recommended)**

Copy `droid-pilot` into your project's `.claude/skills/` directory. Generated test code will be placed in your project root.

```bash
mkdir -p /path/to/your-project/.claude/skills
cp -r droid-pilot /path/to/your-project/.claude/skills/
```

```
your-project/
├── .claude/skills/droid-pilot/   ← tool lives here
├── pages/                        ← generated Page Objects
├── tests/                        ← generated test cases
└── reports/                      ← test reports
```

**Option B: Standalone**

Run droid-pilot scripts directly from any directory, specifying the output path with `--dir`:

```bash
python droid-pilot/scripts/scaffold.py init -p com.example.myapp --dir /path/to/your-project
```

### 2. Requirements

- Python 3.8+
- ADB (Android Debug Bridge)
- `uiautomator2`: `pip install uiautomator2`
- `pytest`: `pip install pytest` (required for test execution)
- Poco (optional, for game apps): `pip install pocoui`

### 3. Connect a Device

Make sure your Android device is connected with USB debugging enabled:

```bash
adb devices
```

### 4. Start Chatting

Launch Claude Code in your project directory and talk in plain language:

```
> Explore this app, package name is com.example.myapp
> This is the home page
> Scaffold the automation framework
> Run all tests
> Show me the test report
```

## Phases

### Phase 1–3: Explore & Build Knowledge Base

Claude traverses app pages automatically — or together with you (co-creation mode). For each page, it records:

- Page identity and recognition conditions
- All interactive elements with locators
- Navigation routes between pages

**Co-creation mode**: You navigate the phone manually to any page, tell Claude "this is the settings page", and Claude dumps it and adds it to the knowledge base. Much faster than fully automated exploration.

### Phase 4: Scaffold the Framework

Generates a complete project structure from the knowledge base:

```
your-project/
├── pages/
│   ├── base_page.py          # base class with all UI operations
│   ├── home_page.py          # Page Object (auto-generated methods)
│   └── settings_page.py
├── tests/
│   ├── conftest.py           # fixtures: device, package, page instances, app restart
│   ├── test_home.py          # test skeleton: page load, routing, checkpoints
│   └── test_settings.py
└── reports/
```

Each Page Object includes:
- Element locators (`Elements` class)
- Auto-generated action methods: `tap_btn_xxx()`, `input_xxx(text)`, `get_xxx()`
- Page verification method: `verify_on_page()`

### Phase 5: Test Execution (Claude-driven)

Claude reads the test source code and executes each step one by one:

1. Force-stop + restart app before each test (isolation)
2. Execute UI actions step by step
3. Screenshot + dump context → Claude judges pass/fail
4. Accumulate results across all tests

**Self-healing**: When a step fails, Claude first classifies the cause:
- **Environment noise** (popups, crashes, wrong foreground app) → auto-dismiss and retry, no code change needed
- **Test defect** (broken locator, wrong route, missing step) → record, continue the test, fix the code after the full batch completes

### Phase 6: Test Report

```
reports/{run_id}/
├── report.json    # full data: each step, screenshot path, Claude judgment
├── summary.md     # human-readable: pass rate, failure details, suggestions
└── screenshots/
```

## Tips

### Package Name

Claude will ask for the package name. If you don't know it:

```bash
# Get foreground app package
adb shell dumpsys window | grep mCurrentFocus

# Search by keyword
adb shell pm list packages | grep keyword
```

### Fast Login

If your app supports any shortcut login method, tell Claude upfront — it can skip UI login entirely on every test restart:

```bash
# Broadcast token injection
adb shell am broadcast -a com.example.LOGIN --es token "test_token"

# Intent with credentials
adb shell am start -n com.example/.LoginActivity --es account "test"
```

Claude will record this in the `restart_app` fixture in `conftest.py`.

### Game Apps (Poco)

Tell Claude how long the app takes to reach an interactive state after launch. Poco needs to wait for the game engine to initialize before connecting.

## Project Structure

```
droid-pilot/
├── SKILL.md              # Claude behavior guide (triggers, workflow)
├── README.md             # this file (Chinese)
├── README_EN.md          # this file (English)
├── core/                 # driver layer
│   ├── drivers/
│   │   ├── base.py       #   Element dataclass + BaseDriver abstract class
│   │   ├── u2_driver.py  #   UIAutomator2 driver
│   │   ├── poco_driver.py#   Poco driver (Unity/Cocos)
│   │   ├── vision_driver.py # vision-only driver (screenshot + coordinates)
│   │   └── auto_driver.py#   auto-routing (u2 → poco → vision)
│   ├── page_matcher.py   #   page matching engine
│   └── fingerprint.py    #   page fingerprint & Jaccard similarity
├── scripts/              # tool scripts (I/O only, no decisions)
│   ├── explore.py        #   exploration state management
│   ├── page_learn.py     #   page knowledge dump/write
│   ├── page_identify.py  #   page identification
│   ├── execute_action.py #   execute UI actions
│   ├── screen_context.py #   screen context
│   ├── scaffold.py       #   project scaffolding
│   ├── page_gen.py       #   Page Object generation
│   ├── test_runner.py    #   test runner
│   └── report.py         #   report generation
├── knowledge/            # knowledge base
│   ├── apps/             #   app-level docs
│   └── pages/{package}/  #   page dicts + topology + exploration state
└── templates/            # code generation templates
    ├── base_page.py.tpl
    ├── conftest.py.tpl
    ├── page_object.py.tpl
    └── test_skeleton.py.tpl
```

## Design Principles

1. **Claude decides, scripts do I/O** — all analysis, naming, and judgment are done by Claude; scripts only handle data read/write
2. **Page Objects call scripts via subprocess** — keeps the tool decoupled; no direct imports of core modules
3. **Claude-as-Judge** — every step produces a screenshot + dump; Claude judges pass/fail, more flexible than hardcoded assertions
4. **Knowledge base in the skill, generated code in the project** — knowledge is reusable; test code lives with the project
5. **No external template engines** — uses `string.Template` to keep dependencies at zero

## Supported Drivers

| Driver | Use case |
|--------|----------|
| `u2` | Standard Android apps (UIAutomator2) |
| `poco` | Game apps (Unity / Cocos engine) |
| `vision` | Fallback: screenshot + coordinate-based interaction |
| `auto` | Auto-routing: tries u2 → poco → vision in order |
