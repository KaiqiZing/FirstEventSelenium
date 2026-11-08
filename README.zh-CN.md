# FirstEventSelenium

针对被测平台 **FirstSeleniumUIEvent**（Vue 3 + Element Plus 前端 `:5173`，Flask 后端 `:5050`）的**独立、自包含** Selenium 自动化工程。

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![pytest](https://img.shields.io/badge/tested%20with-pytest-green.svg)](https://docs.pytest.org/)

[English](README.md) | 简体中文

---

架构复刻自 `FiccAccountSelenium` 的分层风格，但代码与被测系统、参考工程**物理隔离**，`import` 链完全自洽，不修改 `FirstSeleniumUIEvent` 与 `FiccAccountSelenium` 的任何现有文件。

---

## 一、分层结构

```
FirstEventSelenium/
├── config/                 # 配置层
│   ├── settings.yaml       # base_url / timeout / 浏览器参数 / 下载目录 / 截图路径
│   └── *Element.ini        # 6 个分组文件，37 个场景 section（[module] key=by>value）
├── base/
│   └── find_element.py     # 场景码 -> (INI, Section) 映射 + by>value 解析与缓存
├── common/
│   ├── exceptions.py       # ElementNotFoundError 等
│   └── webdriver_wait_common.py  # 显式等待与元素操作封装
├── util/
│   ├── driver_factory.py   # Chrome 驱动创建（含下载目录 prefs）
│   ├── screenshot_util.py  # 失败截图
│   ├── read_ini.py         # INI 解析
│   ├── api_client.py       # requests.Session 直连后端辅助
│   ├── scenario_support.py # open_scenario / result_logs / wait_result_contains / preflight_services
│   ├── amount_util.py      # 金额文本 -> Decimal 清洗（¥/千分位/括号负数）、分->元换算、容差比较
│   ├── sqlite_source.py    # SQLite 落库只读直连（I-18 页面数字 vs 数据库；E-03 密文库 vs 页面明文）
│   └── allure_compat.py    # allure 装饰器兼容封装
├── handle/
│   ├── base_scenario_handle.py  # 场景操作基类（定位/等待/输入/结果区断言）
│   ├── action_support.py        # 跨场景平台动作（iframe/窗口/Shadow DOM/弹窗/拖拽/上传/富文本/懒加载）
│   └── *_handles.py             # 各组场景元素级操作流
├── business/
│   └── *_business.py      # 按组业务组合（allure.step 包装，必要时叠加 API/重试）
├── case/
│   ├── conftest.py         # driver fixture / 会话级健康预检 / 失败自动截图
│   └── test_*.py          # 37 个用例，统一断言页面底部「操作结果」区
├── run_tests.py           # 多模式运行入口
├── requirements.txt
└── pytest.ini
```

数据流：`case(pytest) → business(业务组合) → handle(场景操作) → base(元素解析) + common(等待)`，`util/driver_factory + screenshot + api_client + scenario_support` 为横切支撑。

---

## 二、环境准备

### 1. 被测系统（由使用者手工启动）

```bash
# 前端（Vite 已代理 /api -> 5000，同源无需跨域）
cd FirstSeleniumUIEvent/frontend && npm install && npm run dev   # :5174

# 后端（内存态数据，重启复位）
cd FirstSeleniumUIEvent/backend && python app.py                 # 127.0.0.1:5000
```

> 本工程不启动被测服务，也不修改被测代码。若被测服务未启动，执行时将给出明确的失败提示（会话级健康预检 `GET /api/health` 与前端可达性）。
>
> 前端地址默认 `http://localhost:5174`（`settings.yaml env.*.base_url`）。Vite 端口被占用时会顺延，因此预检失败会自动探测 `5173 / 5174` 并告警切换，无需改配置。

### 2. 运行环境

- Python 3.11+（本工程在 Python 3.13 下验证）
- 浏览器驱动推荐 `webdriver-manager` 自动适配（已随 `requirements.txt` 安装）

**支持的浏览器与系统**（`settings.yaml browser.type` 配置，`pytest --browser` 可覆盖）：

| 浏览器 | 系统 | 驱动方式 |
| --- | --- | --- |
| Chrome | Windows / macOS / Linux | ChromeDriver（webdriver-manager 自动适配） |
| Edge | Windows / macOS / Linux | EdgeDriver（webdriver-manager 自动适配） |
| Firefox | Windows / macOS / Linux | GeckoDriver（webdriver-manager 自动适配） |
| chromium（360 安全/极速、QQ、奇安信等） | 各平台 | ChromeDriver + `browser.binary_path` 指向浏览器可执行文件 |
| Safari | 仅 macOS | safaridriver（需先 `safaridriver --enable` 授权） |

> 沙箱类启动参数（`--no-sandbox` / `--disable-dev-shm-usage`）仅在 Linux（CI/Docker）下注入，
> Windows / macOS 下启动参数更干净；其余路径/驱动均按当前系统自动适配。

```bash
cd FirstEventSelenium
python -m venv .venv
.venv\Scripts\activate          # Windows（macOS/Linux 用 source .venv/bin/activate）
pip install -r requirements.txt
```

---

## 三、运行方式

### 全量运行

```bash
python run_tests.py --mode all
# 等价于
python -m pytest case/ -v
```

### 其它模式

```bash
python run_tests.py --mode smoke        # 冒烟：I-01 / I-02 / W-01（marker=smoke）
python run_tests.py --mode regression   # 回归（marker=regression）
python run_tests.py --mode allure       # 生成 allure 结果并渲染 HTML 报告
```

### 单场景 / 单组

```bash
python -m pytest case/test_interact.py -q          # 页面交互类
python -m pytest case/test_crypt.py -q             # 数据加密类（E-01~E-04）
python -m pytest case/test_window.py -q            # 多窗口类
python -m pytest "case/test_interact.py::test_i01_not_interactable" -q
python -m pytest case/ --tb=short -q               # 简略回溯
```

> 每个用例内部通过 `open_scenario(driver, "/i/01")` 直达对应路由，无需手工导航。

### 按浏览器执行矩阵（--browser）

同一套用例换浏览器复跑，浏览器类型经命令行覆盖 `settings.yaml` 的 `browser.type`：

```bash
python run_tests.py --mode smoke --browser chrome
python run_tests.py --mode smoke --browser edge
python run_tests.py --mode smoke --browser firefox
python run_tests.py --mode smoke --browser chromium      # 360/QQ 等：需在 settings.yaml 配好 binary_path
python -m pytest case/ -q --browser firefox              # 直接用 pytest 亦可
```

> `--browser` 取值：`chrome` / `edge` / `firefox` / `chromium` / `safari`；
> `360` / `qq` 等别名会自动归一为 `chromium`。
> 未传 `--browser` 时回落配置默认值，完全向后兼容（默认 `chrome`）。

---

## 四、场景覆盖清单（37 个）

### 页面交互类 `I-01 ~ I-18`（`case/test_interact.py`）

| 编号 | 场景 | 断言关键字（示意） |
| --- | --- | --- |
| I-01 | 元素不可交互 | 交接记录已保存 |
| I-02 | 点击被拦截（遮罩/固定头部） | 已保存 |
| I-03 | 元素引用失效（StaleElement） | 已刷新 |
| I-04 | iframe 嵌套定位 | 已提交 |
| I-05 | Shadow DOM 控件 | 已生效 |
| I-06 | 动态 ID / class | 已绑定 |
| I-07 | 原生 + 自绘双下拉 | 已选中 |
| I-08 | 悬浮菜单 | 已切换 |
| I-09 | 拖拽排序 | 已调整 |
| I-10 | 文件上传 | 上传成功 |
| I-11 | 原生 alert/confirm/prompt | 已完成 |
| I-12 | 富文本编辑 | 已发布 |
| I-13 | 渐入动画 | 已播放 |
| I-14 | 滚动懒加载 | 已加载全部 |
| I-15 | 坐标偏移容器 | 已获取 |
| I-16 | 受控输入 + 异步联想 | 联想已回填 |
| I-17 | 父子级金额勾稽（折叠 / 同名列 / 尾差） | 已展开全部父级结算单 / 重算完成 / 金额一致 |
| I-18 | 页面数字与数据库核对（分页 / 「分」单位 / 汇总漂移 / NULL / 陈旧读数） | 数据库已重建 / 明细已落库 / 汇总金额已按明细重算为 / 页面数据未自动刷新 |

#### I-18 一致性核对的实现方式

被测系统在 `backend/data/settlement.db` **真实落盘**（非纯内存），本工程用 `util/sqlite_source.py` 以只读方式直连该库，
把「库侧原始行」与「页面渲染数字」分别取出后逐一比对：

| 核对点 | 页面侧 | 数据库侧 | 脚本侧处理 |
| --- | --- | --- | --- |
| 单位 | `¥862,300.00`（元） | `amount_cents=86230000`（分） | `cents_to_yuan` 统一单位后再比 |
| 分页 | 每次只渲染 5 行 | 15 条明细全量 | `collect_all_details` 翻完 3 页取全量 |
| 汇总漂移 | 汇总卡取「结算单汇总字段」合计 | `settle_bill.total_amount_cents` ≠ `settle_detail` 求和 | 两类数据源分别取、分别比 |
| 未清算 | 显示「—」 | `amount_cents=NULL` | `amount_of` 返回 `None`，求和按 0 |
| 陈旧读数 | 快照时间不变 | 入账后已落库 | 先断言页面仍为旧值，再刷新后比对 |
| 负数格式 | `(¥98,000.00)` | `-9800000` | `parse_amount` 括号转负号 |
| 写库延迟 | 保存后立即返回 | 约 0.6s 后才可读 | `wait_db_equals` / `wait_db_changed` 轮询 |

库文件路径由被测接口 `/api/dbconsistency/db/meta` 返回，不写死绝对路径；用例开头与结尾都会调 `/api/dbconsistency/reset`
重建落库，可反复执行。

#### I-18 的两个设计原则

1. **不写死任何金额/条数**：样本与期望值全部来自动态数据

   | 内容 | 做法 |
   | --- | --- |
   | 明细条数 / 页数 / 每页行数 | 与库 `COUNT(*)` 和页面汇总卡互推，并校验「ceil(总数/页大小) == 页数」 |
   | 期望金额 | 一律 `cents_to_yuan(库中「分」)` 推导，页面侧只断言「相等 / 不等关系」 |
   | 特殊行样本 | 按**角色**从库中筛选：`ROLE_UNSETTLED`（NULL）、`ROLE_NEGATIVE`（负数）、`pick_detail_in_matched_bill`（勾稽一致的结算单） |
   | 记账账户 | 取页面资金账户首行账号（`account_numbers()[0]`），与服务端记账目标一致 |

   样例断言（无任何具体金额、任何具体编号）：

   ```python
   item_no, bill_no = h.pick_detail_in_matched_bill()
   for delta in (Decimal("100.00"), Decimal("-250.00")):      # 一增一减
       result = biz.run_i18_adjust_then_recap(item_no, bill_no, delta)
       assert amount_equal(result.after_summary, result.before_summary + delta)          # 变化量 == 调整增量
       assert amount_equal(result.after_summary, cents_to_yuan(result.handle.db_bill_sum_cents()))  # 页面 == 库
   ```

2. **以完整业务闭环驱动核对**：`调整明细金额 -> 重算汇总 -> 结算单汇总金额合计变化 -> 页面显示 ⇔ 数据库总额`

   - 调整后：明细落库且页面显示一致；**结算单汇总字段不回写**，页面汇总金额合计保持不变；
   - 重算汇总后：汇总字段按明细求和回写，页面「结算单汇总金额合计」发生变化；
   - 收口断言：变化后的页面金额，必须与数据库中 `settle_bill` 求和一致（这才是该场景的核心业务校验）。

   「静态全量核对」（逐条明细、汇总卡、资金账户、NULL、负数格式）作为前置口径校验，
   「业务闭环」（调整 ± 金额后重算）才是真正模拟业务人员操作的链路。

### 等待与响应类 `W-01 ~ W-05`（`case/test_wait.py`）

| 编号 | 场景 | 断言关键字（示意） |
| --- | --- | --- |
| W-01 | 慢接口 + loading 遮罩 | 数据已加载 |
| W-02 | SPA 无刷新路由切换 | 已切换 |
| W-03 | 10s 异步导出任务 | 导出完成 + 下载产物存在 |
| W-04 | 保存后落库竞态 | 已出现在列表 |
| W-05 | 不稳定接口容错重试 | 最终成功 |

### 多窗口与多标签 `M-01 ~ M-04`（`case/test_window.py`）

| 编号 | 场景 | 断言关键字（示意） |
| --- | --- | --- |
| M-01 | 新标签页打开 | 已打开新标签 |
| M-02 | OAuth 授权小窗自动回传并关闭 | 授权成功并自动关闭 |
| M-03 | 新窗口内嵌 iframe | 主档登记完成 |
| M-04 | 非用户手势 window.open 拦截计数 | 被拦截/成功 |

### 浏览器兼容类 `C-01 ~ C-02`（`case/test_compat.py`）

| 编号 | 场景 | 断言关键字（示意） |
| --- | --- | --- |
| C-01 | 原生日期时间控件 | 排期已提交 |
| C-02 | 运行环境信息核对 | 已采集当前浏览器环境信息 |

### 其他疑难类 `X-01 ~ X-04`（`case/test_misc.py`）

| 编号 | 场景 | 断言关键字（示意） |
| --- | --- | --- |
| X-01 | 图形验证码（万能码 1234） | 验证码校验通过 |
| X-02 | webdriver 特征检测（只读不绕过） | 环境校验完成 / 受限提示 |
| X-03 | 会话 Cookie 登录态 | 登录成功 / 已退出 |
| X-04 | 服务端造数自造自销 | 服务端已生成工单 |

### 数据加密类 `E-01 ~ E-04`（`case/test_crypt.py`）

| 编号 | 场景 | 断言关键字（示意） |
| --- | --- | --- |
| E-01 | 传输字段加密（RSA-OAEP，公钥异步签发，摘要比对） | 服务端解密成功 / 明文提交失败 / 加密提交失败 |
| E-02 | 敏感字段脱敏展示（掩码 + 限时查看 + 冷却） | 档案列表已刷新 / 已自动收起 / 查看…失败 |
| E-03 | 客户档案密文存储核对（AES-256-GCM + 多密钥版本） | 登记成功 / 同明文密文共 2 份 / 解密成功 / 解密失败 |
| E-04 | 接口报文加密 + 时间戳/签名校验 | 本地解密成功 / 签名校验通过 / 签名校验未通过 |

#### 加密类场景的统一断言口径

页面上能直接看到的**都不是**可信断言源，四个场景分别这样处理：

1. **E-01 传输加密**：DOM `value` 是明文、线上报文是密文，且 OAEP 随机填充导致**每次密文都不同**
   → 禁止拿密文做相等断言；另用「同一明文两次提交密文不同」反证随机性。
   被测系统已**不再回显明文口令**（`CRYPTO_ECHO_PLAINTEXT=False`），稳定断言点改为
   「服务端解密结果的**摘要**」（`serverDigest`，SHA-256 前 16 位大写）：脚本用 `hashlib`
   独立复算，与页面 `#local-digest` / `#server-digest` 三处互校，非安全上下文（无 Web Crypto、
   页面显示「未比对」）时退化为仅校验服务端侧摘要，不依赖浏览器能力。
   公钥是**异步资源**（0.3~0.8s），进页面先等指纹就绪再提交（指纹先于状态标签更新，
   须等「密钥已就绪」文案而非仅等 DOM 收敛）；密钥轮换后旧密文失效（1003）；
   明文通道提交后摘要区必须被清空（不得残留上一轮解密结果）。
   **网络层取证**：页面 `#request-body` 是前端自渲染的自证，因此额外用 CDP `Network` 域
   （`util/network_recorder.py`）抓取浏览器真实收发的请求体与响应体，证明「报文里确实没有
   明文、响应里确实没回显 `revealedPassword`」。仅 Chromium 内核支持，其余浏览器自动降级、
   改由接口层兜底，不影响用例通过；可设 `UIEVENT_DISABLE_PERF_LOG=1` 主动关闭。
2. **E-02 展示脱敏**：页面只有掩码，个别行 DOM 上还挂着 `data-raw` 明文（真实项目常见泄漏点）
   → 该属性只存在于个别行，属**脏路径**，主断言一律以 `GET /api/crypto/masked/raw` 全量明文为准；
   抽屉明文限时 5 秒可见并自动收起，同一条记录冷却期内重复申请返回 1002。
3. **E-03 密文存储**：页面是服务端解密结果、库里是 AES 密文 + 随机 IV + HMAC 摘要列
   → 直读 SQLite `cust_profile` 与 `/api/crypto/vault/db/query`，**按 `key_version` 解密后**再与页面明文比对；
   「未登记 NULL（页面「—」、接口 2003）」与「密钥已吊销（页面「解密失败」）」文案不同，分开断言；
   列表每页只有 5 条，必须翻页收集全量；同一明文重复登记密文必不相同，等值检索只能靠摘要列。
4. **E-04 报文加密**：接口返回整体密文，**解密成功 ≠ 校验通过**
   → 时间戳过期（2001）与签名被篡改（2002）分别断言，且这两种报文仍能正常解密渲染出 5 条明细；
   解密与验签必须基于**同一份报文**（接口每次都会生成新的随机 IV 与时间戳），
   因此从页面读取 `ts/sign/enc/iv`，再用服务端解密通道复算金额与页面千分位文本容差比对。

业务失败码（1001/1002/1003/2001/2002/2003）HTTP 仍为 200 且提示由 ElMessage 承载会自动消失，
故全部断言读页面底部「操作结果」日志区。

---

## 五、测试结果

在前后端均已启动的前提下，执行 `python -m pytest case/ -q`：

```
32 passed, 1 failed in ~5m30s
```

- **32 个场景通过**，覆盖 `I-01~I-18`、`W-01~W-05`、`M-01~M-04`、`C-01/C-02`、`X-01/X-02/X-03`；
  其中页面交互类 `I-01~I-18` 已在本轮实测 `18 passed in 3m00s`（含新增 I-18 页面数字与数据库核对）。
- **X-04（服务端造数自造自销）未通过**，属于**被测系统后端缺陷**，与自动化代码无关，详见下文。
- 上条统计不含本轮新增的数据加密类 `E-01~E-04`（`python -m pytest case/test_crypt.py -q` 单独统计）。

### X-04 已知阻塞说明

被测后端 `POST /api/seed/new` 稳定返回 **HTTP 500**：

- 直连 `http://127.0.0.1:5000/api/seed/new` 与经前端代理 `http://localhost:5174/api/seed/new` 均返回 500；
- 同文件的 `GET /api/seed/list` 正常（返回 `{"records": []}`）；
- 被测源码 `backend/api/slow_api.py::seed_new` 逻辑正常，判断**运行中的后端进程为旧代码 / 未重启**（服务为内存态，重启即复位）。

**建议**：重启被测后端进程（重新执行 `cd backend && python app.py`），使最新的 `slow_api.py` 生效后，再运行 `python -m pytest case/test_misc.py::test_x04_seed_data -q` 即可通过。

---

## 六、浏览器与系统兼容性

### 1. 支持矩阵

| 浏览器 | 平台 | 驱动方式 | 状态 |
| --- | --- | --- | --- |
| Chrome | Windows / macOS / Linux | ChromeDriver（webdriver-manager / Selenium Manager） | 已实现并回归 |
| Edge | Windows / macOS / Linux | EdgeDriver（webdriver-manager） | 已实现并回归（Windows） |
| Firefox | Windows / macOS / Linux | GeckoDriver（webdriver-manager） | 已实现并回归（Windows） |
| chromium（360 安全/极速、QQ、奇安信等） | 各平台 | ChromeDriver + `binary_path` | 已实现，需在装有对应浏览器的机器验证 |
| Safari | 仅 macOS | safaridriver | 已实现，需在 macOS 验证 |

### 2. 国产浏览器（360 / QQ / 奇安信等）用法

国产浏览器普遍基于 Chromium 内核，选 `chromium` 类型并用 `binary_path` 指向其可执行文件：

```yaml
browser:
  type: chromium
  binary_path: "C:\\Program Files (x86)\\360\\360se6\\Application\\360se.exe"   # 360 安全浏览器
  # binary_path: "C:\\Program Files (x86)\\360\\360Chrome\\Chrome\\Application\\360chrome.exe"  # 360 极速浏览器
  driver_path: ""   # 建议填写与浏览器内核版本匹配的 chromedriver（360 内核版本可能异于本机 Chrome）
```

> 360 各版本浏览器内核与 Chrome 主版本存在差异，用 `browser.driver_path` 显式指定匹配的
> chromedriver 最稳妥；直接跑也可先 `--browser 360`（别名自动归一 `chromium`）看启动日志。

### 3. Safari（仅 macOS）

- 首次需执行 `safaridriver --enable`，并在「系统设置 → 隐私与安全性 → 开发者工具」允许远程自动化；
- Safari 无 headless 概念，开启 `headless` 会被忽略并告警；
- 在 Windows / Linux 上选择 `safari` 会得到明确的 `ConfigError` 提示。

### 4. 验证边界

- Windows 本机已完成 chrome / edge / firefox 三浏览器回归；
- Safari 与 360 等国产浏览器需在装有对应浏览器（macOS / Windows 客户机）的环境按上文指引验证。

---

## 七、红线遵守说明

针对被测系统 README 明示的不可绕过/不可实现项，本工程**不做规避**，仅按页面允许方式断言可观测结果：

- **X-01 图形验证码**：使用后端万能码 `1234`，不接入 OCR。
- **X-02 / C-02 webdriver 特征检测**：仅执行校验并读取/断言校验结果，浏览器参数**不注入** `AutomationControlled` 等反自动化特征。
- **M-04 弹窗拦截**：保留浏览器默认弹窗策略以复现“被拦截”，并断言页面计数。
- **C-01 日期时间控件**：使用原生控件填入并提交。
- **I-15 坐标偏移容器**：只做“展开完整区域后点击”，并读取 rect / DPR。
- **W-03 导出下载**：校验浏览器下载目录产物是否存在。

---

## 贡献

欢迎贡献！提交 Issue 或 Pull Request 前，请先阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 许可证

本项目基于 [MIT License](LICENSE) 开源。
