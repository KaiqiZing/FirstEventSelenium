"""页面交互类业务（I-01~I-18）：以 allure.step 包装场景动作与结果断言。"""
from __future__ import annotations

from decimal import Decimal
from typing import NamedTuple

from util import allure_compat
from business.business_context import biz_step
from util.amount_util import cents_to_yuan
from handle.interact_handles import (
    I01Handle,
    I02Handle,
    I03Handle,
    I04Handle,
    I05Handle,
    I06Handle,
    I07Handle,
    I08Handle,
    I09Handle,
    I10Handle,
    I11Handle,
    I12Handle,
    I13Handle,
    I14Handle,
    I15Handle,
    I16Handle,
    I17Handle,
    I18Handle,
)


class I18RecapResult(NamedTuple):
    """I-18「调整金额 -> 重算汇总」业务闭环结果：供用例断言页面显示与数据库总额是否一致。"""

    handle: I18Handle
    bill_no: str
    before_summary: Decimal  # 调整前页面「结算单汇总金额合计」
    after_summary: Decimal  # 重算后页面「结算单汇总金额合计」
    after_detail_sum: Decimal  # 重算后库中该结算单明细求和（元）


@allure_compat.feature("页面交互")
class InteractBusiness:
    def __init__(self, driver):
        self.driver = driver

    @allure_compat.story("I-01 元素不可交互")
    def run_i01(self, operator: str, note: str, reviewer: str) -> None:
        with biz_step("填写交接人/说明并勾选须知保存"):
            I01Handle(self.driver).submit_handover(operator, note)
        with biz_step("展开高级配置并应用"):
            I01Handle(self.driver).apply_advanced(reviewer)

    @allure_compat.story("I-02 点击被遮罩拦截")
    def run_i02(self) -> None:
        h = I02Handle(self.driver)
        with biz_step("生成对账结果并等待遮罩消失"):
            h.generate_and_wait()
        with biz_step("点击下载对账结果"):
            h.download_result()

    @allure_compat.story("I-03 元素引用失效")
    def run_i03(self) -> None:
        h = I03Handle(self.driver)
        with biz_step("开启自动刷新并等待整表重建"):
            h.enable_auto_refresh()
        with biz_step("关闭自动刷新稳定列表后查看任务"):
            h.disable_auto_refresh()
            h.view_first_task()

    @allure_compat.story("I-04 双层 iframe")
    def run_i04(self, reason: str, amount: str, dept: str) -> None:
        h = I04Handle(self.driver)
        with biz_step("穿透两层 iframe 提交报销单"):
            h.submit_reimburse(reason, amount, dept)
        with biz_step("回主文档登记处理记录"):
            h.click("main_log_btn")

    @allure_compat.story("I-05 Shadow DOM")
    def run_i05(self, content: str) -> None:
        h = I05Handle(self.driver)
        with biz_step("外层影子节点保存内容"):
            h.save_outer(content)
        with biz_step("触发内层影子节点动作"):
            h.run_inner()
        with biz_step("读取影子节点状态"):
            h.read_state()

    @allure_compat.story("I-06 动态属性")
    def run_i06(self, asset_no: str, asset_name: str) -> None:
        h = I06Handle(self.driver)
        with biz_step("提交资产信息"):
            h.submit_asset(asset_no, asset_name)
        with biz_step("重新生成控件属性后再次提交"):
            h.regen_attributes()
            h.submit_asset(asset_no, asset_name)

    @allure_compat.story("I-07 原生与自绘下拉")
    def run_i07(self, region: str, period: str, biz_type: str, scope: str) -> None:
        h = I07Handle(self.driver)
        with biz_step("原生下拉查询"):
            h.native_query(region, period)
        with biz_step("自绘下拉查询"):
            h.biz_query(biz_type, scope)

    @allure_compat.story("I-08 悬浮菜单")
    def run_i08(self) -> None:
        h = I08Handle(self.driver)
        with biz_step("展开批量打标签"):
            h.batch_label()
        with biz_step("悬浮客户行打开编辑"):
            h.edit_customer()

    @allure_compat.story("I-09 拖拽")
    def run_i09(self) -> None:
        h = I09Handle(self.driver)
        with biz_step("拖拽第一项到已选区"):
            h.drag_first_to_picked()
        with biz_step("确认分配"):
            h.confirm()

    @allure_compat.story("I-10 文件上传")
    def run_i10(self, abs_path: str) -> None:
        with biz_step("上传合同文件并提交登记"):
            I10Handle(self.driver).upload_and_register(abs_path)

    @allure_compat.story("I-11 原生弹窗")
    def run_i11(self, note: str) -> None:
        h = I11Handle(self.driver)
        with biz_step("处理 alert 告警"):
            h.alert_view()
        with biz_step("确认 confirm 补货"):
            h.confirm_stock()
        with biz_step("prompt 登记备注"):
            h.prompt_note(note)

    @allure_compat.story("I-12 富文本")
    def run_i12(self, title: str, body: str) -> None:
        with biz_step("编辑富文本并发布公告"):
            I12Handle(self.driver).publish(title, body)

    @allure_compat.story("I-13 动画完成")
    def run_i13(self) -> None:
        with biz_step("等待动画完成并确认推送"):
            I13Handle(self.driver).open_and_confirm()

    @allure_compat.story("I-14 懒加载")
    def run_i14(self) -> int:
        with biz_step("滚动加载至全部任务"):
            return I14Handle(self.driver).load_all()

    @allure_compat.story("I-15 坐标偏移")
    def run_i15(self) -> None:
        h = I15Handle(self.driver)
        with biz_step("展开完整区域并标记目标"):
            h.expand_and_mark()
        with biz_step("读取目标坐标"):
            h.inspect()

    @allure_compat.story("I-16 受控输入")
    def run_i16(self, customer: str, ticket_type: str, keyword: str, expect: str) -> None:
        h = I16Handle(self.driver)
        with biz_step("创建受控工单"):
            h.submit_ticket(customer, ticket_type)
        with biz_step("关键词联想搜索"):
            h.search_suggest(keyword, expect)
        with biz_step("备注与一键清空"):
            h.clear_remark()

    @allure_compat.story("I-17 父子级金额勾稽")
    def run_i17(self) -> I17Handle:
        """重置结算数据并展开全部子单；返回场景句柄供用例按行层级读取金额。

        子单默认折叠（DOM 中不存在子行），必须先展开才能定位子级明细。
        """
        h = I17Handle(self.driver)
        with biz_step("重置结算数据，子单回到默认折叠态"):
            h.reset_data()
        with biz_step("展开全部父级结算单，等待子单明细渲染"):
            h.expand_all()
        return h

    @allure_compat.story("I-17 父子级金额勾稽")
    def run_i17_adjust(self, parent_id: str, child_id: str, amount: str, expect_state: str) -> I17Handle:
        """调整子单金额并等待后台异步重算（约 0.8s）后父单勾稽状态刷新。"""
        h = I17Handle(self.driver)
        with biz_step(f"调整子单 {child_id} 金额为 {amount}，等待后台重算"):
            h.adjust_child_amount(child_id, amount)
            h.wait_recalc_done(parent_id, expect_state)
        return h

    @allure_compat.story("I-17 父子级金额勾稽")
    def run_i17_collapse(self) -> I17Handle:
        """收起全部父单，验证子单明细被移出 DOM。"""
        h = I17Handle(self.driver)
        with biz_step("收起全部父级结算单，子单明细移出 DOM"):
            h.collapse_all()
        return h

    # ------------------------------------------------------------------ #
    # I-18 页面数字 与 数据库一致性核对（SQLite 真实落库）
    # ------------------------------------------------------------------ #
    @allure_compat.story("I-18 页面数字与数据库核对")
    def run_i18_reset(self) -> I18Handle:
        """重建 SQLite 落库并回到初始数据（该场景会改库，保证可反复执行）。"""
        h = I18Handle(self.driver)
        with biz_step("重置数据库，恢复初始数据"):
            h.reset_data()
        return h

    @allure_compat.story("I-18 页面数字与数据库核对")
    def run_i18_collect_all_details(self) -> dict[str, Decimal | None]:
        """翻完全部分页取全量明细（当前页只有 5 行，直接求和必漏数据）。"""
        h = I18Handle(self.driver)
        with biz_step("逐页翻页并收集全部明细金额"):
            return h.collect_all_details()

    @allure_compat.story("I-18 页面数字与数据库核对")
    def run_i18_adjust_then_recap(self, item_no: str, bill_no: str, delta: Decimal) -> I18RecapResult:
        """业务闭环：调整明细金额 -> 重算汇总 -> 结算单汇总金额合计随之变化。

        每一步都同步核对「页面显示」与「数据库总额」：

        1. 调整后：明细金额落库且页面显示一致；但结算单汇总字段**不回写**，页面汇总金额合计不变；
        2. 重算后：汇总字段按明细求和回写，页面汇总金额合计发生变化；
        3. 收口：页面显示的汇总金额合计必须等于库中 `settle_bill` 求和。
        """
        h = I18Handle(self.driver)
        before_summary = h.summary_value("total")
        # 目标金额 = 库中现值 + 增量（金额由库推导，不在用例里写死）
        target = cents_to_yuan(h.db_detail_cents(item_no)) + delta
        h.adjust_detail(item_no, str(target))
        with biz_step(f"调整明细 {item_no} 金额 {delta:+}，等待页面与库同步"):
            h.wait_detail_amount(item_no, target)
            h.wait_db_equals(lambda: h.db_detail_cents(item_no), int(target * 100))
        with biz_step(
            "未重算前：结算单汇总金额合计不变，且仍等于库汇总字段求和"
        ):
            h.wait_page_decimal(lambda: h.summary_value("total"), before_summary)
            h.wait_page_decimal(lambda: h.summary_value("total"), cents_to_yuan(h.db_bill_sum_cents()))
        with biz_step(f"重算 {bill_no} 汇总：结算单汇总金额合计应变化 {delta:+}"):
            h.recap_bill(item_no)
            h.wait_db_equals(
                lambda: h.db_bill_total_cents(bill_no), h.db_detail_sum_cents(bill_no)
            )
            after_summary = h.wait_page_decimal(
                lambda: h.summary_value("total"), cents_to_yuan(h.db_bill_sum_cents())
            )
        return I18RecapResult(
            handle=h,
            bill_no=bill_no,
            before_summary=before_summary,
            after_summary=after_summary,
            after_detail_sum=cents_to_yuan(h.db_detail_sum_cents(bill_no)),
        )

    @allure_compat.story("I-18 页面数字与数据库核对")
    def run_i18_post(self, account_no: str) -> int:
        """模拟清算入账：直接改数据库但页面不刷新（页面数字瞬间变为陈旧读数）。"""
        h = I18Handle(self.driver)
        with biz_step("服务端模拟清算入账，等待账户余额落库"):
            before = h.db_account_cents(account_no)
            h.post_account()
            return h.wait_db_changed(lambda: h.db_account_cents(account_no), before)

    @allure_compat.story("I-18 页面数字与数据库核对")
    def run_i18_refresh(self) -> I18Handle:
        """刷新页面快照：把「库已变、页面未变」的差异同步回来。"""
        h = I18Handle(self.driver)
        with biz_step("刷新数据快照"):
            h.refresh()
        return h

    @allure_compat.story("I-18 页面数字与数据库核对")
    def run_i18_db_dialog(self, table: str) -> int:
        """打开页面「数据库查询」弹窗直查原始行，返回行数。"""
        h = I18Handle(self.driver)
        with biz_step(f"打开数据库查询弹窗并查询 {table} 原始记录"):
            h.open_db_dialog()
            rows = h.query_db_table(table)
        with biz_step("关闭数据库查询弹窗"):
            h.close_db_dialog()
        return rows
