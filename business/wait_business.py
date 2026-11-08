"""等待响应类业务（W-01~W-05）。"""
from __future__ import annotations

from util import allure_compat
from business.business_context import biz_step
from handle.wait_handles import W01Handle, W02Handle, W03Handle, W04Handle, W05Handle


@allure_compat.feature("等待响应")
class WaitBusiness:
    def __init__(self, driver):
        self.driver = driver

    @allure_compat.story("W-01 慢接口 + loading")
    def run_w01(self) -> int:
        h = W01Handle(self.driver)
        with biz_step("选择常规(3s)档位并查询"):
            h.pick_normal_speed()
            return h.query_and_wait_rows()

    @allure_compat.story("W-02 SPA 子视图切换")
    def run_w02(self) -> None:
        h = W02Handle(self.driver)
        with biz_step("切换至收支明细子视图"):
            h.switch_to_flow()

    @allure_compat.story("W-03 异步导出任务")
    def run_w03(self) -> None:
        h = W03Handle(self.driver)
        with biz_step("发起导出并等待完成"):
            h.start_export()
            assert h.wait_export_done(), "导出任务在超时时间内未完成"
        with biz_step("点击下载导出文件"):
            h.click_download()

    @allure_compat.story("W-04 保存落库竞态")
    def run_w04(self, content: str) -> None:
        h = W04Handle(self.driver)
        with biz_step("保存处理内容并等待落库完成"):
            assert h.save_record(content), "未等到保存请求完成日志"
        with biz_step("刷新已存记录并确认新记录可见"):
            h.refresh_list()
            assert h.wait_record_shown(content), "刷新后未在列表看到刚保存的记录"

    @allure_compat.story("W-05 不稳定接口重试")
    def run_w05(self) -> int:
        with biz_step("带重试同步直至成功"):
            return W05Handle(self.driver).sync_until_success()
