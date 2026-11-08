"""通用 WebDriver 显式等待与元素操作封装（裁剪自参考工程并扩展）。"""
from __future__ import annotations

from typing import Any

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from common.exceptions import ElementNotFoundError
from log.user_log import get_logger
from util.screenshot_util import ScreenshotUtil

_DEFAULT_TIMEOUT = 10


def _load_timeout_from_config() -> int:
    try:
        from config.settings import Config

        return int(Config().get_env_config().get("timeout", _DEFAULT_TIMEOUT))
    except Exception:
        return _DEFAULT_TIMEOUT


class WebDriverWaitCommon:
    def __init__(self, driver, timeout: int | None = None):
        self.driver = driver
        self.logger = get_logger()
        self.timeout = timeout if timeout is not None else _load_timeout_from_config()

    def _resolve_locator(self, locator: Any) -> tuple[str, str]:
        """兼容 XPath 字符串和 Selenium tuple 定位器。"""
        if isinstance(locator, tuple) and len(locator) == 2:
            by, value = locator
            return str(by), str(value)
        if isinstance(locator, str):
            return By.XPATH, locator
        raise ValueError(f"不支持的定位器格式: {locator}")

    def _wait(self, timeout: int | None = None) -> WebDriverWait:
        return WebDriverWait(self.driver, timeout or self.timeout)

    def _build_not_found_error(self, locator: Any, action: str) -> ElementNotFoundError:
        screenshot_path = ""
        try:
            screenshot_path = ScreenshotUtil.capture(self.driver, f"{action}_{locator}")
        except Exception as capture_error:
            self.logger.warning("元素异常时截图失败: %s", capture_error)
        return ElementNotFoundError(
            message=f"{action}失败，未找到目标元素",
            locator=locator,
            screenshot_path=screenshot_path or None,
        )

    def wait_for_visible(self, locator: Any):
        """等待元素可见。"""
        resolved = self._resolve_locator(locator)
        try:
            return self._wait().until(EC.visibility_of_element_located(resolved))
        except TimeoutException as exc:
            raise self._build_not_found_error(locator, "等待元素可见") from exc

    def wait_for_presence(self, locator: Any):
        """等待元素出现在 DOM（不一定可见）。"""
        resolved = self._resolve_locator(locator)
        try:
            return self._wait().until(EC.presence_of_element_located(resolved))
        except TimeoutException as exc:
            raise self._build_not_found_error(locator, "等待元素出现") from exc

    def wait_for_clickable(self, locator: Any):
        """等待元素可点击。"""
        resolved = self._resolve_locator(locator)
        try:
            return self._wait().until(EC.element_to_be_clickable(resolved))
        except TimeoutException as exc:
            raise self._build_not_found_error(locator, "等待元素可点击") from exc

    def wait_for_disappear(self, locator: Any, timeout: int | None = None) -> bool:
        """等待元素消失，超时返回 False。"""
        resolved = self._resolve_locator(locator)
        try:
            return self._wait(timeout).until(EC.invisibility_of_element_located(resolved))
        except TimeoutException:
            return False

    def is_element_visible(self, locator: Any, timeout: int | None = None) -> bool:
        """判断元素是否可见，不抛异常。"""
        resolved = self._resolve_locator(locator)
        try:
            self._wait(timeout).until(EC.visibility_of_element_located(resolved))
            return True
        except TimeoutException:
            return False

    def get_text(self, locator: Any) -> str:
        """获取元素文本。"""
        return self.wait_for_visible(locator).text

    def get_attribute(self, locator: Any, attr: str) -> str | None:
        """获取元素属性值。"""
        return self.wait_for_visible(locator).get_attribute(attr)

    def scroll_to_element(self, locator: Any):
        """滚动到元素附近，方便后续点击和截图。"""
        element = self.wait_for_visible(locator)
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});",
            element,
        )
        return element

    def send_keys_params(self, locator, params_contents, clear_first=True):
        """
        健壮输入：等待可见 -> 清空 -> 输入。
        :param locator: XPath 字符串或 tuple(By, value)
        :param params_contents: 要输入的值
        :param clear_first: 是否先清空输入框
        """
        element = self.wait_for_visible(locator)
        if clear_first:
            element.clear()
        element.send_keys(params_contents)
        return element

    def click_params(self, locator, force_js=False):
        """
        健壮点击：等待可点击 -> 点击；原生失败自动 JS 点击兜底。
        :param locator: XPath 字符串或 tuple(By, value)
        :param force_js: 需要强制 JS 点击时置 True
        """
        element = self.wait_for_clickable(locator)
        if force_js:
            self.driver.execute_script("arguments[0].click();", element)
            return element
        try:
            element.click()
        except Exception as exc:
            self.logger.warning("原生点击失败，尝试使用 JS 点击兜底: %s", exc)
            self.driver.execute_script("arguments[0].click();", element)
        return element

    def wait_for_text_present(self, locator, text: str, timeout: int | None = None) -> bool:
        """等待元素文本包含指定内容，超时返回 False。"""
        resolved = self._resolve_locator(locator)
        try:
            return self._wait(timeout).until(
                EC.text_to_be_present_in_element(resolved, text)
            )
        except TimeoutException:
            return False

    def execute_script(self, script: str, *args):
        """统一 JS 执行入口。"""
        return self.driver.execute_script(script, *args)
