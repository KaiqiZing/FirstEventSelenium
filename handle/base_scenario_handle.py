"""场景句柄基类：统一封装元素解析 / 显式等待 / 日志 / 结果区断言。

每个场景的 handle 继承本类并传入场景码（module，如 "I01"），
元素 key 统一通过 fd.get_locator(key, module) 从对应分组 INI 读取。
"""
from __future__ import annotations

from typing import Any

from base.find_element import FindElement
from common.webdriver_wait_common import WebDriverWaitCommon
from handle.action_support import set_input_value
from log.user_log import get_logger
from util.scenario_support import (
    assert_result_contains,
    result_logs,
    wait_result_contains,
)


class BaseScenarioHandle:
    def __init__(self, driver, module: str, timeout: int | None = None):
        self.driver = driver
        self.module = str(module).upper()
        self.logger = get_logger()
        self.fd = FindElement(driver)
        self.wait = WebDriverWaitCommon(driver, timeout)

    # ---------------- 定位器 ---------------- #
    def loc(self, key: str) -> tuple:
        """返回 (By, value) 元组定位器。"""
        return self.fd.get_locator(key, self.module)

    def xpath(self, key: str) -> str:
        """返回 XPath 字符串（用于拼接复合 XPath）。"""
        return self.fd.get_text(key, self.module)

    # ---------------- 等待 ---------------- #
    def visible(self, key: str):
        return self.wait.wait_for_visible(self.loc(key))

    def presence(self, key: str):
        return self.wait.wait_for_presence(self.loc(key))

    def clickable(self, key: str):
        return self.wait.wait_for_clickable(self.loc(key))

    # ---------------- 操作 ---------------- #
    def click(self, key: str, force_js: bool = False):
        return self.wait.click_params(self.loc(key), force_js=force_js)

    def fill(self, key: str, value: str, clear_first: bool = True):
        return self.wait.send_keys_params(self.loc(key), value, clear_first=clear_first)

    def js_fill(self, key: str, value: str):
        """用原生 value setter 写入并派发 input/change 事件，确保 Vue v-model 同步。

        适用于 el-input 内层 input 与原生 date/time/datetime-local 控件，
        避免 element.clear()+send_keys 在受控组件上残留旧值或未触发绑定的问题。
        """
        element = self.wait.wait_for_visible(self.loc(key))
        element.clear()
        set_input_value(self.driver, element, value)
        return element

    def text_of(self, key: str) -> str:
        return self.wait.get_text(self.loc(key))

    def attr_of(self, key: str, attr: str) -> str | None:
        return self.wait.get_attribute(self.loc(key), attr)

    def scroll_to(self, key: str):
        return self.wait.scroll_to_element(self.loc(key))

    # ---------------- 结果区断言 ---------------- #
    def logs(self) -> list[str]:
        return result_logs(self.driver)

    def wait_log(self, keyword: str, timeout: int | None = None) -> bool:
        return wait_result_contains(self.driver, keyword, timeout or self.wait.timeout)

    def assert_log(self, keyword: str, timeout: int | None = None, extra: str = "") -> None:
        assert_result_contains(self.driver, keyword, timeout or self.wait.timeout, extra)
