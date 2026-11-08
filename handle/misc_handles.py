"""疑难类（X-01~X-04）场景操作层。"""
from __future__ import annotations

import time

from selenium.webdriver.common.by import By

from handle.base_scenario_handle import BaseScenarioHandle
from util.scenario_support import result_logs, wait_result_contains


class X01Handle(BaseScenarioHandle):
    """图形验证码：使用后端万能码 1234。"""

    def __init__(self, driver):
        super().__init__(driver, "X01")

    def login_with_universal(self, account: str, password: str, code: str = "1234") -> None:
        self.wait.wait_for_visible(self.loc("account"))
        self.js_fill("account", account)
        self.js_fill("password", password)
        self.js_fill("captcha", code)
        self.click("login_btn")

    def wait_login_success(self, timeout: int = 10) -> bool:
        return wait_result_contains(self.driver, "登录成功", timeout)


class X02Handle(BaseScenarioHandle):
    """webdriver 特征检测：只校验/读取，不做绕过。"""

    def __init__(self, driver):
        super().__init__(driver, "X02")

    def run_check(self) -> None:
        self.click("check_btn")

    def wait_check_done(self, timeout: int = 15) -> bool:
        return wait_result_contains(self.driver, "环境校验完成", timeout)

    def read_mark(self) -> str:
        """读取访问标识（String(navigator.webdriver) 的值）。"""
        try:
            return self.text_of("detect_mono").strip()
        except Exception:
            return ""

    def is_passed(self) -> bool:
        """根据判定结果判断是否视为正常浏览器环境。"""
        try:
            verdict = self.text_of("result_verdict")
            return "正常浏览器环境" in verdict or "环境校验通过" in verdict
        except Exception:
            return False

    def is_blocked(self) -> bool:
        """受限提示是否出现（automatic 特征被检测到时置 True）。"""
        return self.wait.is_element_visible(self.loc("block_tip"), timeout=8)

    def read_mono_block(self) -> str:
        return self.read_mark()

    def generate_summary(self) -> None:
        self.click("gen_summary")


class X03Handle(BaseScenarioHandle):
    """会话 Cookie 登录态：登录 -> 保持会话 -> 退出。"""

    def __init__(self, driver):
        super().__init__(driver, "X03")

    def do_login(self, account: str = "tester", password: str = "123456") -> None:
        self.wait.wait_for_visible(self.loc("login_account"))
        self.js_fill("login_account", account)
        self.js_fill("login_password", password)
        self.click("login_btn")

    def do_biz(self) -> None:
        self.click("do_biz")

    def recheck(self) -> None:
        self.click("recheck_btn")

    def do_logout(self) -> None:
        self.click("logout_btn")

    def wait_login_success(self, timeout: int = 10) -> bool:
        return wait_result_contains(self.driver, "登录成功", timeout)

    def session_ready(self) -> bool:
        return "已登录" in "\n".join(result_logs(self.driver))


class X04Handle(BaseScenarioHandle):
    """服务端造数：造一条含时间戳工单并归档自销。"""

    def __init__(self, driver):
        super().__init__(driver, "X04")

    def generate(self, biz_name: str) -> str:
        self.js_fill("biz_name", biz_name)
        self.click("gen_btn")
        generated = self.wait.wait_for_visible(self.loc("gen_id")).text
        return generated

    def archive(self) -> None:
        self.click("archive_btn")

    def wait_archive_done(self, timeout: int = 10) -> bool:
        return wait_result_contains(self.driver, "归档完成", timeout)

    def ensure_server_data(self) -> None:
        self.click("load_all")
