"""页面交互类（I-01~I-18）场景操作层。"""
from __future__ import annotations

import time
from decimal import Decimal
from typing import Callable

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.wait import WebDriverWait

from handle import action_support as act
from handle.base_scenario_handle import BaseScenarioHandle
from log.user_log import get_logger
from util.amount_util import amount_equal, cents_to_yuan, parse_amount
from util.api_client import ApiClient
from util.sqlite_source import SqliteSource


class I01Handle(BaseScenarioHandle):
    """元素不可交互：勾选须知使按钮可用；先展开折叠再操作内部控件。"""

    def __init__(self, driver):
        super().__init__(driver, "I01")

    def submit_handover(self, operator: str, note: str) -> None:
        self.fill("operator", operator)
        self.fill("note", note)
        # 勾选须知 -> 保存按钮由 disabled 变为可点击
        self.click("agree")
        self.clickable("save_btn")
        self.click("save_btn")

    def apply_advanced(self, reviewer: str) -> None:
        # 折叠内元素未展开前不存在：先展开折叠项
        self.click("collapse_adv")
        self.fill("reviewer", reviewer)
        self.click("apply_adv")


class I02Handle(BaseScenarioHandle):
    """点击被拦截：等遮罩消失 / 下载按钮可点后再下载。"""

    def __init__(self, driver):
        super().__init__(driver, "I02")

    def generate_and_wait(self, timeout: int = 15) -> None:
        self.click("gen_btn")
        # 遮罩出现后等待其消失
        act.wait_loading_mask_gone(self.driver, self.loc("mask"), timeout=timeout)

    def download_result(self) -> None:
        self.clickable("download_btn")
        self.click("download_btn")


class I03Handle(BaseScenarioHandle):
    """元素引用失效：先停自动刷新再操作，操作时重新定位。"""

    def __init__(self, driver):
        super().__init__(driver, "I03")

    def enable_auto_refresh(self, settle_seconds: float = 6.5) -> None:
        """打开自动刷新，等待至少一次整表重建。"""
        switch = self.presence("auto_switch")
        if "is-checked" not in switch.get_attribute("class"):
            switch.click()
        time.sleep(settle_seconds)

    def disable_auto_refresh(self) -> None:
        """关闭自动刷新，稳定当前列表。"""
        switch = self.presence("auto_switch")
        if "is-checked" in switch.get_attribute("class"):
            switch.click()
        time.sleep(0.5)

    def view_first_task(self) -> None:
        self.presence("table_body")
        row_btn = self.loc("row_view")
        act.retry_on_stale(self.driver, row_btn, lambda el: el.click())


class I04Handle(BaseScenarioHandle):
    """双层 iframe 内提交报销单。"""

    def __init__(self, driver):
        super().__init__(driver, "I04")

    def submit_reimburse(self, reason: str, amount: str, dept: str) -> None:
        act.switch_frame(self.driver, self.loc("frame_a"))
        self.wait.wait_for_visible(("css selector", "#innerFrame"))
        act.switch_frame(self.driver, self.loc("frame_b"))
        self.fill("reason", reason, clear_first=True)
        amount_el = self.wait.wait_for_visible(self.loc("amount"))
        amount_el.clear()
        amount_el.send_keys(amount)
        dept_select = Select(self.wait.wait_for_visible(self.loc("dept")))
        dept_select.select_by_visible_text(dept)
        self.click("submit")
        act.switch_to_default_content(self.driver)


class I05Handle(BaseScenarioHandle):
    """Shadow DOM：两层 shadowRoot 穿透操作。"""

    def __init__(self, driver):
        super().__init__(driver, "I05")

    def save_outer(self, content: str) -> None:
        host = self.presence("shadow_host")
        root = host.shadow_root
        inp = root.find_element(By.CSS_SELECTOR, "input.sinp")
        inp.clear()
        inp.send_keys(content)
        root.find_element(By.CSS_SELECTOR, "button.sbtn").click()

    def run_inner(self) -> None:
        host = self.presence("shadow_host")
        inner_host = host.shadow_root.find_element(By.CSS_SELECTOR, "shadow-inner-box")
        inner_root = inner_host.shadow_root
        inner_root.find_element(By.CSS_SELECTOR, "button.sbtn").click()

    def read_state(self) -> None:
        self.click("read_state")


class I06Handle(BaseScenarioHandle):
    """动态 id/class：只依赖 placeholder 与按钮文本。"""

    def __init__(self, driver):
        super().__init__(driver, "I06")

    def submit_asset(self, asset_no: str, asset_name: str) -> None:
        self.fill("asset_no", asset_no)
        self.fill("asset_name", asset_name)
        self.click("submit_btn")

    def regen_attributes(self) -> None:
        self.click("regen_btn")


class I07Handle(BaseScenarioHandle):
    """原生 select + 自绘下拉混排。"""

    def __init__(self, driver):
        super().__init__(driver, "I07")

    def native_query(self, region: str, period: str) -> None:
        Select(self.wait.wait_for_visible(self.loc("region"))).select_by_visible_text(region)
        Select(self.wait.wait_for_visible(self.loc("period"))).select_by_visible_text(period)
        self.click("query_native")

    def biz_query(self, biz_type: str, scope: str) -> None:
        self.click("biz_trigger")
        act.click_el_option(self.driver, biz_type)
        self.click("scope_trigger")
        act.click_el_option(self.driver, scope)
        self.click("query_biz")


class I08Handle(BaseScenarioHandle):
    """悬浮菜单。"""

    def __init__(self, driver):
        super().__init__(driver, "I08")

    def batch_label(self) -> None:
        act.hover(self.driver, self.loc("drop_trigger"))
        WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable(self.loc("drop_batch"))).click()

    def edit_customer(self) -> None:
        act.hover(self.driver, self.loc("customer_row"))
        WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable(self.loc("row_edit"))).click()


class I09Handle(BaseScenarioHandle):
    """HTML5 拖拽分配。"""

    def __init__(self, driver):
        super().__init__(driver, "I09")

    def drag_first_to_picked(self) -> None:
        chip = self.wait.wait_for_presence(self.loc("chip"))
        target = self.wait.wait_for_presence(self.loc("picked_drop"))
        act.drag_and_drop(self.driver, chip, target)
        time.sleep(0.5)

    def confirm(self) -> None:
        self.click("commit")

    def reset(self) -> None:
        self.click("reset")


class I10Handle(BaseScenarioHandle):
    """文件上传：对隐藏 input[type=file] send_keys 本地绝对路径。"""

    def __init__(self, driver):
        super().__init__(driver, "I10")

    def upload_and_register(self, abs_path: str) -> None:
        act.upload_file(self.driver, self.loc("file_input"), abs_path)
        WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable(self.loc("submit_reg"))
        ).click()


class I11Handle(BaseScenarioHandle):
    """原生 alert/confirm/prompt。"""

    def __init__(self, driver):
        super().__init__(driver, "I11")

    def alert_view(self) -> str:
        self.click("alert_btn")
        return act.accept_alert(self.driver)

    def confirm_stock(self) -> str:
        self.click("confirm_btn")
        return act.accept_alert(self.driver)

    def prompt_note(self, note: str) -> str:
        self.click("prompt_btn")
        return act.prompt_alert(self.driver, note)


class I12Handle(BaseScenarioHandle):
    """contenteditable 富文本。"""

    def __init__(self, driver):
        super().__init__(driver, "I12")

    def publish(self, title: str, body: str) -> None:
        self.fill("title", title)
        act.fill_contenteditable(self.driver, self.loc("editor"), body)
        self.click("publish")


class I13Handle(BaseScenarioHandle):
    """渐入动画：等待动画进入完成态再操作。"""

    def __init__(self, driver):
        super().__init__(driver, "I13")

    def open_and_confirm(self, timeout: int = 20) -> None:
        self.click("open_panel")
        # 等待动画完成日志出现（事件驱动，比样式类更可靠）
        self.wait.wait_for_visible(self.loc("slide_panel"))
        self.wait_log("推送面板动画完成，内容就绪", timeout=timeout)
        WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable(self.loc("confirm_btn"))
        ).click()


class I14Handle(BaseScenarioHandle):
    """滚动懒加载：容器内滚动直至加载完全部。"""

    def __init__(self, driver, max_pages: int = 20, timeout: int = 90):
        super().__init__(driver, "I14")
        self.max_pages = max_pages
        self.timeout = timeout

    def load_all(self) -> int:
        deadline = time.time() + self.timeout
        last_count = 0
        while time.time() < deadline:
            rows = self.driver.find_elements(By.CSS_SELECTOR, ".scroll-box .row")
            if not rows:
                act.scroll_container_to_bottom(self.driver, self.loc("scroll_box"))
                time.sleep(0.4)
                continue
            count = len(rows)
            tip_text = ""
            try:
                tip = self.driver.find_element(By.CSS_SELECTOR, ".more-tip")
                tip_text = tip.text
            except Exception:
                pass
            if count >= 160 or "已加载全部" in tip_text:
                return count
            if count == last_count:
                # 长时间无增长则强制滚动触发下一页
                act.scroll_container_to_bottom(self.driver, self.loc("scroll_box"))
            else:
                act.scroll_container_to_bottom(self.driver, self.loc("scroll_box"))
            last_count = count
            time.sleep(0.6)
        raise AssertionError("懒加载在超时时间内未加载完 160 条任务")

    def back_first_page(self) -> None:
        self.click("reset_btn")


class I15Handle(BaseScenarioHandle):
    """坐标偏移：先展开完整区域再点击目标点。"""

    def __init__(self, driver):
        super().__init__(driver, "I15")

    def expand_and_mark(self) -> None:
        self.click("expand_btn")
        self.click("target_dot", force_js=True)

    def inspect(self) -> None:
        self.click("inspect_btn")


class I16Handle(BaseScenarioHandle):
    """受控输入 + 异步联想：真实键入、等待联想、正确清空。"""

    def __init__(self, driver):
        super().__init__(driver, "I16")

    def submit_ticket(self, customer: str, ticket_type: str) -> None:
        self.fill("cust_input", customer)
        self.click("type_trigger")
        act.click_el_option(self.driver, ticket_type)
        self.click("submit_ticket")

    def search_suggest(self, keyword: str, expect_option: str) -> None:
        self.fill("kw_input", keyword)
        WebDriverWait(self.driver, 10).until(
            EC.visibility_of_element_located(self.loc("suggest_item"))
        )
        items = self.driver.find_elements(*self.loc("suggest_item"))
        for item in items:
            if expect_option in item.text:
                item.click()
                break
        else:
            items[0].click()
        self.click("search_btn")

    def clear_remark(self) -> None:
        self.fill("remark", "临时备注")
        self.click("clear_remark")


class I17Handle(BaseScenarioHandle):
    """结算单父子金额勾稽：树形行按 level 区分同名列，异步重算等待，金额用 Decimal 清洗后比较。

    三个核心坑：
    1. 子单未展开时 DOM 里不存在子行 —— 先展开再定位；
    2. 父子行金额单元格 class 与文案格式完全相同 —— 必须按 `el-table__row--level-N` 限定层级；
    3. 金额是格式化文本（`¥1,286,500.00`、负数 `(¥3,400.00)`）—— 断言前清洗并用容差比较。
    """

    PARENT_LEVEL = 0
    CHILD_LEVEL = 1

    def __init__(self, driver, timeout: int = 15):
        super().__init__(driver, "I17", timeout)

    # ---------------- 行定位：父子同名列靠 level class 区分 ---------------- #
    def row_xpath(self, row_id: str, level: int = PARENT_LEVEL) -> str:
        """按「单号 + 行层级」定位树形表格行（子行需先展开才存在）。"""
        return (
            f"//tr[contains(@class,'el-table__row--level-{level}')]"
            f"[.//span[contains(@class,'mono')][normalize-space(.)='{row_id}']]"
        )

    def row(self, row_id: str, level: int = PARENT_LEVEL):
        return self.wait.wait_for_visible((By.XPATH, self.row_xpath(row_id, level)))

    def rows(self, level: int = PARENT_LEVEL) -> list:
        """只统计可见行：Element Plus 折叠子行时仅置 `display:none`，DOM 节点仍在。

        因此「子单是否展开」不能用 DOM 行数判断，必须过滤不可见行。
        """
        key = "parent_row" if level == self.PARENT_LEVEL else "child_row"
        return [row for row in self.driver.find_elements(*self.loc(key)) if row.is_displayed()]

    def row_count(self, level: int = PARENT_LEVEL) -> int:
        return len(self.rows(level))

    def wait_row_count(self, level: int, expected: int, timeout: int | None = None) -> int:
        """轮询指定层级行数直到等于 expected（树形行随展开/折叠动态增删）。"""
        deadline = time.time() + (timeout or self.wait.timeout)
        count = self.row_count(level)
        while count != expected and time.time() < deadline:
            time.sleep(0.3)
            count = self.row_count(level)
        if count != expected:
            role = "父" if level == self.PARENT_LEVEL else "子"
            raise AssertionError(f"{role}单行在超时时间内未达到 {expected} 行，当前 {count} 行")
        return count

    def wait_child_rows_gone(self, timeout: int | None = None) -> None:
        """等待子行不可见（折叠后子行仍在 DOM 中，只是 display:none）。"""
        if not self.wait.wait_for_disappear(self.loc("child_row"), timeout or self.wait.timeout):
            raise AssertionError("收起后子单明细行仍然可见")

    # ---------------- 展开 / 收起 ---------------- #
    def expand_all(self, expect_children: int = 11, timeout: int | None = None) -> int:
        """子单默认折叠：点「展开全部」后等子行渲染进 DOM。"""
        self.click("expand_all")
        return self.wait_row_count(self.CHILD_LEVEL, expect_children, timeout)

    def expand_parent(self, parent_id: str, timeout: int | None = None) -> int:
        """等价路径：点父行展开箭头逐个展开（覆盖 `.el-table__expand-icon` 写法）。"""
        self.row(parent_id, self.PARENT_LEVEL).find_element(
            By.CSS_SELECTOR, self.xpath("expand_icon")
        ).click()
        deadline = time.time() + (timeout or self.wait.timeout)
        while time.time() < deadline:
            count = self.row_count(self.CHILD_LEVEL)
            if count > 0:
                return count
            time.sleep(0.3)
        raise AssertionError(f"展开父单 {parent_id} 后子单明细行始终未渲染")

    def collapse_all(self, timeout: int | None = None) -> None:
        self.click("collapse_all")
        self.wait_child_rows_gone(timeout)

    def reset_data(self, expect_parents: int = 3, timeout: int | None = None) -> None:
        """重置为初始数据：父行重建且子行全部回到折叠态（用例可重复执行）。"""
        self.click("reset_btn")
        self.wait_row_count(self.PARENT_LEVEL, expect_parents, timeout)
        self.wait_child_rows_gone(timeout)

    # ---------------- 金额读取（文本 -> Decimal） ---------------- #
    def amount_text(self, row_id: str, level: int = CHILD_LEVEL) -> str:
        """读取指定层级行的「金额」列文案（父子列同名，靠 level 区分）。"""
        return self.row(row_id, level).find_element(
            By.CSS_SELECTOR, self.xpath("cell_amount")
        ).text.strip()

    def amount_of(self, row_id: str, level: int = CHILD_LEVEL) -> Decimal:
        """金额文案清洗为 Decimal（剥离 ¥ / 千分位，括号按负数处理）。"""
        return parse_amount(self.amount_text(row_id, level))

    def parent_state_text(self, parent_id: str) -> str:
        """父行勾稽状态标签：金额一致 / 差异 ¥x.xx。"""
        return self.row(parent_id, self.PARENT_LEVEL).find_element(
            By.CSS_SELECTOR, self.xpath("cell_state")
        ).text.strip()

    def parent_child_total_text(self, parent_id: str) -> str:
        """父行「子单合计 ¥x.xx」文案。"""
        return self.row(parent_id, self.PARENT_LEVEL).find_element(
            By.CSS_SELECTOR, self.xpath("cell_child_total")
        ).text.strip()

    def parent_child_total(self, parent_id: str) -> Decimal:
        return parse_amount(self.parent_child_total_text(parent_id))

    def summary_text(self, field: str) -> str:
        """读取底部汇总项：field ∈ {child, declared, diff}。"""
        return self.text_of(f"summary_{field}")

    def summary_value(self, field: str) -> Decimal:
        return parse_amount(self.summary_text(field))

    # ---------------- 调整子单金额 + 等待后台重算 ---------------- #
    def adjust_child_amount(self, child_id: str, amount: str) -> None:
        """点子行「调整」→ 写入新金额 → 保存（后台重算约 0.8s）。"""
        row = self.row(child_id, self.CHILD_LEVEL)
        row.find_element(By.XPATH, ".//button[contains(.,'调整')]").click()
        # el-input 受控组件：原生 value setter + input/change 事件，确保 v-model 同步
        self.js_fill("edit_input", amount)
        self.click("save_btn")

    def wait_parent_state(self, parent_id: str, expect: str, timeout: int | None = None) -> str:
        """轮询父单勾稽状态标签直到包含 expect（重算结果异步刷新，不能立刻断言）。"""
        deadline = time.time() + (timeout or self.wait.timeout)
        text = ""
        while time.time() < deadline:
            try:
                text = self.parent_state_text(parent_id)
                if expect in text:
                    self.logger.info("父单 %s 勾稽状态已刷新为: %s", parent_id, text)
                    return text
            except Exception:  # 行尚未渲染，继续轮询
                pass
            time.sleep(0.3)
        raise AssertionError(
            f"父单 {parent_id} 勾稽状态在超时时间内未变为含「{expect}」的文本，当前: {text or '（未读取到）'}"
        )

    def wait_recalc_done(
        self, parent_id: str, expect_state: str = "金额一致", timeout: int | None = None
    ) -> str:
        """后台重算为异步：先等结果区「重算完成」日志（事件驱动），再等父单状态刷新。"""
        timeout = timeout or self.wait.timeout
        self.assert_log(f"{parent_id} 重算完成", timeout=timeout)
        return self.wait_parent_state(parent_id, expect_state, timeout)


class I18Handle(BaseScenarioHandle):
    """页面数字 与 数据库一致性核对（SQLite 真实落库）。

    页面侧是「元 + 格式化 + 分页 + 汇总字段」，库侧是「分 + 全量 + 含 NULL」，
    四个必须脚本侧消化的差异：

    1. 单位：金额以「分」(INTEGER) 落库，页面按「元」展示 → 断言前用 `cents_to_yuan` 统一单位；
    2. 分页：页面只渲染当前页 5 行 → 直接对表格行求和必漏数据，须翻完全部分页；
    3. 汇总漂移：`settle_bill.total_amount_cents` 与明细求和是两类数据源 → 分别取、分别比；
    4. NULL：未清算明细库中为 None、页面显示「—」 → 求和按 0，且与「0 元」区分。
    """

    UNSETTLED_TEXT = "—"
    # 资金账户列序号（1 基）：3=可用资金，4=冻结资金
    ACCOUNT_COLUMN = {"available": 3, "frozen": 4}

    def __init__(self, driver, timeout: int = 15):
        super().__init__(driver, "I18", timeout)
        self.api = ApiClient()
        self.logger = get_logger()
        self._source: SqliteSource | None = None

    # ---------------- 页面：汇总卡与快照 ---------------- #
    def summary_text(self, field: str) -> str:
        """底部汇总卡文案：field ∈ {total, count, available, frozen}。"""
        return self.text_of(f"summary_{field}")

    def summary_value(self, field: str) -> Decimal:
        """汇总卡金额清洗为 Decimal（字段本身是「结算单汇总字段」合计，非明细实时求和）。"""
        return parse_amount(self.summary_text(field))

    def summary_count(self) -> int:
        return int(self.summary_text("count").replace(",", "").strip())

    def snapshot_text(self) -> str:
        """页面「数据快照」时间：判断页面读数是否陈旧。"""
        return self.text_of("snapshot")

    # ---------------- 页面：明细分页行 ---------------- #
    def detail_rows(self) -> list:
        return self.driver.find_elements(*self.loc("detail_rows"))

    def row_xpath(self, item_no: str) -> str:
        return self.xpath("detail_row").format(item=item_no)

    def row(self, item_no: str):
        """定位明细行：目标行不在当前页时自动翻页（分页表格只渲染当前页）。"""
        self.ensure_row_visible(item_no)
        return self.wait.wait_for_visible((By.XPATH, self.row_xpath(item_no)))

    def amount_text(self, item_no: str) -> str:
        """明细金额文案（`¥862,300.00` / 未清算为 `—`）。"""
        return self.row(item_no).find_element(
            By.CSS_SELECTOR, self.xpath("cell_amount")
        ).text.strip()

    def amount_of(self, item_no: str) -> Decimal | None:
        """页面金额 -> Decimal；未清算（「—」）返回 None，与「¥0.00」区分。"""
        text = self.amount_text(item_no)
        if text == self.UNSETTLED_TEXT:
            return None
        return parse_amount(text)

    def page_items(self) -> list[tuple[str, str]]:
        """当前页可见明细（编号, 金额文案）—— 只有 5 行，不能直接求和。"""
        items: list[tuple[str, str]] = []
        for row in self.detail_rows():
            try:
                item_no = row.find_element(By.CSS_SELECTOR, "span.mono").text.strip()
                amount = row.find_element(
                    By.CSS_SELECTOR, self.xpath("cell_amount")
                ).text.strip()
            except Exception:  # 处于编辑态/重渲染中的行跳过
                continue
            items.append((item_no, amount))
        return items

    def page_count(self) -> int:
        return len(self.driver.find_elements(*self.loc("pager_numbers")))

    def active_page(self) -> int:
        return int(self.text_of("pager_active").strip())

    def wait_page_size(self, expect_rows: int, timeout: int | None = None) -> list[tuple[str, str]]:
        """轮询表格行数直到达到期望值（分页为异步重渲染，直接读取可能只渲染了一部分）。"""
        deadline = time.time() + (timeout or self.wait.timeout)
        items: list[tuple[str, str]] = []
        while time.time() < deadline:
            items = self.stable_page_items()
            if len(items) == expect_rows:
                return items
            time.sleep(0.2)
        raise AssertionError(f"表格行数超时未达到 {expect_rows}，当前 {len(items)} 行")

    def stable_page_items(self, timeout: int | None = None) -> list[tuple[str, str]]:
        """当前页明细读取两次完全一致后才返回：避免 el-table 异步重渲染读到「半页」。"""
        deadline = time.time() + (timeout or self.wait.timeout)
        last: list[tuple[str, str]] = []
        while time.time() < deadline:
            current = self.page_items()
            if current and current == last:
                return current
            last = current
            time.sleep(0.15)
        raise AssertionError("明细表格在超时时间内未渲染稳定")

    def goto_page(self, no: int, expect_rows: int | None = None,
                  timeout: int | None = None) -> list[tuple[str, str]]:
        """翻到指定页并等待行数据刷新；`expect_rows` 为目标页应有行数时可做到精确等待。"""
        before = [item for item, _ in self.page_items()]
        target = self.xpath("pager_item").format(no=no)
        self.wait.wait_for_clickable((By.XPATH, target))
        self.wait.click_params((By.XPATH, target))
        deadline = time.time() + (timeout or self.wait.timeout)
        items: list[tuple[str, str]] = []
        while time.time() < deadline:
            try:
                items = self.stable_page_items(timeout=max(1.0, deadline - time.time()))
            except AssertionError:  # 尚未渲染稳定，继续下一轮
                continue
            changed = [item for item, _ in items] != before
            if changed and (expect_rows is None or len(items) == expect_rows):
                return items
            time.sleep(0.2)
        raise AssertionError(f"第 {no} 页明细在超时时间内未刷新")

    def _page_contains(self, item_no: str) -> bool:
        return any(item == item_no for item, _ in self.page_items())

    def ensure_row_visible(self, item_no: str) -> int:
        """确保目标明细行已翻到当前页（分页展示：不在当前页的行 DOM 里不存在）。"""
        if self._page_contains(item_no):
            return self.active_page()
        start = self.active_page()
        total = self.page_count()
        for offset in range(1, total + 1):
            no = (start - 1 + offset) % total + 1
            self.goto_page(no)
            if self._page_contains(item_no):
                return no
        raise AssertionError(f"全部 {total} 页中均未找到明细 {item_no}")

    def collect_all_details(self) -> dict[str, Decimal | None]:
        """翻完全部分页，取到全量明细金额（页面编号 -> Decimal；未清算为 None）。

        每页都按「应有行数」等待渲染完成，避免异步重渲染导致漏取某一页的行。
        """
        total = self.summary_count()
        pages = self.page_count()
        if self.active_page() != 1:
            self.goto_page(1)  # 回到首页，以「满页行数」作为页大小
        page_size = len(self.stable_page_items()) or total
        if pages > 1 and total > page_size:
            assert (total + page_size - 1) // page_size == pages, (
                f"页大小推导异常：共 {total} 条 / 每页 {page_size} 条，却显示 {pages} 页"
            )
        collected: dict[str, Decimal | None] = {}
        for no in range(1, pages + 1):
            expect_rows = max(1, min(page_size, total - (no - 1) * page_size))
            if self.active_page() == no:
                items = self.wait_page_size(expect_rows)
            else:
                items = self.goto_page(no, expect_rows)
            for item_no, text in items:
                collected[item_no] = None if text == self.UNSETTLED_TEXT else parse_amount(text)
        if self.active_page() != 1:
            self.goto_page(1, min(page_size, total))
        return collected

    # ---------------- 页面：资金账户 ---------------- #
    def account_row_xpath(self, account_no: str) -> str:
        return self.xpath("account_row").format(account=account_no)

    def account_amount_text(self, account_no: str, kind: str = "available") -> str:
        row = self.wait.wait_for_visible((By.XPATH, self.account_row_xpath(account_no)))
        return row.find_element(
            By.XPATH, self.xpath("account_cell").format(idx=self.ACCOUNT_COLUMN[kind])
        ).text.strip()

    def account_amount(self, account_no: str, kind: str = "available") -> Decimal:
        return parse_amount(self.account_amount_text(account_no, kind))

    def account_numbers(self) -> list[str]:
        """页面资金账户账号列表（服务端默认对第一行记账，勿写死账号）。"""
        numbers = []
        for row in self.driver.find_elements(*self.loc("account_rows")):
            try:
                numbers.append(row.find_element(By.CSS_SELECTOR, "span.mono").text.strip())
            except Exception:  # 重渲染中的行跳过
                continue
        return numbers

    # ---------------- 数据库：按「角色」动态挑选样本 ---------------- #
    @staticmethod
    def ROLE_UNSETTLED(row: dict) -> bool:
        """未清算：库中金额为 NULL，页面显示「—」。"""
        return row["amount_cents"] is None

    @staticmethod
    def ROLE_NEGATIVE(row: dict) -> bool:
        """负数：库中为负，页面以括号展示。"""
        return (row["amount_cents"] or 0) < 0

    def pick_detail(self, role: Callable[[dict], bool]) -> str:
        """按角色从库中挑一条明细编号（样本不写死，随被测数据量自适应）。"""
        for row in self.db_rows("settle_detail"):
            if role(row):
                return row["item_no"]
        raise AssertionError(f"库中不存在符合角色 {getattr(role, '__name__', role)} 的明细样本")

    def pick_detail_in_matched_bill(self) -> tuple[str, str]:
        """挑一条「所属结算单汇总字段 == 明细求和」的已清算明细。

        只有重算前本就勾稽一致的结算单，重算后汇总金额的变化量才等于本次调整增量，
        断言才能用「汇率增量」而不是写死的金额。
        """
        for bill in self.db_rows("settle_bill"):
            bill_no = bill["bill_no"]
            if bill["total_amount_cents"] != self.db_detail_sum_cents(bill_no):
                continue
            for row in self.db_rows("settle_detail", bill_no):
                if row["amount_cents"] is not None:
                    return row["item_no"], bill_no
        raise AssertionError("库中不存在「汇总字段与明细求和一致」的结算单")

    # ---------------- 页面异步刷新：轮询等待 ---------------- #
    def wait_page_decimal(self, reader: Callable[[], Decimal | None], expected: Decimal,
                          timeout: int | None = None) -> Decimal:
        """轮询页面数字直到与 expected 一致（页面保存/刷新为异步，不能立刻断言）。"""
        deadline = time.time() + (timeout or self.wait.timeout)
        actual: Decimal | None = None
        while time.time() < deadline:
            try:
                actual = reader()
            except Exception:  # 行正在重渲染
                actual = None
            if actual is not None and amount_equal(actual, expected):
                return actual
            time.sleep(0.3)
        raise AssertionError(f"页面数字在超时时间内未刷新为 {expected}，当前: {actual}")

    def wait_detail_amount(self, item_no: str, expected: Decimal, timeout: int | None = None) -> Decimal:
        return self.wait_page_decimal(lambda: self.amount_of(item_no), expected, timeout)

    def wait_account_amount(self, account_no: str, expected: Decimal, kind: str = "available",
                            timeout: int | None = None) -> Decimal:
        return self.wait_page_decimal(lambda: self.account_amount(account_no, kind), expected, timeout)

    # ---------------- 数据库：SQLite 直读 ---------------- #
    def source(self) -> SqliteSource:
        """库文件路径由被测服务 `/api/dbconsistency/db/meta` 返回，不写死。"""
        if self._source is None:
            meta = self.api.dbconsistency_meta()["data"]
            self._source = SqliteSource(meta["dbPath"])
        return self._source

    def db_rows(self, table: str, key: str | None = None) -> list[dict]:
        return self.source().rows(table, key)

    def db_detail(self, item_no: str) -> dict:
        for row in self.db_rows("settle_detail"):
            if row["item_no"] == item_no:
                return row
        raise AssertionError(f"数据库中不存在明细 {item_no}")

    def db_detail_cents(self, item_no: str) -> int | None:
        """明细金额原始值（分）；未清算为 None。"""
        return self.db_detail(item_no)["amount_cents"]

    def db_detail_count(self) -> int:
        return len(self.db_rows("settle_detail"))

    def db_detail_sum_cents(self, bill_no: str | None = None) -> int:
        """明细求和（分）：NULL 按 0 处理，且不把「未清算」当 0 元以外的其它语义。"""
        return sum((row["amount_cents"] or 0) for row in self.db_rows("settle_detail", bill_no))

    def db_bill_total_cents(self, bill_no: str) -> int:
        """结算单汇总字段（分）——与明细求和是两类数据源。"""
        rows = self.db_rows("settle_bill", bill_no)
        if not rows:
            raise AssertionError(f"数据库中不存在结算单 {bill_no}")
        return rows[0]["total_amount_cents"]

    def db_bill_sum_cents(self) -> int:
        return sum(row["total_amount_cents"] for row in self.db_rows("settle_bill"))

    def db_account_cents(self, account_no: str, column: str = "available_cents") -> int:
        rows = self.db_rows("fund_account", account_no)
        if not rows:
            raise AssertionError(f"数据库中不存在资金账号 {account_no}")
        return rows[0][column]

    def db_available_sum_cents(self) -> int:
        return sum(row["available_cents"] for row in self.db_rows("fund_account"))

    def db_frozen_sum_cents(self) -> int:
        return sum(row["frozen_cents"] for row in self.db_rows("fund_account"))

    # ---------------- 数据库：轮询等待落库 ---------------- #
    def wait_db_equals(self, reader: Callable[[], object], expected, timeout: int | None = None):
        """轮询数据库直到 reader() == expected（写库有 0.6s 延迟，接口返回不代表可读）。"""
        deadline = time.time() + (timeout or self.wait.timeout)
        actual = None
        while time.time() < deadline:
            try:
                actual = reader()
            except Exception:
                actual = None
            if actual == expected:
                return actual
            time.sleep(0.3)
        raise AssertionError(f"数据库值在超时时间内未刷新为 {expected}，当前: {actual}")

    def wait_db_changed(self, reader: Callable[[], object], old_value, timeout: int | None = None):
        """轮询数据库直到值发生变化，返回新值（用于「入账已落库」这类未知终值场景）。"""
        deadline = time.time() + (timeout or self.wait.timeout)
        actual = old_value
        while time.time() < deadline:
            try:
                actual = reader()
            except Exception:
                actual = old_value
            if actual != old_value:
                return actual
            time.sleep(0.3)
        raise AssertionError(f"数据库值在超时时间内未发生变化，仍为 {old_value}")

    # ---------------- 页面操作 ---------------- #
    def refresh(self) -> str:
        """刷新数据快照：把「已入账但未刷新」的陈旧读数同步回来。"""
        self.click("refresh_btn")
        self.assert_log("已刷新数据快照")
        return self.snapshot_text()

    def reset_data(self) -> None:
        """重建 SQLite 落库并回到初始数据（用例可重复执行）。"""
        self.click("reset_btn")
        self.assert_log("数据库已重建")

    def adjust_detail(self, item_no: str, amount: str) -> None:
        """页面调整明细金额：只写明细表，不回写结算单汇总字段。"""
        row = self.row(item_no)
        row.find_element(By.XPATH, self.xpath("row_adjust")).click()
        # el-input 受控组件：原生 value setter + input/change，确保 v-model 同步
        self.js_fill("edit_input", amount)
        row.find_element(By.XPATH, self.xpath("row_save")).click()
        self.assert_log(f"提交明细 {item_no} 金额调整为")

    def recap_bill(self, item_no: str) -> None:
        """点明细行「重算汇总」：按明细求和回写所属结算单的汇总字段。"""
        self.row(item_no).find_element(By.XPATH, self.xpath("row_recap")).click()

    def post_account(self) -> None:
        """模拟清算入账：直接改数据库，页面不刷新（制造页面与库的短暂不一致）。"""
        self.click("post_btn")
        self.assert_log("页面数据未自动刷新")

    # ---------------- 数据库查询弹窗 ---------------- #
    def open_db_dialog(self) -> str:
        """打开「数据库查询」弹窗，返回库文件路径。"""
        self.click("open_db_btn")
        self.visible("dialog")
        self.wait.wait_for_presence(self.loc("db_rows"))
        return self.text_of("db_path")

    def query_db_table(self, table: str) -> int:
        """弹窗内切换表并执行查询，返回原始行数（金额单位：分，NULL 显示 NULL）。"""
        act.el_select_by_text(self.driver, self.loc("db_select"), table)
        self.click("db_query_btn")
        # 被测接口处理与按钮 disabled 均有约 0.6s 延迟：先跨过这段，再等行数连续两次稳定，
        # 否则读到的是上一次查询的残留行（表间行数恰好相同时尤其危险）。
        time.sleep(0.6)
        deadline = time.time() + self.wait.timeout
        last = -1
        rows = 0
        while time.time() < deadline:
            rows = len(self.driver.find_elements(*self.loc("db_rows")))
            if rows > 0 and rows == last:
                return rows
            last = rows
            time.sleep(0.2)
        raise AssertionError(f"数据库查询弹窗未渲染出 {table} 的查询结果，当前 {rows} 行")

    def close_db_dialog(self) -> None:
        self.click("dialog_close")
        if not self.wait.wait_for_disappear(self.loc("dialog")):
            raise AssertionError("数据库查询弹窗未能关闭")
