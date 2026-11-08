"""等待响应类（W-01~W-05）场景操作层。"""
from __future__ import annotations

import time

from selenium.webdriver.common.by import By

from handle import action_support as act
from handle.base_scenario_handle import BaseScenarioHandle
from util.scenario_support import result_logs, wait_result_contains


class W01Handle(BaseScenarioHandle):
    """慢接口：点击查询后先等 loading 遮罩消失再读表格。"""

    def __init__(self, driver):
        super().__init__(driver, "W01")

    def pick_normal_speed(self) -> None:
        act.click_el_radio_by_text(self.driver, "常规（3s）")

    def query_and_wait_rows(self, timeout: int = 20) -> int:
        self.click("query_btn")
        # 等待 loading 遮罩消失
        act.wait_loading_mask_gone(self.driver, self.loc("loading_mask"), timeout=timeout)
        # 表格行数稳定后再读取
        deadline = time.time() + timeout
        last_count = 0
        stable_since = time.time()
        while time.time() < deadline:
            rows = self.driver.find_elements(*self.loc("table_rows"))
            count = len(rows)
            if count and count == last_count:
                if time.time() - stable_since > 0.8:
                    return count
            else:
                last_count = count
                stable_since = time.time()
            time.sleep(0.3)
        return last_count


class W02Handle(BaseScenarioHandle):
    """SPA 路由切换：点击 tab 后从 URL 与视图卡片双重确认已切换。"""

    def __init__(self, driver):
        super().__init__(driver, "W02")

    def switch_to_flow(self, timeout: int = 10) -> None:
        self.click("tab_flow")
        # 等待 URL 带 view=flow（无整页刷新）
        deadline = time.time() + timeout
        while time.time() < deadline:
            if "view=flow" in self.driver.current_url:
                break
            time.sleep(0.3)
        else:
            raise AssertionError("切换子视图后 URL 未包含 view=flow")
        self.wait.wait_for_visible(self.loc("view_card"))


class W03Handle(BaseScenarioHandle):
    """异步导出长任务：页面内部轮询，等待任务完成再点下载。"""

    def __init__(self, driver):
        super().__init__(driver, "W03")

    def start_export(self) -> None:
        self.click("start_btn")

    def wait_export_done(self, timeout: int = 40) -> bool:
        return wait_result_contains(self.driver, "导出完成", timeout)

    def click_download(self) -> None:
        self.wait.wait_for_visible(self.loc("download_link"))
        self.click("download_link")


class W04Handle(BaseScenarioHandle):
    """保存后落库竞态：等待保存完成后再刷新列表断言。"""

    def __init__(self, driver):
        super().__init__(driver, "W04")

    def save_record(self, content: str, timeout: int = 15) -> bool:
        self.fill("content", content)
        self.click("save_btn")
        # 后端 sleep 2.6s 后才入库并返回
        return wait_result_contains(self.driver, "保存请求完成", timeout)

    def refresh_list(self) -> None:
        self.click("refresh_btn")

    def wait_record_shown(self, content: str, timeout: int = 10) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            records = self.driver.find_elements(*self.loc("rec_list"))
            for rec in records:
                if content in rec.text:
                    return True
            time.sleep(0.4)
        return False


class W05Handle(BaseScenarioHandle):
    """不稳定接口：页面内带重试，直到成功为止。"""

    def __init__(self, driver, max_seconds: int = 60):
        super().__init__(driver, "W05")
        self.max_seconds = max_seconds

    def sync_until_success(self, timeout_each: int = 10) -> int:
        deadline = time.time() + self.max_seconds
        attempts = 0
        while time.time() < deadline:
            attempts += 1
            button = self.wait.wait_for_clickable(self.loc("sync_btn"))
            button.click()
            if wait_result_contains(self.driver, "同步成功", timeout_each):
                return attempts
            # 失败提示日志出现后，按钮会自动恢复可点，进入下一轮
            time.sleep(0.5)
        raise AssertionError(f"W-05 不稳定接口在 {self.max_seconds}s 内始终未同步成功")

    def result_row_count(self) -> int:
        try:
            return len(self.driver.find_elements(*self.loc("result_table")))
        except Exception:
            return 0

    def last_logs(self) -> list[str]:
        return result_logs(self.driver)
