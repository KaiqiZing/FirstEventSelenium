# coding=utf-8
"""I-01 ~ I-18 页面交互类场景主流程用例。

运行前需保证被测系统已启动：前端 http://localhost:5174 与后端 http://127.0.0.1:5000。
"""
from __future__ import annotations

import tempfile
from decimal import Decimal
from pathlib import Path

import pytest

from business.interact_business import InteractBusiness
from handle.interact_handles import I01Handle, I02Handle, I09Handle, I14Handle, I18Handle
from util import allure_compat
from util.amount_util import amount_equal, cents_to_yuan, parse_amount
from util.scenario_support import open_scenario

# I-17 结算单固定数据：001 勾稽一致、002 固定一分钱尾差
I17_PARENT_MATCHED = "S-20260915-001"
I17_PARENT_TAIL_DIFF = "S-20260915-002"
I17_CHILD_ADJUST = "D-0001"
I17_CHILD_NEGATIVE = "D-0014"

# I-18 不写死任何样本编号/金额：明细与账户样本均按「角色」从数据库动态挑选
# （见 I18Handle.pick_detail / pick_detail_in_matched_bill / account_numbers）


@pytest.mark.smoke
@allure_compat.feature("页面交互")
def test_i01_not_interactable(driver):
    """不可交互控件：勾选须知后才能保存；折叠区展开后应用高级配置。"""
    open_scenario(driver, "/i/01")
    InteractBusiness(driver).run_i01("交接员-01", "完成 8 月对账交接", "审核员-王")
    handle = I01Handle(driver)
    handle.assert_log("交接记录已保存")
    handle.assert_log("高级配置已应用")
    handle.assert_log("审核员-王")


@pytest.mark.smoke
@allure_compat.feature("页面交互")
def test_i02_click_intercepted(driver):
    """点击被遮罩拦截：等遮罩消失后再点下载。"""
    open_scenario(driver, "/i/02")
    InteractBusiness(driver).run_i02()
    h2 = I02Handle(driver)
    h2.assert_log("对账计算完成，可以下载结果文件")
    h2.assert_log("已开始下载对账结果文件 result-2609.csv")


@allure_compat.feature("页面交互")
def test_i03_stale_element(driver):
    """元素引用失效：开启自动刷新导致整表重建，随后稳定列表再点击。"""
    open_scenario(driver, "/i/03")
    InteractBusiness(driver).run_i03()
    I01Handle(driver).assert_log("已查看任务")


@allure_compat.feature("页面交互")
def test_i04_iframe_nested(driver):
    """双层 iframe：穿透到第二层提交报销单并回主文档登记。"""
    open_scenario(driver, "/i/04")
    reason = "采购投影仪与支架报销"
    InteractBusiness(driver).run_i04(reason, "1288.5", "研发中心")
    handle = I01Handle(driver)
    handle.assert_log("主页面已同步到内层提交")
    handle.assert_log(reason)
    handle.assert_log("主文档记录：登记了本页处理记录")


@allure_compat.feature("页面交互")
def test_i05_shadow_dom(driver):
    """Shadow DOM：两层影子节点穿透操作与状态读取。"""
    open_scenario(driver, "/i/05")
    content = f"台账-{__import__('time').time_ns() % 100000}"
    InteractBusiness(driver).run_i05(content)
    handle = I01Handle(driver)
    handle.assert_log("影子外层已保存")
    handle.assert_log(content)
    handle.assert_log("影子内层子任务已执行完成")
    handle.assert_log("穿透读取外层")
    handle.assert_log("穿透读取内层")


@allure_compat.feature("页面交互")
def test_i06_dynamic_attributes(driver):
    """动态 id/class：用占位符与按钮文本定位，跨批次提交两次。"""
    open_scenario(driver, "/i/06")
    asset_no = "AS-20260906-01"
    asset_name = "园区视频会议终端"
    InteractBusiness(driver).run_i06(asset_no, asset_name)
    handle = I01Handle(driver)
    handle.assert_log("资产信息已提交")
    handle.assert_log(asset_no)


@allure_compat.feature("页面交互")
def test_i07_dropdowns(driver):
    """原生 select 与 Element 自绘下拉。"""
    open_scenario(driver, "/i/07")
    InteractBusiness(driver).run_i07("华北直辖区", "2026 年 8 月", "渠道返利", "仅直营店")
    handle = I01Handle(driver)
    handle.assert_log("原生条件查询")
    handle.assert_log("华北直辖区")
    handle.assert_log("组件条件查询")
    handle.assert_log("rebate")
    handle.assert_log("direct")


@allure_compat.feature("页面交互")
def test_i08_hover_menu(driver):
    """hover 展开的菜单与行操作。"""
    open_scenario(driver, "/i/08")
    InteractBusiness(driver).run_i08()
    handle = I01Handle(driver)
    handle.assert_log("菜单动作：执行「批量标签」")
    handle.assert_log("客户 上海恒隆商贸有限公司：执行「编辑资料」")


@allure_compat.feature("页面交互")
def test_i09_drag_drop(driver):
    """HTML5 拖拽：把候选配送员拖入已选区并确认。"""
    open_scenario(driver, "/i/09")
    InteractBusiness(driver).run_i09()
    I09Handle(driver).assert_log("分配确认：已选 1 人（陈师傅）")


@allure_compat.feature("页面交互")
def test_i10_file_upload(driver):
    """文件上传：隐藏 input[type=file] 通过 send_keys 注入文件路径。"""
    open_scenario(driver, "/i/10")
    tmp = tempfile.NamedTemporaryFile(prefix="contract_", suffix=".txt", delete=False, mode="w", encoding="utf-8")
    tmp.write("合同样本内容：设备采购补充协议")
    tmp.close()
    file_name = Path(tmp.name).name
    try:
        InteractBusiness(driver).run_i10(tmp.name)
        handle = I01Handle(driver)
        handle.assert_log("已选择本地文件")
        handle.assert_log("登记号")
        handle.assert_log(file_name)
    finally:
        Path(tmp.name).unlink(missing_ok=True)


@allure_compat.feature("页面交互")
def test_i11_native_dialogs(driver):
    """原生 alert/confirm/prompt 三类弹窗。"""
    open_scenario(driver, "/i/11")
    note = "今晚 22:00 前安排补货"
    InteractBusiness(driver).run_i11(note)
    handle = I01Handle(driver)
    handle.assert_log("已查看告警：无线降噪耳机 Pro")
    handle.assert_log("补货确认弹窗：用户选择「确定」")
    handle.assert_log(f"已登记备注：{note}")


@allure_compat.feature("页面交互")
def test_i12_rich_text(driver):
    """contenteditable 富文本：真实键入正文后发布。"""
    open_scenario(driver, "/i/12")
    title = f"中秋国庆值班安排 {__import__('time').time_ns() % 1000}"
    InteractBusiness(driver).run_i12(title, "9 月 12 日起执行节假日值班，请各部门排班确认。")
    handle = I01Handle(driver)
    handle.assert_log("公告已发布")
    handle.assert_log(title)


@allure_compat.feature("页面交互")
def test_i13_animation(driver):
    """渐入动画：等待动画结束（.entered）再点确认。"""
    open_scenario(driver, "/i/13")
    InteractBusiness(driver).run_i13()
    I01Handle(driver).assert_log("已确认阅读系统升级公告")


@allure_compat.feature("页面交互")
def test_i14_lazy_load(driver):
    """滚动懒加载：容器内滚动加载全部 160 条。"""
    open_scenario(driver, "/i/14")
    count = InteractBusiness(driver).run_i14()
    assert count == 160, f"懒加载未能加载满 160 条，当前 {count} 条"
    tip = I14Handle(driver).wait.wait_for_visible(("css selector", ".more-tip.end"))
    assert "已加载全部任务" in tip.text


@allure_compat.feature("页面交互")
def test_i15_coordinate_offset(driver):
    """坐标偏移：展开完整区域后点击溢出裁切区的目标点。"""
    open_scenario(driver, "/i/15")
    InteractBusiness(driver).run_i15()
    handle = I01Handle(driver)
    handle.assert_log("目标货架已标记，点位已写入定位单")
    handle.assert_log("目标点位 rect")


@allure_compat.feature("页面交互")
def test_i16_controlled_input(driver):
    """受控输入 + 异步联想 + 清空。"""
    open_scenario(driver, "/i/16")
    InteractBusiness(driver).run_i16("上海迅捷物流有限公司", "故障报修", "发票", "发票冲红")
    handle = I01Handle(driver)
    handle.assert_log("工单已提交")
    handle.assert_log("执行搜索：关键词「发票冲红」")
    handle.assert_log("备注已清空，可重新录入")


@allure_compat.feature("页面交互")
def test_i17_parent_child_amount(driver):
    """结算单父子金额勾稽：折叠子行 / 父子同名金额列 / 尾差与负数 / 异步重算。"""
    open_scenario(driver, "/i/17")
    biz = InteractBusiness(driver)

    # 1. 子单默认折叠：DOM 中只有 3 张父单，展开后才有 11 条子单明细
    h = biz.run_i17()
    h.assert_log("结算数据已重置为初始状态")
    assert h.row_count(h.PARENT_LEVEL) == 3
    assert h.row_count(h.CHILD_LEVEL) == 11
    h.assert_log("已展开全部父级结算单（共 3 张）")

    # 2. 父子同名金额列：只能按行层级分别读取（父=申报金额，子=明细金额）
    assert amount_equal(h.amount_of(I17_PARENT_MATCHED, h.PARENT_LEVEL), Decimal("1286500.00"))
    assert amount_equal(h.amount_of(I17_CHILD_ADJUST, h.CHILD_LEVEL), Decimal("862300.00"))
    assert h.parent_state_text(I17_PARENT_MATCHED) == "金额一致"
    assert amount_equal(h.parent_child_total(I17_PARENT_MATCHED), Decimal("1286500.00"))

    # 3. 负数以括号展示，清洗后才是真正的负值
    assert h.amount_text(I17_CHILD_NEGATIVE, h.CHILD_LEVEL) == "(¥3,400.00)"
    assert amount_equal(h.amount_of(I17_CHILD_NEGATIVE, h.CHILD_LEVEL), Decimal("-3400.00"))

    # 4. 固定一分钱尾差：申报 ¥510,710.99 vs 子单合计 ¥510,711.00（金额一律用 Decimal 容差比较）
    assert amount_equal(h.amount_of(I17_PARENT_TAIL_DIFF, h.PARENT_LEVEL), Decimal("510710.99"))
    assert amount_equal(h.parent_child_total(I17_PARENT_TAIL_DIFF), Decimal("510711.00"))
    assert amount_equal(parse_amount(h.parent_state_text(I17_PARENT_TAIL_DIFF)), Decimal("0.01"))
    assert amount_equal(h.summary_value("child"), Decimal("2102011.00"))
    assert amount_equal(h.summary_value("declared"), Decimal("2102010.99"))
    assert amount_equal(h.summary_value("diff"), Decimal("0.01"))

    # 5. 调整子单金额 -> 后台异步重算（约 0.8s）-> 父单出现 ¥100.00 差异
    h = biz.run_i17_adjust(I17_PARENT_MATCHED, I17_CHILD_ADJUST, "862400.00", "差异")
    assert amount_equal(h.amount_of(I17_CHILD_ADJUST, h.CHILD_LEVEL), Decimal("862400.00"))
    assert amount_equal(h.parent_child_total(I17_PARENT_MATCHED), Decimal("1286600.00"))
    assert amount_equal(parse_amount(h.parent_state_text(I17_PARENT_MATCHED)), Decimal("100.00"))
    assert amount_equal(h.summary_value("diff"), Decimal("100.01"))

    # 6. 恢复原金额 -> 勾稽回到一致，全量尾差仍为 0.01
    h = biz.run_i17_adjust(I17_PARENT_MATCHED, I17_CHILD_ADJUST, "862300.00", "金额一致")
    assert h.parent_state_text(I17_PARENT_MATCHED) == "金额一致"
    assert amount_equal(h.parent_child_total(I17_PARENT_MATCHED), Decimal("1286500.00"))
    assert amount_equal(h.summary_value("diff"), Decimal("0.01"))

    # 7. 收起全部 -> 子单明细被置为 display:none（DOM 仍在，故按可见行统计）
    biz.run_i17_collapse()
    assert h.row_count(h.CHILD_LEVEL) == 0
    h.assert_log("已收起全部父级结算单")


@pytest.mark.regression
@allure_compat.feature("页面交互")
def test_i18_page_db_consistency(driver):
    """页面数字 与 数据库一致性核对：期望值全部动态取自数据库，不写死任何金额/条数。

    两大部分：
    1. 静态全量核对：明细逐条、汇总卡、资金账户 —— 页面显示 ⇔ 库中原始值（库「分」→ 页面「元」）；
    2. 业务闭环：调整明细金额 -> 重算汇总 -> 结算单汇总金额合计变化 ->
       变化后的页面金额必须与数据库中金额总数一致（本用例的核心业务断言）。
    """
    open_scenario(driver, "/i/18")
    biz = InteractBusiness(driver)

    # ========== 0. 本场景会真实写库：先重建落库，保证用例可反复执行 ==========
    h = biz.run_i18_reset()
    h.assert_log("数据库已重建")

    # ========== 1. 分页口径：条数与页码全部由库/页面推导 ==========
    detail_count = h.db_detail_count()
    assert h.summary_count() == detail_count, "页面「明细条数」与库中明细行数不一致"
    page_size = len(h.stable_page_items())
    assert 0 < page_size < detail_count, "明细未分页：当前页不应就是全量"
    assert h.page_count() == (detail_count + page_size - 1) // page_size

    # ========== 2. 逐条核对：翻完全部分页（只看第一页必然漏数据） ==========
    page_map = biz.run_i18_collect_all_details()
    assert len(page_map) == detail_count, "翻完所有分页后仍与库明细行数不一致"
    for item_no, page_value in page_map.items():
        db_value = cents_to_yuan(h.db_detail_cents(item_no))
        if db_value is None:
            assert page_value is None, f"{item_no} 库中未清算，页面应显示「—」而非 {page_value}"
            continue
        assert page_value is not None and amount_equal(page_value, db_value), (
            f"{item_no} 页面金额 {page_value} 与数据库金额 {db_value} 不一致"
        )
    page_total = sum((v for v in page_map.values() if v is not None), Decimal("0"))
    assert amount_equal(page_total, cents_to_yuan(h.db_detail_sum_cents()))

    # ========== 3. NULL 未清算：样本按角色从库里挑，不写死编号 ==========
    unsettled = h.pick_detail(I18Handle.ROLE_UNSETTLED)
    h.ensure_row_visible(unsettled)  # 分页展示：目标行不在当前页时 DOM 里没有
    assert h.amount_text(unsettled) == I18Handle.UNSETTLED_TEXT
    assert h.amount_of(unsettled) is None, "未清算明细应解析为 None，而非 0 元"

    # ========== 4. 负数：库中为负 ⇔ 页面括号展示且解析为负 ==========
    negative = h.pick_detail(I18Handle.ROLE_NEGATIVE)
    h.ensure_row_visible(negative)
    negative_text = h.amount_text(negative)
    assert negative_text.startswith("(") and negative_text.endswith(")")
    assert h.amount_of(negative) < 0
    assert amount_equal(h.amount_of(negative), cents_to_yuan(h.db_detail_cents(negative)))

    # ========== 5. 汇总卡 ⇔ 库求和（汇总字段与明细求和是两类数据源） ==========
    assert amount_equal(h.summary_value("total"), cents_to_yuan(h.db_bill_sum_cents()))
    assert amount_equal(h.summary_value("available"), cents_to_yuan(h.db_available_sum_cents()))
    assert amount_equal(h.summary_value("frozen"), cents_to_yuan(h.db_frozen_sum_cents()))
    assert h.db_bill_sum_cents() != h.db_detail_sum_cents(), "汇总字段与明细求和存在漂移才需分别核对"
    assert len(h.account_numbers()) == len(h.db_rows("fund_account"))

    # ========== 6. 业务闭环：调整明细 -> 重算汇总 -> 汇总金额合计变化 -> 页面 ⇔ 库 ==========
    item_no, bill_no = h.pick_detail_in_matched_bill()
    for delta in (Decimal("100.00"), Decimal("-250.00")):  # 一增一减
        result = biz.run_i18_adjust_then_recap(item_no, bill_no, delta)
        h = result.handle

        # 6.1 业务正确性：结算单汇总金额合计的变化量 == 本次调整增量
        assert amount_equal(
            result.after_summary, result.before_summary + delta
        ), f"重算后汇总金额应为 {result.before_summary} {delta:+} = {result.before_summary + delta}"

        # 6.2 核心一致性：页面显示的汇总金额合计 == 数据库中金额总数
        assert amount_equal(
            result.after_summary, cents_to_yuan(h.db_bill_sum_cents())
        ), "页面「结算单汇总金额合计」与数据库汇总字段求和不一致"

        # 6.3 明细侧：该条页面金额 == 库明细原始值
        assert amount_equal(h.amount_of(item_no), cents_to_yuan(h.db_detail_cents(item_no)))

        # 6.4 重算效果：本单汇总字段 == 本单明细求和；库中也仍存在漂移单（重算只作用于本单）
        assert cents_to_yuan(h.db_bill_total_cents(result.bill_no)) == result.after_detail_sum
        assert h.db_bill_sum_cents() != h.db_detail_sum_cents()

    # ========== 7. 陈旧读数：入账只改库，页面不刷新；刷新后重新一致 ==========
    account_no = h.account_numbers()[0]
    before_page = h.account_amount(account_no)
    before_db = h.db_account_cents(account_no)
    posted_cents = biz.run_i18_post(account_no)
    assert posted_cents != before_db, "清算入账后库侧账户余额应发生变化"
    assert amount_equal(h.account_amount(account_no), before_page), "入账后页面应仍停留在旧快照"
    h = biz.run_i18_refresh()
    h.wait_account_amount(account_no, cents_to_yuan(posted_cents))
    h.wait_page_decimal(lambda: h.summary_value("available"), cents_to_yuan(h.db_available_sum_cents()))

    # ========== 8. 页面「数据库查询」弹窗：各表原始行数 ⇔ 直读库 ==========
    for table in ("settle_bill", "settle_detail", "fund_account"):
        rows = biz.run_i18_db_dialog(table)
        assert rows == len(h.db_rows(table)), f"{table} 弹窗原始行数与库中行数不一致"

    # ========== 9. 收尾：恢复初始落库 ==========
    biz.run_i18_reset()
