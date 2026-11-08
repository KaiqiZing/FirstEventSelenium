"""多窗口/多标签类（M-01~M-04）场景操作层。"""
from __future__ import annotations

import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select

from handle import action_support as act
from handle.base_scenario_handle import BaseScenarioHandle
from util.scenario_support import wait_result_contains


class M01Handle(BaseScenarioHandle):
    """新标签页：target=_blank 打开单据详情 / 脚本打开空白标签。"""

    def __init__(self, driver):
        super().__init__(driver, "M01")

    def open_bill_detail(self) -> str:
        self.wait.wait_for_visible(self.loc("bill_link"))
        main_handle = self.driver.current_window_handle
        before = len(self.driver.window_handles)
        self.driver.find_element(*self.loc("bill_link")).click()
        assert act.wait_new_window(self.driver, before, timeout=10), "点击单据链接后未出现新标签页"
        act.switch_to_latest_window(self.driver)
        bill_no = self.wait.wait_for_visible(self.loc("detail_billno")).text
        return bill_no

    def open_script_blank(self) -> str:
        before = len(self.driver.window_handles)
        self.click("open_blank")
        if act.wait_new_window(self.driver, before, timeout=5):
            act.switch_to_latest_window(self.driver)
            return self.driver.title
        return ""

    def close_to_main(self, main_handle: str) -> None:
        act.close_latest_and_back(self.driver, main_handle)


class M02Handle(BaseScenarioHandle):
    """OAuth 小窗授权：小窗自动回传并关闭。"""

    def __init__(self, driver):
        super().__init__(driver, "M02")

    def start_and_approve(self, timeout: int = 12) -> None:
        main_handle = self.driver.current_window_handle
        before = len(self.driver.window_handles)
        self.click("start_auth")
        assert act.wait_new_window(self.driver, before, timeout=5), "授权小窗未打开"
        act.switch_to_latest_window(self.driver)
        approve = self.wait.wait_for_visible(("css selector", "#approveBtn"))
        approve.click()
        # 等小窗自动关闭，回到主窗口
        assert act.wait_popup_auto_close(self.driver, main_handle, [], timeout=timeout), "授权小窗未自动关闭"
        act.switch_window(self.driver, main_handle)

    def use_ticket(self) -> None:
        self.click("use_ticket")


class M03Handle(BaseScenarioHandle):
    """新窗口内嵌 iframe（窗口内容即 frame-a，内含二级 iframe frame-b）。"""

    def __init__(self, driver):
        super().__init__(driver, "M03")

    def open_process_window(self) -> str:
        main_handle = self.driver.current_window_handle
        before = len(self.driver.window_handles)
        self.click("open_win")
        assert act.wait_new_window(self.driver, before, timeout=5), "处理窗口未打开"
        act.switch_to_latest_window(self.driver)
        return main_handle

    def submit_inner_apply(self, reason: str, amount: str, dept: str) -> None:
        # 新窗口顶层文档即 frame-a，仅需进入其内层 iframe(frame-b)
        act.switch_frame(self.driver, ("css selector", "#innerFrame"))
        self.fill("reason", reason, clear_first=True)
        amount_el = self.wait.wait_for_visible(self.loc("amount"))
        amount_el.clear()
        amount_el.send_keys(amount)
        Select(self.wait.wait_for_visible(self.loc("dept"))).select_by_visible_text(dept)
        self.click("submit")
        act.switch_to_default_content(self.driver)

    def close_window(self, main_handle: str) -> None:
        act.close_latest_and_back(self.driver, main_handle)

    def register_main(self) -> None:
        self.click("main_register")


class M04Handle(BaseScenarioHandle):
    """弹窗拦截策略：手势内直接打开 vs 延时脚本打开。"""

    def __init__(self, driver):
        super().__init__(driver, "M04")

    def direct_open(self) -> bool:
        main_handle = self.driver.current_window_handle
        before = len(self.driver.window_handles)
        self.click("direct_btn")
        opened = act.wait_new_window(self.driver, before, timeout=5)
        if opened:
            act.switch_to_latest_window(self.driver)
            act.close_latest_and_back(self.driver, main_handle)
        return opened

    def delayed_open(self) -> bool:
        before = len(self.driver.window_handles)
        self.click("delayed_btn")
        # 1.2s 后脚本触发
        time.sleep(2.0)
        return len(self.driver.window_handles) > before

    def wait_result_contains(self, keyword: str, timeout: int = 10) -> bool:
        return wait_result_contains(self.driver, keyword, timeout)
