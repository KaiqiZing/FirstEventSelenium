# Contributing

Thanks for your interest in contributing to **FirstEventSelenium**! Contributions are welcome in the form of bug reports, new scenarios, browser compatibility fixes, and documentation improvements.

[English](#english) | [简体中文](#简体中文)

---

## English

### How to contribute

1. **Fork & branch**: fork the repository and create a feature branch, e.g. `feat/i19-scenario` or `fix/safari-driver`.
2. **Set up the environment**: follow the [README](README.md) — Python 3.11+, `pip install -r requirements.txt`, and start the system under test (frontend `:5174`, backend `:5000`).
3. **Make your change**:
   - New scenarios follow the existing layering: locator goes to `config/*Element.ini`, element operations to `handle/`, orchestration to `business/`, the pytest case to `case/`, with an `allure` step description.
   - No hardcoded amounts, IDs, or paths — derive expected values from dynamic data (see the I-18 design principles in the README).
4. **Verify**: run at least the affected group plus the smoke suite, on Chrome:

   ```bash
   python -m pytest case/test_<group>.py -q
   python run_tests.py --mode smoke
   ```

5. **Commit & PR**: use clear commit messages (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`). In the PR description, state which scenarios were run and on which browser/OS.

### Ground rules

- **Respect the red lines**: never bypass the system-under-test restrictions (CAPTCHA OCR, webdriver-feature spoofing, popup-policy changes, etc.). See the "Non-Bypass Red Lines" section of the README.
- **No secrets in code**: the project must stay free of real credentials, private IPs, or internal URLs. Use localhost and demo data only. Do not commit logs, screenshots, or downloads (already covered by `.gitignore`).
- **Do not modify the system under test**: this suite is physically isolated from `FirstSeleniumUIEvent`; issues found there should be reported, not patched here.
- Keep the README (English) and README.zh-CN.md (Chinese) in sync when behavior or usage changes.

### Reporting bugs

Include: OS + Python version, browser + driver version, the failing command, the relevant pytest output / Allure report, and (if applicable) the failure screenshot from `logs/` — attached, not committed.

---

## 简体中文

### 参与方式

1. **Fork & 分支**：fork 本仓库并新建功能分支，例如 `feat/i19-scenario`、`fix/safari-driver`。
2. **环境准备**：按 [README.zh-CN.md](README.zh-CN.md) 操作 —— Python 3.11+，`pip install -r requirements.txt`，并启动被测系统（前端 `:5174`、后端 `:5000`）。
3. **编写改动**：
   - 新场景遵循既有分层：定位器进 `config/*Element.ini`，元素操作进 `handle/`，业务组合进 `business/`，用例进 `case/`，并补充 `allure` 步骤描述。
   - 不写死金额、编号、路径 —— 期望值一律从动态数据推导（见 README 中 I-18 的设计原则）。
4. **验证**：至少运行受影响分组与冒烟套件（Chrome）：

   ```bash
   python -m pytest case/test_<分组>.py -q
   python run_tests.py --mode smoke
   ```

5. **提交 & PR**：使用清晰的提交信息（`feat:`、`fix:`、`docs:`、`refactor:`、`test:`）。PR 描述中注明实际运行了哪些场景、在哪个浏览器/系统上验证。

### 基本守则

- **遵守红线**：不绕过被测系统限制（验证码 OCR、webdriver 特征伪装、修改弹窗策略等），见 README「红线遵守说明」。
- **代码中不含敏感信息**：保持零真实凭据、零内网 IP、零内部域名，只使用 localhost 与演示数据；不要提交日志、截图、下载产物（`.gitignore` 已覆盖）。
- **不修改被测系统**：本工程与 `FirstSeleniumUIEvent` 物理隔离；发现被测系统缺陷应反馈报告，而不是在本仓库打补丁。
- 行为或用法变更时，同步维护英文 README 与中文 README.zh-CN.md。

### 反馈缺陷

请附上：操作系统与 Python 版本、浏览器与驱动版本、失败命令、相关 pytest 输出 / Allure 报告，以及（如有）`logs/` 下的失败截图 —— 以附件形式提供，勿直接提交进仓库。
