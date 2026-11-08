# coding=utf-8
"""X-01 ~ X-04 疑难类场景主流程用例。"""
from __future__ import annotations

import pytest

from business.misc_business import MiscBusiness
from handle.misc_handles import X01Handle, X03Handle, X04Handle
from util import allure_compat
from util.scenario_support import open_scenario


@allure_compat.feature("疑难")
def test_x01_captcha(driver):
    """图形验证码：使用后端万能码 1234 完成登录。"""
    open_scenario(driver, "/x/01")
    MiscBusiness(driver).run_x01()
    X01Handle(driver).assert_log("验证码校验通过")
    X01Handle(driver).assert_log("「demo」登录成功")


@allure_compat.feature("疑难")
def test_x02_bot_detection(driver):
    """webdriver 特征检测：仅校验并断言可观测结果，不做反自动化绕过。"""
    open_scenario(driver, "/x/02")
    mark, passed = MiscBusiness(driver).run_x02()
    from handle.misc_handles import X02Handle

    x2 = X02Handle(driver)
    x2.assert_log("环境校验完成")
    assert mark in ("true", "false"), f"访问标识读取异常: {mark}"
    if passed:
        x2.assert_log("当日渠道数据摘要已生成")
    else:
        assert x2.is_blocked(), "自动化特征被检出但未展示受限提示"


@allure_compat.feature("疑难")
def test_x03_cookie_session(driver):
    """会话 Cookie 登录态：登录保持 -> 快照 -> 退出清理。"""
    open_scenario(driver, "/x/03")
    MiscBusiness(driver).run_x03()
    h = X03Handle(driver)
    h.assert_log("登录成功：测试员")
    h.assert_log("已生成当日运营快照（需要登录态）")
    h.assert_log("登录态检测：已登录（tester）")
    h.assert_log("已退出登录，会话 Cookie 已清除")
    # 退出后登录面板回到「未登录」，刷新页面重触发 onMounted 的登录态检测
    driver.refresh()
    h.assert_log("登录态检测：未登录")


@allure_compat.feature("疑难")
def test_x04_seed_data(driver):
    """服务端造数：生成带时间戳工单并归档。"""
    open_scenario(driver, "/x/04")
    biz_name = "退款复核"
    generated = MiscBusiness(driver).run_x04(biz_name)
    assert generated.startswith("SEED-"), f"生成工单编号异常: {generated}"
    h = X04Handle(driver)
    h.assert_log("服务端已生成工单")
    h.assert_log(f"工单已归档：{generated}")
    # 造数数据同样落在服务端，可一键查询
    h.ensure_server_data()
    h.assert_log("查询服务端已生成数据")
