# coding=utf-8
"""case 级 Pytest 配置：基础地址、浏览器 driver、会话级服务预检、失败自动取证。"""
from __future__ import annotations

import pytest

from common.exceptions import find_in_chain, format_exception_chain
from config.settings import Config
from log.user_log import get_logger
from util import allure_compat
from util.driver_factory import DriverFactory
from util.screenshot_util import ScreenshotUtil
from util.scenario_support import get_base_url, preflight_services

logger = get_logger()


@pytest.fixture(scope="session", autouse=True)
def service_preflight():
    """全量执行前先校验被测前后端可用，快速失败并给出启动指引。"""
    preflight_services()
    yield


@pytest.fixture(scope="function")
def driver(request):
    """
    统一浏览器入口：启动浏览器并打开被测前端首页根地址。
    每个场景用例内部通过 open_scenario 再直达 /i/01 等场景路由。
    浏览器类型取 pytest --browser，未传则回落 settings.yaml 的 browser.type。
    """
    browser_type = request.config.getoption("--browser")
    d = DriverFactory.create_driver(browser_type=browser_type)
    d.get(get_base_url())
    yield d
    d.quit()


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """
    用例失败自动取证并归档：setup/call 失败时捕获异常链与 driver 现场。

    架构第 ⑤ 层（收敛层）：**不看异常类型、不做业务分支**，只负责把散落
    在各层的证据收拢成一条链并送进报告：
      1. 异常链全文（__cause__ 展开，含业务上下文 / 定位器 / 截图路径）；
      2. 元素级截图（ElementNotFoundError 抛出瞬间已拍，沿链捞取）；
      3. 用例级截图（本 hook 拍，pytest 判定失败之后）。

    取证任一步失败只降级为 warning，绝不掩盖原始失败。
    """
    outcome = yield
    rep = outcome.get_result()

    if rep.when not in ("setup", "call") or not rep.failed:
        return

    exc_value = call.excinfo.value if getattr(call, "excinfo", None) else None

    # 1) 异常链全文：不依赖 driver，浏览器都没起来时也能留证
    if exc_value is not None:
        allure_compat.attach_text("失败异常链", format_exception_chain(exc_value))

    if "driver" not in item.fixturenames:
        return
    drv = item.funcargs.get("driver")
    if not drv:
        return

    # 2) 元素级截图：抛出瞬间拍下的原始现场，沿异常链捞取
    element_shot = find_in_chain(exc_value, "screenshot_path")
    if element_shot:
        allure_compat.attach_png("元素超时现场", element_shot)

    # 3) 用例级现场截图：判定失败后的最终屏幕状态
    try:
        on_failure = bool(Config().get("screenshot.on_failure", True))
    except Exception:
        on_failure = True
    if not on_failure:
        return

    try:
        screenshot_path = ScreenshotUtil.capture(drv, item.name)
    except Exception as capture_error:
        logger.warning("用例失败截图失败（不掩盖原始失败）: %s", capture_error)
        return

    print(f"\n[全局拦截] 用例失败，已保存崩溃现场截图: {screenshot_path}")
    allure_compat.attach_png("用例失败现场", screenshot_path)
