# FirstEventSelenium 技术架构 · 数据流向 · 面试要点

> 基于当前代码库最新状态整理（37 个场景用例 / 6 大分组）。
> 被测系统：**FirstSeleniumUIEvent**（Vue 3 + Element Plus 前端 `:5173`，Flask 后端 `127.0.0.1:5050`，结算与密文数据真实落盘 SQLite）。
> 工程性质：独立、自包含的 Selenium UI 自动化工程，与被测系统、参考工程物理隔离，不修改被测代码。

---

## 第一部分：技术架构

### 1.1 技术栈

| 类别 | 选型 | 说明 |
| --- | --- | --- |
| 语言 | Python 3.11+（3.13 验证） | 大量 `from __future__ import annotations` 与类型标注 |
| 自动化内核 | Selenium ≥ 4.20 | WebDriver + CDP（Chromium 网络层取证） |
| 测试框架 | pytest ≥ 8.0 | fixture / hook / marker（smoke、regression） |
| 报告 | allure-pytest ≥ 2.13 | 经 `allure_compat` 兼容层接入，可整体降级 |
| 配置 | PyYAML + INI（configparser） | 运行配置与元素定位双配置源 |
| 接口辅助 | requests | 直连后端 API，绕过页面做数据准备与兜底断言 |
| 驱动管理 | webdriver-manager | Chrome/Edge/Firefox 驱动自动适配 |

### 1.2 分层总览

```
case/        用例层     pytest 用例 + fixture + 失败取证 hook
business/    业务层     场景业务组合（biz_step 打标 + allure 步骤）
handle/      操作层     场景元素级操作流 + 跨场景平台动作
base/        定位层     场景码 -> INI -> (By, value) 定位器解析
common/      基础层     显式等待封装 + 统一异常体系
util/        工具层     驱动工厂 / API / SQLite / 金额 / 摘要 / 网络取证 / 截图 / allure 兼容
config/      配置层     settings.yaml（运行配置）+ 6 个 *Element.ini（元素定位）
log/         日志层     全局 Logger（控制台 + 按天滚动文件）
run_tests.py 入口层     多模式运行（all / smoke / regression / allure）
conftest.py  根配置     仅注册 --browser 命令行选项
```

依赖方向严格单向：`case → business → handle → base + common`，`util / config / log` 为横切支撑，下层永不反向依赖上层。

### 1.3 各层职责与设计目的

#### ① 配置层 `config/` —— 双配置源分离

| 文件 | 作用 | 设计目的 |
| --- | --- | --- |
| `settings.yaml` | 环境地址、超时、浏览器类型/参数、下载目录、截图开关 | 运行参数集中一处；`Config` 单例 + 点路径读取（`browser.type`），环境经 `env.active` 切换 |
| `settings.py` | `Config` 单例配置中心 | 全局只加载一次；缺键返回 default 而非抛错；配置格式错误抛 `ConfigError` 并带配置键/文件名证据 |
| `*Element.ini`（6 个） | 37 个场景的 element 定位，`key=by>value`（如 `css>.mask`、`xpath>//button[...]`） | **元素定位与代码物理分离**：前端改样式只动 INI 不动 Python；by 缺省为 xpath，降低配置书写成本 |

#### ② 定位层 `base/find_element.py` —— 场景码注册器

- 场景码前缀（I/W/M/C/X/E）→ 分组 INI 的映射表 `GROUP_INI`，Section 名即场景码本身。
- 解析 `by>value` 为 Selenium `(By, value)` 元组，`_BY_ALIAS` 支持 8 种定位方式。
- **双级缓存**：INI 文件句柄缓存（`_ini_cache`）+ 定位器解析缓存（`locator_cache`），37 个场景反复定位不重复读盘、不重复解析。
- 与 WebDriver 完全解耦（构造参数 driver 仅为历史兼容），可独立单测。

#### ③ 基础层 `common/` —— 等待体系 + 异常体系

**`webdriver_wait_common.py`**：所有元素操作的唯一入口。

- 显式等待三档：`visibility`（可见）/ `presence`（在 DOM）/ `clickable`（可点击），超时时长从 `settings.yaml` 读取。
- `click_params`：**原生点击失败自动 JS 点击兜底**；`send_keys_params`：等待可见 → 清空 → 输入。
- 等待超时不是抛原生 `TimeoutException`，而是**当场截图**后包装为 `ElementNotFoundError`（携带定位器 + 截图路径）——取证发生在离现场最近的时刻。

**`exceptions.py`**：框架统一异常体系。

- `FrameworkError` 基类定义 `evidence()` 协议：子类（`ElementNotFoundError` / `BusinessError` / `ConfigError`）只负责提供结构化证据，`__str__` 自动拼装。
- `format_exception_chain()` 沿 `__cause__` / `__context__` 展开异常链；**硬性约定：异常链恒为 2 层**（技术根因 → 领域异常），链深 >2 即说明某层做了多余翻译。
- `find_in_chain()` 沿链捞取指定属性（如根因异常上挂的截图路径）。

#### ④ 操作层 `handle/` —— 场景操作流

- `base_scenario_handle.py`：场景句柄基类。传入场景码后，`loc(key)` 一行完成「INI 读取 → 定位器解析」，并收敛 click / fill / js_fill / 结果区断言等高频操作。`js_fill` 用原生 value setter + 派发 input/change 事件，**解决 Vue v-model 受控组件 send_keys 不同步的问题**。
- `action_support.py`：跨场景平台动作库（窗口句柄切换、嵌套 iframe、Shadow DOM 穿透、原生 alert、ActionChains hover/拖拽、文件上传、contenteditable 富文本、内部滚动容器）。
- `*_handles.py`（6 个）：每个场景一个 Handle 类，只描述「怎么操作这个页面」，不含业务流程编排。

#### ⑤ 业务层 `business/` —— 业务组合 + 异常打标

- `*_business.py`（6 个）：把 Handle 的原子操作按业务步骤组合，每步包在 `biz_step(...)` 上下文中（等价于 allure step）。
- `business_context.py`：**异常流的打标层**。`biz_step` 从调用栈自动推断场景码（`run_e01_xxx` → `E01`），遵循严格的三分类：
  1. `FrameworkError` 已自带技术证据 → **裸重抛**，不套链；
  2. `AssertionError`（业务期望未达成）→ 包装为 `BusinessError` 并 `raise ... from` 挂上「场景码 + 步骤名 + 入参」；
  3. 其余异常（pytest 控制流等）→ 原样透传。
- 复杂场景用 `NamedTuple` 返回结构化结果（如 `I18RecapResult`：调整前后页面汇总 + 库侧明细求和），把「取数」与「断言」分离，用例层拿到的是可直接断言语义的数据。

#### ⑥ 用例层 `case/` —— 用例 +  fixture + 收敛取证

- `test_*.py`（6 个，37 用例）：每个用例 `open_scenario(driver, "/i/01")` 直达场景路由，断言统一落在页面底部「操作结果」日志区。
- `conftest.py`：
  - `service_preflight`（session 级）：执行前先探活前端 + `GET /api/health`，**快速失败**并给出启动指引；前端端口被占用时自动探测 5173/5174 回退切换。
  - `driver` fixture（function 级）：读取 `--browser` 覆盖配置，创建驱动、打开首页、用例结束 `quit`。
  - `pytest_runtest_makereport` hook：**失败收敛层**——不看异常类型、不做业务分支，统一把 ①异常链全文 ②元素级截图（沿链捞取）③用例级现场截图 收拢进 allure 报告；取证自身失败只降级为 warning，**绝不掩盖原始失败**。

#### ⑦ 工具层 `util/` —— 横切能力

| 模块 | 作用 | 设计目的 |
| --- | --- | --- |
| `driver_factory.py` | 五浏览器统一创建（chrome/edge/firefox/chromium/safari） | 工厂 + 别名归一（360/QQ → chromium）；`binary_path` 支持国产浏览器；沙箱参数仅 Linux 注入；开启 performance 日志为 CDP 取证前置 |
| `scenario_support.py` | 路由直达、结果区轮询断言、服务预检、端口回退 | 「操作结果区」是全局统一断言点：业务失败码 HTTP 仍为 200、ElMessage 会自动消失，只有日志区稳定可读 |
| `api_client.py` | `requests.Session` 直连后端 | 造数 / 数据准备 / 兜底断言，绕过页面缩短链路 |
| `sqlite_source.py` | 被测 SQLite **只读**直读 | I-18/E-03 的库侧证据源；表白名单 + 参数化查询，杜绝注入面；库路径由被测接口动态返回，不写死 |
| `amount_util.py` | 金额文本 → `Decimal`（¥/千分位/括号负数），容差比较，分→元换算 | 金融断言纪律：禁止 float 直接相等；一分钱容差 |
| `digest_util.py` | SHA-256 摘要独立复算 | E-01 断言点从「明文相等」改为「摘要相等」，脚本侧复算不依赖浏览器 Web Crypto |
| `network_recorder.py` | CDP Network 域抓真实请求/响应体 | 页面报文区是前端自证不可信；仅 Chromium 支持，其余浏览器**自动降级**不失败 |
| `screenshot_util.py` | 截图命名与路径管理 | 文件名清洗非法字符，时间戳防覆盖 |
| `allure_compat.py` | allure 兼容层 | allure 未安装时全部降级为日志/无操作，用例永不受报告组件影响 |
| `read_ini.py` | INI 解析 | 相对路径归一 + 缺 Section/key 的明确报错 |

#### ⑧ 日志层 `log/user_log.py`

全局单例 Logger：控制台 + `TimedRotatingFileHandler` 按天滚动（保留 30 天），配合 `pytest.ini` 的 `log_cli` 实现执行过程实时可见。

#### ⑨ 入口层 `run_tests.py` + 根 `conftest.py`

- 四种模式：all / smoke（marker）/ regression（marker）/ allure（出结果 + 调 allure CLI 渲染 HTML）。
- `--browser` 选项注册在**根** conftest（pytest 解析期根 conftest 必先加载，子目录 conftest 未必），读取在使用处——这是 pytest 选项注册的典型坑的解法。

### 1.4 架构设计的三条主线

1. **配置与代码分离**：元素定位（INI）、运行参数（YAML）全部外置，代码零硬编码定位串。
2. **断言源可信分级**：页面可见内容 ≠ 可信断言源。稳定断言点依次是：「操作结果」日志区 → 服务端 API → SQLite 库 → CDP 网络层，页面 DOM 仅作辅助。
3. **可降级设计**：allure、CDP 网络取证、performance 日志、JS 点击兜底——增强能力失效时一律降级而非失败，保证用例在任何浏览器/环境下核心断言依然成立。

---

## 第二部分：数据流向（按业务流程）

### 2.1 主流程：一次用例的完整生命周期

```
run_tests.py --mode all
   │  组装 pytest 命令（mode → marker / alluredir）
   ▼
pytest 加载：根 conftest 注册 --browser → case/conftest
   │
   ▼
[session] service_preflight
   │  Config 读 settings.yaml → resolve_base_url() 探测 5173/5174 回退
   │  → GET 前端首页 + GET {api}/api/health → 不可达则 RuntimeError 快速失败
   ▼
[function] driver fixture
   │  --browser 覆盖 settings.yaml browser.type → DriverFactory 别名归一
   │  → 按浏览器分支创建（驱动路径优先 driver_path，其次 webdriver-manager）
   │  → 注入下载目录 prefs / performance 日志 → driver.get(base_url)
   ▼
用例 test_xxx(driver)
   │  open_scenario(driver, "/i/01")：直达路由 + 等页面标题出现
   ▼
business.run_xxx(...)
   │  biz_step("步骤名", **上下文)：allure step + 调用栈推断场景码
   ▼
handle 场景操作
   │  self.loc(key) → FindElement：场景码→INI→by>value→(By,value)（双缓存）
   │  → WebDriverWaitCommon：显式等待 → click/fill/js_fill
   │  → action_support：iframe/窗口/Shadow DOM/弹窗等平台动作
   ▼
被测页面执行 → 写入底部「操作结果」日志区
   ▼
断言（三选一，按可信级别）
   │  a. assert_result_contains：轮询日志区关键字（主断言）
   │  b. ApiClient 直连后端比对（兜底/造数验证）
   │  c. SqliteSource 只读直读库 + amount_util 清洗比对（I-18/E-03）
   ▼
通过 → driver.quit()
失败 → pytest_runtest_makereport 收敛层：
   │  ① format_exception_chain(异常链) → allure 文本附件
   │  ② find_in_chain 捞元素级截图 → allure PNG
   │  ③ ScreenshotUtil 拍用例现场 → allure PNG
   ▼
allure 模式：allure generate 渲染 HTML 报告
```

### 2.2 业务流程一：I-18 页面数字 ↔ 数据库一致性核对

```
用例开始 → POST /api/dbconsistency/reset（重建落库，保证可反复执行）
   │
   ├─【静态全量核对】
   │   页面侧：翻页收集全量明细（每页 5 条 × N 页）→ parse_amount 清洗（¥/千分位/括号负数）
   │   库侧：  /api/dbconsistency/db/meta 拿库路径 → SqliteSource 只读直读 settle_detail
   │   脚本侧：cents_to_yuan(分→元) 统一单位 → 逐条容差比对
   │   特殊行：NULL（未清算「—」）/ 负数（括号）/ 汇总漂移（bill 汇总字段 ≠ detail 求和）
   │
   └─【业务闭环核对】（核心）
       按角色从库中挑样本（勾稽一致的结算单）
       → 页面调整明细金额 ±delta → wait_db_equals 轮询等写库（约 0.6s 延迟）
       → 断言：明细已落库 + 页面显示一致 + 汇总字段【不回写】（页面汇总不变）
       → 点击「重算汇总」→ 汇总字段按明细求和回写 → 页面汇总变化
       → 收口断言：页面「结算单汇总金额合计」== Σ settle_bill.total_amount_cents（库）
       → 且 变化量 == 调整增量 delta
用例结束 → 再次 reset 复位
```

### 2.3 业务流程二：E-01 传输加密的多源断言

```
open_scenario("/e/01")
   │  公钥是异步资源（0.3~0.8s）：先等「密钥已就绪」文案（指纹先于状态标签更新）
   ▼
NetworkRecorder.start()（CDP Network 域，仅 Chromium；失败自动降级）
   ▼
页面提交加密表单
   │  RSA-OAEP 随机填充 → 每次密文不同 → 禁止密文相等断言
   ▼
三方摘要互校（SHA-256 前 16 位大写）
   │  ① 页面 #local-digest（前端 Web Crypto 算）
   │  ② 页面/接口 serverDigest（服务端解密后算）
   │  ③ 脚本 digest_util.password_digest(明文) 独立复算
   ▼
网络层取证（增强项）
   │  rec.try_wait_record("/api/crypto/login/encrypted")
   │  → 真实请求体无明文、响应体无 revealedPassword
   │  → 非 Chromium 浏览器跳过，接口层兜底，不影响通过
   ▼
明文通道对照：提交明文 → 服务端拒绝 → 断言摘要区被清空（不残留上一轮结果）
```

### 2.4 失败取证流（异常链视角）

```
WebDriverWaitCommon 等待超时
   │  当场截图 → raise ElementNotFoundError(定位器, 截图路径)
   ▼                        （第 1 层：技术根因，自带证据）
handle 断言未达成 → AssertionError
   ▼
business biz_step 捕获 AssertionError
   │  raise BusinessError([场景码] 步骤未达成, 上下文) from exc
   ▼                        （第 2 层：领域异常，from 挂链；链恒为 2 层）
case/conftest pytest_runtest_makereport
   │  不看类型、不做分支：异常链全文 + 链上截图 + 现场截图 → allure
   ▼
报告归档：一条链讲清「哪个场景哪一步、哪个元素、当时页面长什么样」
```

---

## 第三部分：面试要点与实战问题

### 3.1 架构设计类（必问）

**Q1：框架分几层？为什么这么分？**
六层 + 横切：`case → business → handle → base(定位) + common(等待)`，util/config/log 横切。核心动机是**变化隔离**：前端改样式只动 INI（定位层），业务改流程只动 business（业务层），Selenium API 变化只动 common/handle（操作层），用例层只关心「打开哪个场景、断言什么关键字」。单向依赖保证任何一层可独立替换（例如 network_recorder 内部将来从 CDP 换 BiDi，用例零改动）。

**Q2：元素定位怎么管理的？为什么用 INI 而不是 PO 类属性/JSON/YAML？**
场景码注册器模式：场景码（I01）→ 分组 INI 的同名 Section → `key=by>value` 解析为 `(By, value)`，双级缓存。选 INI 因为：一key一行可读性最好、无嵌套结构、configparser 标准库零依赖、与参考工程语义一致便于团队迁移。本质是把 PageObject 的「定位器仓库」从代码挪到配置，改动免改代码、免重跑单测。

**Q3：PO 模式在你这里怎么体现的？**
三层拆分：`handle` = 经典 PageObject（元素级操作），`business` = 业务流程对象（步骤编排 + 打标），`case` = 纯断言。比单层 PO 多出的 business 层解决「多个用例复用同一段业务流程」的重复代码问题，也是 allure 步骤报告与异常打标的挂载点。

**Q4：等待机制怎么设计的？隐式等待为什么设为 0？**
全部显式等待（`WebDriverWait` + EC 三档：presence/visibility/clickable）。`implicit_wait: 0` 因为隐式等待与显式等待混用会造成等待时间不可预期叠加（Selenium 官方反模式）；所有等待点必须可解释、可调参。对非元素类条件（日志区关键字、导出任务完成、写库就绪）用轮询封装（`wait_result_contains` / `wait_db_equals`）。

**Q5：失败怎么定位的？**
三级取证：① 元素级——等待超时**当场**截图并挂进 `ElementNotFoundError`；② 业务级——`biz_step` 把 AssertionError 包装为带场景码/步骤/入参的 `BusinessError` 并 `raise from` 挂链；③ 用例级——pytest hook 统一收敛异常链全文 + 链上截图 + 现场截图进 allure。约定**异常链恒为 2 层**，防止层层翻译把根因埋掉。

### 3.2 Selenium 高频技术点

**Q6：StaleElementReferenceException 怎么处理？**（I-03）
根因：SPA 整表重建后旧元素引用失效。解法：不缓存元素对象，每次操作重新定位（本框架 loc() 每次从缓存取定位串再 find_element）；确实持有了元素的，捕获异常后重新定位重试。框架层面「定位器缓存、元素不缓存」是关键设计。

**Q7：元素不可交互/点击被拦截怎么破？**（I-01/I-02）
先等 `element_to_be_clickable` 而非仅 presence；遮罩场景等遮罩 `invisibility` 后再操作；滚动到可视区 `scrollIntoView({block:'center'})`；最后手段 JS 点击兜底（`click_params` 已内置自动降级）。注意 JS 点击绕过真实用户事件，能不用就不用——兜底而非首选。

**Q8：iframe / Shadow DOM 怎么处理？**（I-04/I-05）
iframe：`switch_to.frame` 逐层穿透，完事 `switch_to.default_content()` 回主文档（双层 iframe 必须逐层进、逐层出）。Shadow DOM：Selenium 4 的 `element.shadow_root` 取 ShadowRoot 再 find_element，CSS 选择器无法穿透 shadow boundary。

**Q9：Vue/React 受控输入框 send_keys 不生效怎么办？**（I-16、C-01）
根因：框架监听 input/change 事件做状态同步，`element.clear()+send_keys` 在受控组件上可能残留旧值或不触发绑定。解法 `js_fill`：用原生 value setter 写值（`Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set`）再手动 `dispatchEvent(new Event('input',{bubbles:true}))`。

**Q10：多窗口怎么切换？**（M-01~M-03）
操作前记录 `window_handles` 快照，`wait_new_window` 等句柄数增加，切到新句柄操作，完事切回。OAuth 小窗场景要等「自动回传并关闭」：轮询句柄数回落再断言主窗口状态。非用户手势的 `window.open` 会被浏览器拦截（M-04），要保留默认弹窗策略复现并断言计数。

**Q11：文件下载/上传怎么验证？**（I-10/W-03）
下载：Chromium 用 prefs `download.default_directory`、Firefox 用 `browser.download.dir + neverAsk.saveToDisk` 静默落指定目录，断言产物文件存在（不点系统弹窗）。上传：直接对 `<input type=file>` `send_keys(绝对路径)`，绕过系统文件选择器。

**Q12：原生 alert/confirm/prompt 与日期控件？**（I-11/C-01）
`driver.switch_to.alert` 的 accept/dismiss/send_keys。原生 `date/datetime-local` 控件不走 send_keys 逐字输入（各浏览器行为差异大），统一走 `js_fill` 写 value + 派发事件。

### 3.3 数据与断言类（本项目特色）

**Q13：金额断言为什么不能用 float？**
浮点求和有尾差（0.1+0.2≠0.3）。本项目纪律：页面文本先 `parse_amount` 清洗（剥 ¥/千分位/括号负数/文案前缀）成 `Decimal`，比较用一分钱容差（`amount_equal`，tolerance=0.005）；库侧金额单位是「分」，先 `cents_to_yuan` 统一单位再比。NULL（未清算）与 0 元语义不同，`None` 全程保留不参与求和。

**Q14：页面数字和数据库核对怎么做才不脆弱？**（I-18）
两条原则：① **不写死任何期望值**——条数、页数、期望金额全部从库动态推导（`ceil(总数/页大小)==页数` 互推校验），样本按「角色」挑选（NULL 行/负数行/勾稽一致单）；② **业务闭环驱动**——不做静态快照比对，而是「调整金额 → 重算汇总 → 页面变化量==调整增量 且 页面==库求和」，模拟真实业务操作链路。写库有约 0.6s 延迟，必须轮询等待而非立即读。

**Q15：加密场景为什么不能断言密文？**（E-01~E-04）
OAEP/AES-GCM 都有随机填充/随机 IV，同一明文每次密文不同——密文相等断言必败。正确姿势：断言「语义等价物」——服务端解密结果的 SHA-256 摘要（脚本 hashlib 独立复算，三方互校）；「同一明文两次提交密文不同」反过来证明随机性。且**页面 DOM 是前端自证不可信**，真实报文用 CDP Network 域抓浏览器网络栈取证。解密成功 ≠ 验签通过（E-04 时间戳过期 2001 与签名篡改 2002 要分开断言）。

**Q16：断言点为什么统一在「操作结果」日志区？**
被测系统业务失败码（1001/2001…）HTTP 仍返回 200，requests 层无感；失败提示走 ElMessage 会自动消失，截图时机不可控。只有底部日志区是累积、稳定、可轮询的。推而广之：**UI 断言要选「稳定、累积、语义化」的锚点**，而不是 toast/弹窗这类瞬态元素。

### 3.4 工程化类

**Q17：多浏览器怎么支持的？**
工厂模式 + 策略分支：`DriverFactory.create_driver` 按类型分发五个创建函数；360/QQ 等国产浏览器别名归一为 chromium，用 ChromeDriver + `binary_path` 指可执行文件（驱动主版本需与其内核匹配，生产建议显式 `driver_path`）；Safari 仅 macOS 且需 `safaridriver --enable`，非 mac 明确报 `ConfigError`；沙箱参数仅 Linux 注入。命令行 `--browser` 覆盖 YAML 配置，同一套用例形成浏览器执行矩阵。

**Q18：能力降级怎么做的？举三个例子。**
① allure 未安装 → `allure_compat` 全部降级为日志，用例照常跑；② CDP 仅 Chromium → Firefox/Safari 下 NetworkRecorder `start()` 返回 False，用例跳过网络层断言改接口层兜底；③ performance 日志缓冲有副作用 → 环境变量 `UIEVENT_DISABLE_PERF_LOG=1` 一键关闭。原则：**增强能力永远不作为唯一断言源**。

**Q19：稳定性治理还做了什么？**
会话级服务预检快速失败（避免 37 个用例挨个超时）；前端端口 5173/5174 自动探测回退（Vite 端口顺延场景）；W-05 不稳定接口按指数/定频重试到成功；截图命名清洗非法字符 + 时间戳防覆盖；日志按天滚动 30 天；取证代码自身 try 兜底不掩盖原始失败。

**Q20：这套框架怎么迁移到别的项目？**
换 `settings.yaml`（地址/浏览器）+ 重写 6 个 INI（元素定位）+ 按场景写 handle/business/case，框架层（base/common/util）零改动。若换技术栈（Playwright/BiDi），只需替换 `webdriver_wait_common` 与 `network_recorder` 的后端实现。

### 3.5 实际项目中踩过的坑（问题清单）

| # | 问题现象 | 根因 | 本项目的解法 |
| --- | --- | --- | --- |
| 1 | 元素定位到但点不动 | 遮罩未消失/折叠未展开/disabled | 等 `clickable` + 等遮罩消失 + 前置状态就绪，JS 点击仅兜底 |
| 2 | 脚本时好时坏 | StaleElement：SPA 重建 DOM 后用了旧引用 | 定位器缓存、元素不缓存，操作前重新定位 |
| 3 | Vue 输入框值没进去/旧值残留 | 受控组件需 input 事件同步 v-model | `js_fill`：原生 setter + dispatchEvent |
| 4 | 金额断言偶发差 0.01 | float 尾差 + 千分位/括号负数未清洗 | Decimal + 一分钱容差 + 单位统一（分→元） |
| 5 | 保存后立刻读库读不到 | 写库异步（约 0.6s） | `wait_db_equals` 轮询，杜绝固定 sleep |
| 6 | 断言 ElMessage 时灵时不灵 | toast 自动消失，时机不可控 | 断言点改到底部累积日志区 |
| 7 | 密文断言永远失败 | OAEP/GCM 随机填充，密文每次不同 | 改断言 SHA-256 摘要；密文不同反证随机性 |
| 8 | 页面显示「已加密」但报文是明文 | 页面 DOM 是前端自证 | CDP Network 域抓真实请求/响应体取证 |
| 9 | 换 Firefox 用例全挂 | CDP 仅 Chromium | 能力探测 + 自动降级 + 接口层兜底 |
| 10 | 分页数据对不上 | 每页只渲染 5 条，漏收后续页 | 翻页收集全量 + `ceil(总数/页大小)==页数` 互校验 |
| 11 | 汇总和明细对不上 | 业务库汇总字段是独立列，天然漂移 | 两类数据源分别取、分别比；重算后收口比对 |
| 12 | 公钥就绪了但提交仍失败 | 指纹先于状态标签更新，等错锚点 | 等「密钥已就绪」文案而非 DOM 收敛 |
| 13 | 37 个用例跑完才发现服务没起 | 无前置检查 | session 级预检 `/api/health` 快速失败 |
| 14 | 换个机器端口不对全挂 | Vite 端口被占顺延 5174 | 预检自动探测 5173/5174 并告警切换 |
| 15 | `--browser` 参数不生效 | 选项注册在子目录 conftest，解析期未加载 | 注册放根 conftest，使用留在 fixture |
| 16 | 下载验证依赖系统弹窗 | 浏览器下载弹窗自动化无法操作 | prefs 静默下载到项目目录，断言文件存在 |
| 17 | 报告组件缺失导致用例失败 | allure 强依赖 | 兼容层降级：报告只是增强，不是链路 |
| 18 | X-04 用例稳定失败 | **被测系统后端缺陷**（`POST /api/seed/new` 500，旧进程未重启） | 自动化侧如实报告，不规避；定位为被测方问题并给出复现证据 |

### 3.6 红线与职业判断（加分项）

- **不绕过被测系统安全机制**：验证码用后端万能码不接 OCR；webdriver 特征检测只断言不注入反检测参数；弹窗拦截保留默认策略复现。自动化是验证手段，不是对抗手段。
- **缺陷归属判断**：X-04 稳定失败时，通过「直连后端 vs 经前端代理均 500、同模块 GET 正常」交叉取证，定位为被测后端旧进程问题而非脚本问题——**用证据说话，不替被测系统兜底，也不让脚本背锅**。
- **测试数据自洁**：I-18 用例开头结尾都调 reset 重建落库，可反复执行、无顺序依赖、无脏数据。

---

*文档生成依据：当前代码库实读（config/base/common/util/handle/business/case 全部模块），与代码同步。*
