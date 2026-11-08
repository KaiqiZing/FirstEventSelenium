"""兼容类（C-01~C-02）场景操作层。"""
from __future__ import annotations

from handle.base_scenario_handle import BaseScenarioHandle


class C01Handle(BaseScenarioHandle):
    """原生日期/时间/日期时间控件：按输入框原生格式填入。"""

    def __init__(self, driver):
        super().__init__(driver, "C01")

    def submit_schedule(self, name: str, start_date: str, end_date: str,
                        start_time: str, sale_at: str) -> None:
        self.js_fill("name", name)
        self.js_fill("start_date", start_date)
        self.js_fill("end_date", end_date)
        self.js_fill("start_time", start_time)
        self.js_fill("sale_at", sale_at)
        self.click("submit_btn")


class C02Handle(BaseScenarioHandle):
    """环境信息核对：读取采集到的关键环境值。"""

    def __init__(self, driver):
        super().__init__(driver, "C02")

    def recollect(self) -> None:
        self.click("collect_btn")

    def read_webdriver_flag(self) -> str:
        return self.text_of("webdriver_kv")

    def read_user_agent(self) -> str:
        return self.text_of("ua_kv")
