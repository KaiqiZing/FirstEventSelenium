# coding=utf-8
"""C-01 ~ C-02 兼容类场景主流程用例。"""
from __future__ import annotations

import pytest

from business.compat_business import CompatBusiness
from handle.compat_handles import C02Handle
from handle.interact_handles import I01Handle as ResultBoxHandle
from util import allure_compat
from util.scenario_support import open_scenario


@allure_compat.feature("兼容")
def test_c01_date_input(driver):
    """原生日期时间控件：按原生格式填入并提交。"""
    open_scenario(driver, "/c/01")
    CompatBusiness(driver).run_c01(
        name="9 月会员日秒杀",
        start_date="2026-09-10",
        end_date="2026-09-12",
        start_time="10:00",
        sale_at="2026-09-12T20:30",
    )
    ResultBoxHandle(driver).assert_log("排期已提交")


@allure_compat.feature("兼容")
def test_c02_env_info(driver):
    """环境信息核对：读取自动化标识与 User Agent。"""
    open_scenario(driver, "/c/02")
    webdriver_flag, ua = CompatBusiness(driver).run_c02()
    assert ua and "Mozilla" in ua, f"User Agent 读取异常: {ua}"
    assert webdriver_flag in ("true", "false"), f"自动化标识读取异常: {webdriver_flag}"
    C02Handle(driver).assert_log("已采集当前浏览器环境信息")
