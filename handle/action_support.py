"""被测平台通用动作支持层。

把跨场景的浏览器/页面级平台动作收敛在此，供各场景 handle 复用：
多窗口句柄、iframe（嵌套）、Shadow DOM 穿透、原生弹窗、hover、HTML5 拖拽、
文件上传、contenteditable、内部滚动容器、Element Plus 浮层等。
"""
from __future__ import annotations

import time
from typing import Any, Callable

from selenium.common.exceptions import (
    NoAlertPresentException,
    NoSuchFrameException,
    NoSuchWindowException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from log.user_log import get_logger

logger = get_logger()


def _wait(driver, timeout: int = 10) -> WebDriverWait:
    return WebDriverWait(driver, timeout)


# --------------------------------------------------------------------------- #
# 多窗口 / 多标签句柄
# --------------------------------------------------------------------------- #
def wait_new_window(driver, before_count: int, timeout: int = 12) -> bool:
    """等待窗口句柄数量比 before_count 增加。"""
    try:
        return _wait(driver, timeout).until(
            lambda d: len(d.window_handles) > before_count
        )
    except TimeoutException:
        return False


def wait_window_count(driver, target_count: int, timeout: int = 12) -> bool:
    try:
        return _wait(driver, timeout).until(lambda d: len(d.window_handles) == target_count)
    except TimeoutException:
        return False


def current_handles(driver) -> list[str]:
    return list(driver.window_handles)


def switch_to_latest_window(driver) -> str:
    """切换到最新打开的窗口，返回该句柄。"""
    handle = driver.window_handles[-1]
    driver.switch_to.window(handle)
    return handle


def switch_window(driver, handle: str) -> None:
    driver.switch_to.window(handle)


def close_latest_and_back(driver, main_handle: str) -> None:
    """关闭当前窗口并切回主句柄（若还存活）。"""
    try:
        driver.close()
    except Exception as exc:  # pragma: no cover
        logger.warning("关闭窗口失败: %s", exc)
    try:
        driver.switch_to.window(main_handle)
    except NoSuchWindowException:
        logger.warning("主窗口句柄已失效: %s", main_handle)


def wait_popup_auto_close(driver, main_handle: str, extra_handles: list[str], timeout: int = 12) -> bool:
    """等待小窗自动关闭，主窗口句柄重新可切回。"""
    try:
        return _wait(driver, timeout).until(
            lambda d: all(h not in d.window_handles for h in extra_handles)
        )
    except TimeoutException:
        return False


# --------------------------------------------------------------------------- #
# iframe 切换
# --------------------------------------------------------------------------- #
def switch_frame(driver, frame_locator: Any, timeout: int = 10) -> None:
    """按定位器进入 iframe（支持 css 字符串 / (By,value) / 元素）。"""
    if isinstance(frame_locator, str):
        frame = _wait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, frame_locator))
        )
    elif isinstance(frame_locator, tuple):
        frame = _wait(driver, timeout).until(EC.presence_of_element_located(frame_locator))
    else:
        frame = frame_locator
    driver.switch_to.frame(frame)


def switch_to_default_content(driver) -> None:
    try:
        driver.switch_to.default_content()
    except NoSuchWindowException:  # pragma: no cover
        logger.warning("无法切回主文档（窗口可能已关闭）")


def switch_to_parent_frame(driver) -> None:
    try:
        driver.switch_to.parent_frame()
    except NoSuchFrameException:
        logger.warning("没有父 frame")


# --------------------------------------------------------------------------- #
# 原生 JS 弹窗 alert/confirm/prompt
# --------------------------------------------------------------------------- #
def accept_alert(driver, timeout: int = 10) -> str:
    alert = _wait(driver, timeout).until(EC.alert_is_present())
    text = alert.text
    alert.accept()
    return text


def dismiss_alert(driver, timeout: int = 10) -> str:
    alert = _wait(driver, timeout).until(EC.alert_is_present())
    text = alert.text
    alert.dismiss()
    return text


def prompt_alert(driver, text: str, timeout: int = 10) -> str:
    alert = _wait(driver, timeout).until(EC.alert_is_present())
    message = alert.text
    alert.send_keys(text)
    alert.accept()
    return message


def has_alert(driver, timeout: float = 1.0) -> bool:
    try:
        driver.switch_to.alert
        return True
    except NoAlertPresentException:
        return False


# --------------------------------------------------------------------------- #
# hover / 键盘鼠标
# --------------------------------------------------------------------------- #
def hover(driver, element_or_locator: Any) -> None:
    """悬停到元素上展开菜单。"""
    if isinstance(element_or_locator, str):
        target = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, element_or_locator))
        )
    elif isinstance(element_or_locator, tuple):
        target = WebDriverWait(driver, 10).until(EC.element_to_be_clickable(element_or_locator))
    else:
        target = element_or_locator
    ActionChains(driver).move_to_element(target).perform()


# --------------------------------------------------------------------------- #
# HTML5 拖拽
# --------------------------------------------------------------------------- #
def drag_and_drop(driver, source: Any, target: Any) -> None:
    """HTML5 拖拽；DataTransfer 触发与否取决于浏览器/驱动实现。"""
    if isinstance(source, (str, tuple)):
        src = WebDriverWait(driver, 10).until(EC.presence_of_element_located(
            source if isinstance(source, tuple) else (By.CSS_SELECTOR, source)
        ))
    else:
        src = source
    if isinstance(target, (str, tuple)):
        dst = WebDriverWait(driver, 10).until(EC.presence_of_element_located(
            target if isinstance(target, tuple) else (By.CSS_SELECTOR, target)
        ))
    else:
        dst = target
    ActionChains(driver).drag_and_drop(src, dst).perform()


# --------------------------------------------------------------------------- #
# 文件上传（隐藏 input[type=file] 直接 send_keys 绝对路径）
# --------------------------------------------------------------------------- #
def upload_file(driver, file_input_locator: Any, abs_path: str) -> None:
    if isinstance(file_input_locator, str):
        element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, file_input_locator))
        )
    elif isinstance(file_input_locator, tuple):
        element = WebDriverWait(driver, 10).until(EC.presence_of_element_located(file_input_locator))
    else:
        element = file_input_locator
    element.send_keys(abs_path)


# --------------------------------------------------------------------------- #
# 富文本 contenteditable
# --------------------------------------------------------------------------- #
def fill_contenteditable(driver, locator: Any, text: str) -> None:
    el = WebDriverWait(driver, 10).until(EC.element_to_be_clickable(locator))
    el.click()
    el.send_keys(text)


# --------------------------------------------------------------------------- #
# 内部滚动容器懒加载
# --------------------------------------------------------------------------- #
def scroll_container_to_bottom(driver, container_locator: Any) -> None:
    el = WebDriverWait(driver, 10).until(EC.presence_of_element_located(container_locator))
    driver.execute_script(
        "arguments[0].scrollTop = arguments[0].scrollHeight;", el
    )


def element_in_viewport(driver, locator: Any) -> bool:
    """判断元素是否已渲染到视口内（供懒加载断言）。"""
    from selenium.webdriver.common.by import By as _By

    try:
        el = driver.find_element(*locator)
        return bool(driver.execute_script(
            "var r=arguments[0].getBoundingClientRect();"
            "return r.top < window.innerHeight && r.bottom > 0;", el
        ))
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# Stale / 拦截异常重试
# --------------------------------------------------------------------------- #
def retry_on_stale(driver, locator: Any, action: Callable[[Any], None], attempts: int = 3):
    """执行 action(element)，遇 StaleElementReference / ElementClickIntercepted 时重新定位重试。"""
    for i in range(1, attempts + 1):
        try:
            element = WebDriverWait(driver, 10).until(EC.element_to_be_clickable(locator))
            action(element)
            return
        except (StaleElementReferenceException, WebDriverException) as exc:
            logger.warning("第 %s 次操作遇异常(%s)，重新定位后重试", i, type(exc).__name__)
            time.sleep(0.5)
    raise AssertionError(f"元素操作在 {attempts} 次重试后仍失败: {locator}")


# --------------------------------------------------------------------------- #
# Vue v-model 可靠输入：用原生 value setter 设值并派发 input/change 事件
# --------------------------------------------------------------------------- #
def set_input_value(driver, element: Any, value: str) -> None:
    """绕过框架值同步问题，直接通过原生 setter 写入并派发事件。

    适用于 el-input 内层 input、原生 date/time/datetime-local 等可绑定 v-model 的输入框，
    避免 element.clear()+send_keys 在 Vue 受控组件上残留旧值或未触发 input 的情况。
    """
    driver.execute_script(
        "const el = arguments[0]; const val = arguments[1];"
        "const proto = el.tagName === 'TEXTAREA'"
        "  ? window.HTMLTextAreaElement.prototype"
        "  : window.HTMLInputElement.prototype;"
        "const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;"
        "setter.call(el, val);"
        "el.dispatchEvent(new Event('input', { bubbles: true, composed: true }));"
        "el.dispatchEvent(new Event('change', { bubbles: true }));",
        element, value,
    )


def set_input_value_by_locator(driver, locator: Any, value: str) -> None:
    """按定位器等待元素后写入值。"""
    if isinstance(locator, (str, tuple)):
        resolved = locator if isinstance(locator, tuple) else (By.CSS_SELECTOR, locator)
        el = WebDriverWait(driver, 10).until(EC.presence_of_element_located(resolved))
    else:
        el = locator
    set_input_value(driver, el, value)


# --------------------------------------------------------------------------- #
# Element Plus 公共控件动作
# --------------------------------------------------------------------------- #
def click_el_checkbox_by_text(driver, text: str) -> None:
    """按 label 文本点击 el-checkbox（含『记住登录状态』/『我已阅读并同意…』）。"""
    xpath = f"//label[contains(@class,'el-checkbox')][contains(.,'{text}')]"
    WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, xpath))).click()


def click_el_radio_by_text(driver, text: str) -> None:
    xpath = f"//label[contains(@class,'el-radio-button')][contains(.,'{text}')]"
    WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, xpath))).click()


def click_el_option(driver, option_text: str, timeout: int = 10) -> None:
    """点击已展开的 el-select 浮层选项（浮层挂 body）。"""
    xpath = f"//li[contains(@class,'el-select-dropdown__item')][contains(.,'{option_text}')]"
    WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((By.XPATH, xpath))).click()


def el_select_by_text(driver, trigger_locator: Any, option_text: str) -> None:
    """打开 el-select 并选择选项文本。"""
    if isinstance(trigger_locator, tuple):
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable(trigger_locator)).click()
    else:
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable(trigger_locator)).click()
    click_el_option(driver, option_text)


def wait_loading_mask_gone(driver, mask_locator: Any, timeout: int = 15) -> bool:
    try:
        return WebDriverWait(driver, timeout).until(
            EC.invisibility_of_element_located(mask_locator)
        )
    except TimeoutException:
        return False


def click_with_js(driver, element: Any) -> None:
    driver.execute_script("arguments[0].click();", element)


def wait_enabled(driver, locator: Any, timeout: int = 15):
    """等待按钮从 disabled 变为可点击。"""
    from selenium.webdriver.common.by import By as _By

    def _enabled(d):
        try:
            el = d.find_element(*locator) if isinstance(locator, tuple) else d.find_element(_By.XPATH, locator)
            return el.is_enabled() and el.is_displayed()
        except Exception:
            return False

    WebDriverWait(driver, timeout).until(_enabled)


def wait_for_new_page_after_click(driver, current_url: str, timeout: int = 15) -> bool:
    try:
        return WebDriverWait(driver, timeout).until(lambda d: d.current_url != current_url)
    except TimeoutException:
        return False
