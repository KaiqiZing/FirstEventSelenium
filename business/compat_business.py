"""兼容类业务（C-01~C-02）。"""
from __future__ import annotations

from util import allure_compat
from business.business_context import biz_step
from handle.compat_handles import C01Handle, C02Handle


@allure_compat.feature("兼容")
class CompatBusiness:
    def __init__(self, driver):
        self.driver = driver

    @allure_compat.story("C-01 日期时间原生控件")
    def run_c01(self, name: str, start_date: str, end_date: str,
                start_time: str, sale_at: str) -> None:
        with biz_step("填写活动排期并提交"):
            C01Handle(self.driver).submit_schedule(
                name, start_date, end_date, start_time, sale_at
            )

    @allure_compat.story("C-02 环境信息")
    def run_c02(self) -> tuple[str, str]:
        h = C02Handle(self.driver)
        with biz_step("重新采集环境信息"):
            h.recollect()
        with biz_step("读取自动化标识与 User Agent"):
            return h.read_webdriver_flag(), h.read_user_agent()
