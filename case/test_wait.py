# coding=utf-8
"""W-01 ~ W-05 等待响应类场景主流程用例。"""
from __future__ import annotations

import pytest

from business.wait_business import WaitBusiness
from handle.wait_handles import W02Handle, W03Handle
from handle.interact_handles import I01Handle as ResultBoxHandle
from util import allure_compat
from util.scenario_support import open_scenario


@pytest.mark.smoke
@allure_compat.feature("等待响应")
def test_w01_slow_loading(driver):
    """慢接口：等待 loading 遮罩消失与表格行稳定。"""
    open_scenario(driver, "/w/01")
    count = WaitBusiness(driver).run_w01()
    assert count >= 10, f"慢接口返回行数异常: {count}"
    ResultBoxHandle(driver).assert_log("查询完成")


@allure_compat.feature("等待响应")
def test_w02_spa_route_switch(driver):
    """SPA 无刷新路由切换：切到收支明细并等待 URL/内容变化。"""
    open_scenario(driver, "/w/02")
    WaitBusiness(driver).run_w02()
    h = W02Handle(driver)
    assert "view=flow" in driver.current_url
    strong_text = h.text_of("view_card")
    assert "收支明细" in strong_text, f"视图卡片内容未切换: {strong_text}"
    ResultBoxHandle(driver).assert_log("当前子视图：flow")


@allure_compat.feature("等待响应")
def test_w03_export_task(driver):
    """异步导出：等待任务完成后再触发下载。"""
    open_scenario(driver, "/w/03")
    WaitBusiness(driver).run_w03()
    h = W03Handle(driver)
    h.assert_log("导出完成")
    h.assert_log("已触发下载导出文件")


@allure_compat.feature("等待响应")
def test_w04_race_assert(driver):
    """保存落库竞态：先等完成再刷新断言，避免断言跑在落库前。"""
    open_scenario(driver, "/w/04")
    content = f"临时调整门店营业时间-{__import__('time').time_ns() % 10000}"
    WaitBusiness(driver).run_w04(content)


@allure_compat.feature("等待响应")
def test_w05_unstable_api(driver):
    """不稳定接口：页面内重试直至同步成功。"""
    open_scenario(driver, "/w/05")
    attempts = WaitBusiness(driver).run_w05()
    assert attempts >= 1
    ResultBoxHandle(driver).assert_log("同步成功")
