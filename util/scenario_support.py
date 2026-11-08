"""场景导航 / 结果区断言 / 服务预检等通用工具（不依赖具体 handle）。"""
from __future__ import annotations

from typing import Any

from log.user_log import get_logger
from config.settings import Config

logger = get_logger()

_RESULT_BOX_XPATH = "//div[contains(@class, 'result-box')]"
_LOG_LINE_XPATH = "//div[contains(@class, 'result-box')]//*[contains(@class,'log-line')]"
_TITLE_XPATH = "//div[contains(@class, 'page-title')]"


# 前端常用端口：Vite 默认 5173，端口被占用时会顺延（如 5174）——配置不通时自动回退
_FRONTEND_PORTS = ("5173", "5174")
# 会话内解析成功的可用前端地址（避免每次请求都探测）
_effective_base_url: str | None = None


def get_base_url() -> str:
    if _effective_base_url:
        return _effective_base_url
    env_config = Config().get_env_config()
    return str(env_config.get("base_url", "http://localhost:5174")).rstrip("/")


def _probe(url: str, timeout: int = 3) -> bool:
    import requests

    try:
        return requests.get(f"{url}/", timeout=timeout).status_code < 500
    except Exception:
        return False


def resolve_base_url(timeout: int = 3) -> str:
    """确定可用前端地址：配置端口不通时回退到另一个常用端口并告警。"""
    global _effective_base_url
    if _effective_base_url:
        return _effective_base_url

    import re

    base = get_base_url()
    if _probe(base, timeout):
        _effective_base_url = base
        return base
    for port in _FRONTEND_PORTS:
        candidate = re.sub(r":\d+$", f":{port}", base)
        if candidate != base and _probe(candidate, timeout):
            logger.warning("配置的前端地址 %s 不可达，已自动切换为 %s", base, candidate)
            _effective_base_url = candidate
            return candidate
    _effective_base_url = base
    return base


def get_api_base_url() -> str:
    env_config = Config().get_env_config()
    return str(env_config.get("api_base_url", "http://127.0.0.1:5000")).rstrip("/")


def open_scenario(driver, route: str, timeout: int = 15) -> None:
    """直达场景路由并等待页面标题出现。"""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.wait import WebDriverWait

    url = f"{get_base_url()}{route}"
    logger.info("打开场景页面: %s", url)
    driver.get(url)
    WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.XPATH, _TITLE_XPATH)))


def wait_page_title(driver, timeout: int = 15) -> str:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.wait import WebDriverWait

    title_el = WebDriverWait(driver, timeout).until(
        EC.visibility_of_element_located((By.XPATH, _TITLE_XPATH))
    )
    return title_el.text


def result_logs(driver) -> list[str]:
    """读取页面底部「操作结果」区全部日志行文本。"""
    from selenium.webdriver.common.by import By

    texts: list[str] = []
    try:
        box = driver.find_element(By.XPATH, _RESULT_BOX_XPATH)
    except Exception:
        return texts
    lines = box.find_elements(By.XPATH, ".//*[contains(@class,'log-line')]")
    for line in lines:
        try:
            texts.append(line.text)
        except Exception:
            continue
    return texts


def wait_result_contains(driver, keyword: str, timeout: int = 15) -> bool:
    """轮询「操作结果」区直到出现包含 keyword 的日志行。"""
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        for text in result_logs(driver):
            if keyword in text:
                logger.info("结果区命中关键字「%s」: %s", keyword, text)
                return True
        time.sleep(0.3)
    return False


def assert_result_contains(driver, keyword: str, timeout: int = 15, extra: str = "") -> None:
    if not wait_result_contains(driver, keyword, timeout):
        recent = result_logs(driver)
        raise AssertionError(
            f"「操作结果」区在 {timeout}s 内未出现关键字「{keyword}」{extra}；当前日志: {recent or '（空）'}"
        )


def preflight_services() -> None:
    """会话级服务预检：前端可达 + 5000 后端健康。失败给出明确提示。"""
    import requests

    base_url = resolve_base_url()
    api_base_url = get_api_base_url()

    try:
        resp = requests.get(f"{base_url}/", timeout=5)
        resp.raise_for_status()
    except Exception as e:
        raise RuntimeError(
            f"被测前端不可达 {base_url}（请先启动: cd frontend && npm run dev），原因: {e}"
        ) from e

    try:
        resp = requests.get(f"{api_base_url}/api/health", timeout=5)
        resp.raise_for_status()
        body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
    except Exception as e:
        raise RuntimeError(
            f"被测后端不可达 {api_base_url}/api/health（请先启动: cd backend && python app.py），原因: {e}"
        ) from e
    logger.info("服务预检通过: frontend=%s backend=%s body=%s", base_url, api_base_url, body)
