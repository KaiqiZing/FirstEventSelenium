"""疑难类业务（X-01~X-04）。"""
from __future__ import annotations

from util import allure_compat
from business.business_context import biz_step
from handle.misc_handles import X01Handle, X02Handle, X03Handle, X04Handle


@allure_compat.feature("疑难")
class MiscBusiness:
    def __init__(self, driver):
        self.driver = driver

    @allure_compat.story("X-01 图形验证码")
    def run_x01(self, account: str = "demo", password: str = "demo123") -> None:
        with biz_step("使用万能码 1234 完成验证码登录"):
            X01Handle(self.driver).login_with_universal(account, password)

    @allure_compat.story("X-02 webdriver 特征检测")
    def run_x02(self) -> tuple[str, bool]:
        """执行校验并按页面允许方式断言可观测结果，不做反自动化绕过。

        返回 (访问标识 mark, 是否判定为正常环境)。
        判定不通过时「生成当日数据摘要」按钮被禁用，仅断言受限提示。
        """
        h = X02Handle(self.driver)
        with biz_step("执行环境校验"):
            h.run_check()
            h.wait_check_done()
        mark = h.read_mark()
        if h.is_passed():
            with biz_step("生成当日数据摘要"):
                h.generate_summary()
                return mark, True
        with biz_step("断言受限提示（automation 特征被检出）"):
            assert h.is_blocked(), "环境被判定为异常但仍未展示受限提示"
            return mark, False

    @allure_compat.story("X-03 会话 Cookie 登录态")
    def run_x03(self) -> None:
        h = X03Handle(self.driver)
        with biz_step("登录并生成运营快照"):
            h.do_login()
            h.wait_login_success()
            h.do_biz()
        with biz_step("重新检测登录态确认会话保持"):
            h.recheck()
        with biz_step("退出登录清理会话"):
            h.do_logout()

    @allure_compat.story("X-04 造数自销")
    def run_x04(self, biz_name: str) -> str:
        h = X04Handle(self.driver)
        with biz_step("生成工单编号"):
            generated = h.generate(biz_name)
        with biz_step("归档此工单"):
            h.archive()
        return generated
