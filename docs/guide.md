# Droid Pilot 使用指南（对话示例）

通过一问一答展示完整使用流程。

---

## 第一步：探索页面，建立知识库

---

**用户**：帮我探索一下我的应用

**Claude**：好的，先确认几个信息：
1. 设备已连接了吗？（我会运行 `adb devices` 检查）
2. 应用包名是什么？不知道的话，把应用打开到前台告诉我，我帮你查

---

**用户**：已连接，应用叫"示例应用"，包名不知道

**Claude**：我来帮你找——`adb shell pm list packages | grep 关键词`，找到了：`com.example.myapp`，是这个吗？

---

**用户**：对

**Claude**：好，应用已在前台。另外问一下：你们有没有便捷的登录方式？比如 adb broadcast 注入 token、测试账号免登录、GM 命令之类的。有的话可以省掉每次 UI 登录，测试跑得更快更稳。

---

**用户**：有，`adb shell am broadcast -a com.example.myapp.LOGIN --es token "YOUR_TEST_TOKEN"`

**Claude**：记录了，我会把这个写进 conftest.py 的 restart_app fixture。开始探索，先 dump 当前页面……

当前是「首页」，我看到底部有 4 个 tab：首页、账单、预算、我的。我来把这个页面录入知识库。

你可以手动操作：先切到「账单」tab，切好了告诉我"这是账单页"，我来录入。也可以让我自动点。你选哪种？

---

**用户**：我来切，这是账单页

**Claude**：收到，正在 dump 账单页元素……已录入。继续切下一个吧。

---

**用户**：这是预算页

**Claude**：录入完成。

---

**用户**：这是"我的"页

**Claude**：录入完成。当前已录入 4 个页面：首页、账单、预算、我的。

知识库已完整，要继续搭建测试框架吗？

---

## 第二步：搭建测试框架

---

**用户**：搭建一下

**Claude**：好，初始化项目结构……

已生成：
```
pages/
  base_page.py        ← 封装了所有 UI 操作的基类
  home_page.py        ← 首页 Page Object
  bill_page.py        ← 账单页 Page Object
  budget_page.py
  profile_page.py
tests/
  conftest.py         ← 含 restart_app（用你提供的 broadcast 登录）
  test_home.py        ← 首页测试骨架
  test_bill.py
  test_budget.py
  test_profile.py
```

每个测试文件里已有基础骨架（页面加载验证、路由验证、checkpoint 验证），你可以直接在骨架上补充业务逻辑。

---

## 第三步：执行测试

---

**用户**：测全部

**Claude**：收集到 12 个测试用例，开始逐个执行……

**[test_home::test_page_loads]**
- force-stop + 广播注入登录态 → 截图确认在首页 ✓
- 验证 checkpoint（余额文字、记一笔按钮）→ 均可见 ✓
- **PASSED**

**[test_home::test_nav_to_bill]**
- 点击「账单」tab
- 截图确认跳转到账单页 ✓
- **PASSED**

**[test_bill::test_page_loads]**
- force-stop + 重启……当前页是首页，需要导航到账单
- （检测到用例步骤缺失：没有导航到账单的步骤）
- 自愈：执行 tap 账单 tab，继续后续步骤
- 截图确认在账单页 ✓
- **PASSED**（记录用例缺陷，批次结束后修复）

...（继续执行剩余 9 个用例）

---

**全部完成，生成报告中……**

---

## 第四步：查看报告

---

**用户**：看报告

**Claude**：

**测试报告 run_20260323_143022**

| 指标 | 结果 |
|------|------|
| 总用例数 | 12 |
| 通过 | 10 |
| 失败 | 1 |
| Skip | 1 |
| 通过率 | 83% |

**失败详情：**
- `test_budget::test_add_budget`
  - 第 3 步失败：点击"添加预算"按钮，元素定位器 `resource_id: btn_add` 未找到
  - 当前屏幕中找到文字为"新建预算"的按钮（resource_id 已更新）
  - **已自动修复** `tests/test_budget.py` 第 18 行，将 resource_id 改为 text 定位

**Skip 详情：**
- `test_profile::test_logout`
  - 第 2 步：需要滑动到页面底部，当前用例未写滑动操作
  - 已记录，建议手动补充

**建议：**
1. `test_budget.py` 已自动修复，下次运行应通过
2. `test_profile::test_logout` 需要补充滑动到底部的步骤

---

## 常见问答

---

**Q：我改了应用，页面有变化，怎么更新知识库？**

**A**：把改动的页面打开，告诉我"这是 xx 页，重新录一下"，我会重新 dump 并覆盖旧的页面数据，然后用 `--force` 重新生成 Page Object。

---

**Q：我的应用是游戏，Poco 驱动，怎么用？**

**A**：可以用。告诉我启动到可操作画面大概需要多久（游戏引擎初始化时间），我会在每次重启后等对应的时间再开始操作，避免 Poco 连不上。

---

**Q：能只跑某一个测试吗？**

**A**：能。告诉我"测 test_home::test_page_loads"，我只跑这一个。

---

**Q：生成的代码放在哪里？**

**A**：放在你当前的项目目录下（pages/ tests/ reports/），不会放进 droid-pilot 工具目录里。

---

**Q：知识库会影响其他项目吗？**

**A**：不会。每个应用的知识库用包名隔离，存在 droid-pilot/knowledge/pages/{package}/ 下。换项目只需重新确认包名，知识库互不干扰。
