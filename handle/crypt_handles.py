"""数据加密类（E-01~E-04）场景操作层。

四个场景的共同口径：**页面上能看到的都不是可信断言源**。

- E-01 传输加密：DOM value 是明文、线上报文是密文，且每次密文都不同 → 断言服务端
  解密结果的**摘要**（日志与响应体不再回显明文，禁止拿密文做相等断言）；
- E-02 展示脱敏：页面只有掩码，个别行的 `data-raw` 是脏路径 → 断言以服务端全量明文为准；
- E-03 密文存储：页面是解密结果、库里是 AES 密文 → 必须按密钥版本解密后再比；
- E-04 报文加密：接口返回整体密文 → 解密成功 ≠ 校验通过，时间戳与签名要分开断言。

业务失败（1001/1002/1003/2001/2002/2003）HTTP 仍为 200，失败提示由全局 ElMessage
承载并会自动消失，因此断言一律读页面底部「操作结果」日志区。
"""
from __future__ import annotations

import json
import time
from decimal import Decimal

from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from handle import action_support as act
from handle.base_scenario_handle import BaseScenarioHandle
from log.user_log import get_logger
from util.amount_util import parse_amount
from util.api_client import ApiClient
from util.digest_util import password_digest
from util.network_recorder import get_network_recorder
from util.sqlite_source import SqliteSource


class E01Handle(BaseScenarioHandle):
    """传输字段加密（RSA-OAEP）：公钥异步签发 + 密文随机 + 明文通道被拒。"""

    NOT_READY = "—"  # 公钥未签发时指纹占位
    KEY_READY = "密钥已就绪"
    PLAIN_REJECTED = "明文提交失败"
    ENCRYPT_FAILED = "加密提交失败"

    # 网络层取证：页面 #request-body 是前端自证，真实报文要看浏览器网络栈
    ENC_URL = "/api/crypto/login/encrypted"
    PLAIN_URL = "/api/crypto/login/plain"

    # 摘要比对三态（前端 #digest-match）
    DIGEST_MATCHED = "一致"
    DIGEST_MISMATCHED = "不一致"
    DIGEST_NOT_COMPARED = "未比对"  # 非安全上下文：无 Web Crypto，前端无法算本地摘要
    # 摘要区无结果时的占位符：前端 .vue 用三元表达式渲染 '—'（明文提交会把 result 置 null）
    PLACEHOLDER = "—"

    def __init__(self, driver, timeout: int = 15):
        super().__init__(driver, "E01", timeout)
        self.api = ApiClient()
        self.logger = get_logger()
        # 网络层记录器（按 driver 共享）：仅 Chromium 内核可用，start() 失败时自动降级
        self.net = get_network_recorder(driver)

    # ---------------- 公钥（异步资源，不能进页面就点） ---------------- #
    def wait_pubkey_ready(self, timeout: int | None = None) -> str:
        """等待公钥签发完成：指纹从「—」变为真实指纹（接口延迟 0.3~0.8s）。"""
        deadline = time.time() + (timeout or self.wait.timeout)
        fingerprint = ""
        while time.time() < deadline:
            fingerprint = self.fingerprint()
            if fingerprint and fingerprint != self.NOT_READY:
                self.logger.info("通道公钥就绪，指纹: %s", fingerprint)
                return fingerprint
            time.sleep(0.2)
        raise AssertionError(
            f"公钥在 {timeout or self.wait.timeout}s 内未签发完成，当前指纹: {fingerprint or '（空）'}"
        )

    def fingerprint(self) -> str:
        try:
            return self.text_of("fingerprint").strip()
        except Exception:  # 首帧未渲染时按未就绪处理，交给 wait_pubkey_ready 轮询
            return ""

    def state_text(self) -> str:
        """原始读取（可能读到正在离场的旧值，断言请用 wait_state_settled）。"""
        return self.text_of("state_tag").strip()

    def wait_state_settled(self, expected: str | None = None, timeout: int | None = None) -> str:
        """等待状态标签收敛并变为期望值后再取文本。

        两处陷阱，缺一不可：
        1. el-tag 带 zoom-in 过渡动画，切换瞬间新旧两个 `.state-tag` 同时存在且都
           visible，`find_element` 只会返回正在离场的旧值 → 必须等 DOM 中只剩一个；
        2. 指纹先于状态标签更新，仅「收敛」仍可能稳定读到旧值「密钥未就绪」→ 传入
           expected 时须等到文本一致为止。
        """
        deadline = time.time() + (timeout or self.wait.timeout)
        texts: list[str] = []
        while time.time() < deadline:
            texts = [
                el.text.strip()
                for el in self.driver.find_elements(*self.loc("state_tag"))
                if el.is_displayed()
            ]
            if len(texts) == 1 and (expected is None or texts[0] == expected):
                return texts[0]
            time.sleep(0.2)
        raise AssertionError(
            f"状态标签未收敛为「{expected}」（可能仍在过渡动画中），当前: {texts}"
            if expected else f"状态标签未在超时时间内收敛（可能仍在过渡动画中），当前: {texts}"
        )

    def wait_fingerprint_changed(self, before: str, timeout: int | None = None) -> str:
        """密钥轮换后等待页面指纹刷新（旧指纹对应的密文随即失效）。"""
        deadline = time.time() + (timeout or self.wait.timeout)
        current = before
        while time.time() < deadline:
            current = self.fingerprint()
            if current and current != before:
                return current
            time.sleep(0.2)
        raise AssertionError(f"重新签发后公钥指纹未变化，仍为: {current or '（空）'}")

    def reload_pubkey(self, timeout: int | None = None) -> str:
        """点「重新签发公钥」并等待指纹刷新完成。"""
        before = self.fingerprint()
        self.click("reload_pubkey")
        self.assert_log("通道公钥就绪", timeout)
        return self.wait_fingerprint_changed(before, timeout)

    # ---------------- 表单提交 ---------------- #
    def fill_credentials(self, account: str, password: str) -> None:
        """受控输入：原生 value setter + input 事件，确保 v-model 同步。"""
        self.js_fill("account", account)
        self.js_fill("password", password)

    def submit_encrypted(self) -> None:
        self.click("submit_encrypted")

    def submit_plain(self) -> None:
        self.click("submit_plain")

    def wait_submit_success(self, password: str, timeout: int | None = None) -> str:
        """加密提交成功：服务端解密成功，且解密结果与输入明文的**摘要**一致。

        口径变更：日志与响应体不再回显明文口令（生产系统本就不该回显），稳定
        断言点从「明文相等」改为「摘要相等」。期望摘要由脚本用 hashlib 独立复算，
        不依赖前端 Web Crypto，因此非安全上下文（页面显示「未比对」）也能验证。
        """
        self.assert_log("服务端解密成功", timeout,
                        extra="；加密提交是否成功应以服务端解密结果为准")
        expect = password_digest(password)
        self.wait_server_digest(expect, timeout)
        verdict = self.wait_digest_settled(timeout)
        if verdict == self.DIGEST_NOT_COMPARED:
            # 非安全上下文：前端拿不到 crypto.subtle，退化为只校验服务端侧摘要
            self.logger.warning("当前为非安全上下文，前端未做本地摘要比对，仅校验服务端摘要")
            return expect
        assert self.local_digest().upper() == expect, (
            f"前端本地摘要与脚本复算不一致: {self.local_digest()} != {expect}"
        )
        assert verdict == self.DIGEST_MATCHED, (
            f"摘要比对结论应为「{self.DIGEST_MATCHED}」，实际: {verdict}"
        )
        return expect

    # ---------------- 摘要比对区（替代明文回显的稳定断言点） ---------------- #
    def _text_or_empty(self, key: str) -> str:
        """取值并归一化：首帧未渲染按空串处理；占位符「—」代表"无结果"，也按空串处理。"""
        try:
            value = self.text_of(key).strip()
        except Exception:
            return ""
        return "" if value == self.PLACEHOLDER else value

    def server_digest(self) -> str:
        """服务端解密后回传的明文摘要（SHA-256 前 16 位大写）。"""
        return self._text_or_empty("server_digest")

    def local_digest(self) -> str:
        """前端 Web Crypto 对输入明文算出的摘要（非安全上下文下为空）。"""
        return self._text_or_empty("local_digest")

    def digest_match(self) -> str:
        """比对结论：一致 / 不一致 / 未比对。"""
        return self._text_or_empty("digest_match")

    def masked_password(self) -> str:
        """服务端回显的掩码口令：只能作为「不等于明文」的反面证据。"""
        return self._text_or_empty("masked_password")

    def wait_server_digest(self, expect: str, timeout: int | None = None) -> str:
        """等待服务端摘要刷新为脚本复算的期望值（等 DOM 而非等日志，天然排除上轮）。"""
        deadline = time.time() + (timeout or self.wait.timeout)
        current = ""
        while time.time() < deadline:
            current = self.server_digest()
            if current and current.upper() == expect.upper():
                return current
            time.sleep(0.2)
        raise AssertionError(
            f"服务端摘要未刷新为期望值 {expect}，当前: {current or '（空）'}"
        )

    def wait_digest_settled(self, timeout: int | None = None) -> str:
        """等待比对结论渲染出终态（一致 / 不一致 / 未比对）。"""
        deadline = time.time() + (timeout or self.wait.timeout)
        verdict = ""
        while time.time() < deadline:
            verdict = self.digest_match()
            if verdict in (self.DIGEST_MATCHED, self.DIGEST_MISMATCHED, self.DIGEST_NOT_COMPARED):
                return verdict
            time.sleep(0.2)
        raise AssertionError(f"摘要比对结论未渲染出终态，当前: {verdict or '（空）'}")

    def wait_digest_cleared(self, timeout: int | None = None) -> None:
        """明文提交后摘要区应被清空：旧通道没有解密结果，不能残留上一轮的摘要。"""
        deadline = time.time() + (timeout or self.wait.timeout)
        while time.time() < deadline:
            if not (self.server_digest() or self.local_digest()):
                return
            time.sleep(0.2)
        raise AssertionError(
            f"明文提交后摘要区未清空，仍残留: 服务端 {self.server_digest() or '（空）'}"
            f" / 本地 {self.local_digest() or '（空）'}"
        )

    # ---------------- 报文（判断「是否真加密」的唯一页面依据） ---------------- #
    def request_body(self) -> str:
        return self.text_of("request_body")

    def request_payload(self) -> dict:
        try:
            return json.loads(self.request_body())
        except (ValueError, TypeError):
            return {}

    def credential_b64(self) -> str:
        return str(self.request_payload().get("credentialB64") or "")

    def wait_request_body_ready(self, timeout: int | None = None) -> str:
        """等待报文区渲染出密文字段 credentialB64。"""
        deadline = time.time() + (timeout or self.wait.timeout)
        body = ""
        while time.time() < deadline:
            body = self.request_body()
            if "credentialB64" in body:
                return body
            time.sleep(0.2)
        raise AssertionError(f"报文区在超时时间内未出现 credentialB64 字段，当前: {body or '（空）'}")

    def wait_request_body_changed(self, before: str, timeout: int | None = None) -> str:
        """等待报文刷新（同一明文重复提交时用于取第二份密文）。"""
        deadline = time.time() + (timeout or self.wait.timeout)
        body = before
        while time.time() < deadline:
            body = self.request_body()
            if body and body != before:
                return body
            time.sleep(0.2)
        raise AssertionError("重复提交后报文内容未刷新，无法验证密文随机性")

    # ---------------- 密钥轮换（服务端侧触发） ---------------- #
    def rotate_pubkey_by_api(self) -> str:
        """经接口轮换密钥对：页面仍持有旧公钥，此时再提交必然 1003。"""
        body = self.api.crypto_pubkey_rotate()
        self.logger.info("服务端已轮换 RSA 密钥对: %s", body.get("data"))
        return str(body.get("data", {}).get("fingerprint") or "")


class E02Handle(BaseScenarioHandle):
    """敏感字段脱敏展示：页面只有掩码，完整值需单独申请且限时可见。"""

    UNREGISTERED = "—"
    MASK_SIGN = "****"

    def __init__(self, driver, timeout: int = 15):
        super().__init__(driver, "E02", timeout)
        self.api = ApiClient()
        self.logger = get_logger()

    # ---------------- 列表（掩码） ---------------- #
    def refresh_list(self) -> None:
        self.click("refresh_btn")
        self.assert_log("档案列表已刷新")

    def rows(self) -> list:
        return self.driver.find_elements(*self.loc("cust_row"))

    def row(self, cust_id: int):
        return self.wait.wait_for_visible(
            (By.CSS_SELECTOR, self.xpath("row_by_id").format(id=cust_id))
        )

    def cell_text(self, cust_id: int, field: str) -> str:
        """field ∈ {mobile, idcard, balance}。"""
        return self.row(cust_id).find_element(
            By.CSS_SELECTOR, self.xpath(f"cell_{field}")
        ).text.strip()

    def data_raw(self, cust_id: int) -> str | None:
        """DOM 属性上的明文泄漏（脏路径：仅个别行有，不能作为主断言口径）。"""
        return self.row(cust_id).find_element(
            By.CSS_SELECTOR, self.xpath("cell_mobile")
        ).get_attribute("data-raw")

    def cust_ids(self) -> list[int]:
        """行主键取自服务端（页面只有掩码，编号本身是明文可直接用）。"""
        rows = self.api.crypto_masked_customers().get("data", {}).get("rows", [])
        return [int(r["id"]) for r in rows]

    # ---------------- 抽屉：限时查看明文 ---------------- #
    def click_reveal(self, cust_id: int) -> None:
        """只点按钮、不等抽屉：冷却期内的申请会失败，抽屉根本不会打开。"""
        self.wait.wait_for_clickable(
            (By.CSS_SELECTOR, self.xpath("reveal_btn").format(id=cust_id))
        ).click()

    def reveal(self, cust_id: int) -> None:
        """点「申请查看」：抽屉打开后必须立即读取，倒计时结束会自动收起。"""
        self.click_reveal(cust_id)
        self.wait.wait_for_visible(self.loc("reveal_mobile"))

    def revealed_text(self, field: str) -> str:
        return self.text_of(f"reveal_{field}").strip()

    def countdown(self) -> int:
        try:
            return int(self.text_of("reveal_countdown").strip())
        except ValueError:
            return 0

    def close_drawer(self) -> None:
        """手动收起抽屉（冷却计时不会因此重置，仍可复现「查看过于频繁」）。"""
        try:
            self.click("drawer_close")
            return
        except Exception:  # 关闭按钮不可见时退回 ESC（抽屉默认支持 ESC 关闭）
            self.logger.info("关闭按钮不可用，改用 ESC 关闭抽屉")
        self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)

    def wait_auto_collapsed(self, cust_no: str, timeout: int | None = None) -> None:
        """抽屉倒计时结束自动收起：断言以结果区日志为准。"""
        self.assert_log(f"{cust_no} 的敏感信息已自动收起", timeout or 12)

    def wait_cooldown_rejected(self, cust_no: str, timeout: int | None = None) -> None:
        """同一条记录冷却期内重复申请：code=1002。"""
        self.assert_log(f"查看客户 {cust_no} 失败", timeout)

    # ---------------- 服务端原始数据（脱敏断言的稳定数据源） ---------------- #
    def export_server_raw(self) -> dict[str, str]:
        """点「导出服务端原始数据」并按客户号取回明文手机号。"""
        self.click("raw_btn")
        self.assert_log("已取服务端原始数据")
        return self.raw_table_map()

    def raw_table_map(self) -> dict[str, str]:
        """页面「服务端原始数据」表：客户号 -> 明文手机号。"""
        out: dict[str, str] = {}
        for row in self.driver.find_elements(*self.loc("raw_row")):
            try:
                cust_no = row.find_element(By.CSS_SELECTOR, "td:nth-child(1)").text.strip()
                mobile = row.find_element(
                    By.CSS_SELECTOR, self.xpath("raw_mobile")
                ).text.strip()
            except StaleElementReferenceException:
                continue
            out[cust_no] = mobile
        return out

    def server_raw_map(self) -> dict[str, dict]:
        """接口侧全量明文：客户号 -> 整行（脱敏断言的稳定数据源）。"""
        rows = self.api.crypto_masked_raw().get("data", {}).get("rows", [])
        return {r["custNo"]: r for r in rows}


class E03Handle(BaseScenarioHandle):
    """密文存储核对（AES-256-GCM 真实落库）：页面是解密结果，库里是密文。"""

    # 列序号（1 基，与页面表头一致）
    COL_CUST_NO = 1
    COL_CUST_NAME = 2
    COL_MOBILE = 3
    COL_IDCARD = 4
    COL_BALANCE = 5
    COL_KEY_VERSION = 6

    FAIL_TEXT = "解密失败"  # 密钥版本不匹配 / 密钥已吊销
    NULL_TEXT = "—"  # 库中 NULL（未登记）

    # 密钥版本语义（从库里动态识别，不写死客户号）
    REVOKED_VERSION = "K0"

    def __init__(self, driver, timeout: int = 15):
        super().__init__(driver, "E03", timeout)
        self.api = ApiClient()
        self.logger = get_logger()
        self._source: SqliteSource | None = None

    # ---------------- 库表直读（密文侧） ---------------- #
    @property
    def source(self) -> SqliteSource:
        """密文库只读连接：库路径由被测接口返回，不写死绝对路径。"""
        if self._source is None:
            meta = self.api.crypto_vault_db_meta().get("data", {})
            self._source = SqliteSource(meta["dbPath"])
        return self._source

    def db_rows(self) -> list[dict]:
        """库表原始行：敏感字段均为密文（base64）+ 随机 IV。"""
        return self.source.rows("cust_profile")

    def db_row(self, cust_no: str) -> dict:
        for row in self.db_rows():
            if row["cust_no"] == cust_no:
                return row
        raise AssertionError(f"密文库中未找到客户 {cust_no}")

    def db_meta(self) -> dict:
        return self.api.crypto_vault_db_meta().get("data", {})

    def pick_row(self, key_version: str, field: str = "mobile_enc") -> dict:
        """按「角色」挑样本行：指定密钥版本且该字段已登记（非 NULL）。"""
        for row in self.db_rows():
            if row["key_version"] == key_version and row.get(field):
                return row
        raise AssertionError(f"密文库中没有「密钥版本={key_version} 且 {field} 非空」的样本行")

    def current_key_version(self) -> str:
        return str(self.db_meta().get("currentKeyVersion") or "")

    def decrypt_by_api(self, cipher_b64: str, iv_b64: str, key_version: str | None = None) -> dict:
        """按密钥版本解密单个字段：失败返回 2003（区分「解密失败」与「未登记」）。"""
        return self.api.crypto_vault_decrypt(cipher_b64, iv_b64, key_version)

    # ---------------- 页面（解密后的明文） ---------------- #
    def vault_rows(self) -> list:
        return self.driver.find_elements(*self.loc("vault_row"))

    def _td_text(self, row, col: int) -> str:
        return row.find_element(By.CSS_SELECTOR, f"td:nth-child({col})").text.strip()

    def row_cust_nos(self) -> list[str]:
        cust_nos: list[str] = []
        for row in self.vault_rows():
            try:
                cust_nos.append(self._td_text(row, self.COL_CUST_NO))
            except StaleElementReferenceException:
                continue
        return cust_nos

    def wait_rows_loaded(self, timeout: int | None = None) -> list[str]:
        deadline = time.time() + (timeout or self.wait.timeout)
        cust_nos: list[str] = []
        while time.time() < deadline:
            cust_nos = self.row_cust_nos()
            if cust_nos:
                return cust_nos
            time.sleep(0.2)
        raise AssertionError("档案明细在超时时间内未渲染")

    def read_current_page(self) -> dict[str, dict[str, str]]:
        """当前页行：客户号 -> {mobile/idcard/balance/keyVersion}（页面展示的是解密结果）。"""
        out: dict[str, dict[str, str]] = {}
        for row in self.vault_rows():
            try:
                out[self._td_text(row, self.COL_CUST_NO)] = {
                    "mobile": self._td_text(row, self.COL_MOBILE),
                    "idcard": self._td_text(row, self.COL_IDCARD),
                    "balance": self._td_text(row, self.COL_BALANCE),
                    "keyVersion": self._td_text(row, self.COL_KEY_VERSION),
                }
            except StaleElementReferenceException:
                continue
        return out

    # ---------------- 分页（每页 5 条，只看当前页必漏数据） ---------------- #
    def page_info(self) -> dict:
        return self.api.crypto_vault_page(1).get("data", {})

    def can_next_page(self) -> bool:
        return self.driver.find_element(*self.loc("page_next")).is_enabled()

    def goto_next_page(self, timeout: int | None = None) -> bool:
        if not self.can_next_page():
            return False
        before = self.row_cust_nos()
        self.wait.click_params(self.loc("page_next"))
        self.wait_rows_changed(before, timeout)
        return True

    def wait_rows_changed(self, before: list[str], timeout: int | None = None) -> list[str]:
        deadline = time.time() + (timeout or self.wait.timeout)
        current = before
        while time.time() < deadline:
            current = self.row_cust_nos()
            if current and current != before:
                return current
            time.sleep(0.2)
        raise AssertionError("翻页后档案明细未刷新")

    def collect_all_rows(self, timeout: int | None = None) -> dict[str, dict[str, str]]:
        """翻完全部分页取全量（页面只渲染当前页 5 行，直接计数必然漏数据）。"""
        self.wait_rows_loaded(timeout)
        collected = self.read_current_page()
        for _ in range(max(0, int(self.page_info().get("pages", 1)) - 1)):
            if not self.goto_next_page(timeout):
                break
            collected.update(self.read_current_page())
        return collected

    # ---------------- 库表原始行 / 库元信息 ---------------- #
    def query_db_raw(self) -> int:
        """点「查询库表原始行」，返回页面展示的密文行数。"""
        self.click("db_query_btn")
        self.assert_log("已读取库表原始行")
        return len(self.driver.find_elements(*self.loc("raw_row")))

    def load_meta(self, timeout: int | None = None) -> str:
        """库表信息：等元信息文案渲染（onMounted 已拉过一次，不能只等日志）。"""
        self.click("db_meta_btn")
        self.wait.is_element_visible(self.loc("db_meta_text"), timeout or self.wait.timeout)
        return self.text_of("db_meta_text").strip()

    def cipher_cells(self) -> list[str]:
        return [el.text.strip() for el in self.driver.find_elements(*self.loc("cipher_cell"))]

    # ---------------- 新档案登记 ---------------- #
    def write_profile(self, cust_no: str, cust_name: str, mobile: str, balance: str = "") -> None:
        self.js_fill("write_custno", cust_no)
        self.js_fill("write_name", cust_name)
        self.js_fill("write_mobile", mobile)
        self.js_fill("write_balance", balance)
        self.click("write_btn")
        self.assert_log(f"登记成功：{cust_no}")

    # ---------------- 密文解密核验 ---------------- #
    def decrypt_on_page(self, cipher_b64: str, iv_b64: str, key_version_label: str | None = None) -> str:
        """页面「密文解密核验」：留空=当前密钥版本；历史版本必须显式选择。"""
        self.js_fill("decrypt_input", cipher_b64)
        self.js_fill("decrypt_iv", iv_b64)
        if key_version_label:
            act.el_select_by_text(self.driver, self.loc("keyversion_select"), key_version_label)
        self.click("decrypt_btn")
        return self.text_of("decrypt_output").strip()

    def wait_decrypt_success(self, plain: str, timeout: int | None = None) -> None:
        self.assert_log("解密成功", timeout)
        deadline = time.time() + (timeout or self.wait.timeout)
        output = ""
        while time.time() < deadline:
            output = self.text_of("decrypt_output").strip()
            if plain and plain in output:
                return
            time.sleep(0.2)
        raise AssertionError(f"解密输出未还原出明文 {plain}，当前输出: {output or '（空）'}")

    def wait_decrypt_failed(self, timeout: int | None = None) -> str:
        self.assert_log("解密失败", timeout)
        return self.text_of("decrypt_output").strip()

    # ---------------- 重置（保证用例可反复执行） ---------------- #
    def reset_vault(self) -> None:
        self.click("reset_btn")
        self.assert_log("密文库已重置")
        self.wait_rows_loaded()


class E04Handle(BaseScenarioHandle):
    """接口报文整体加密 + 时间戳/签名校验：解密成功 ≠ 校验通过。"""

    MODES = {"normal": "正常报文", "expired": "过期时间戳", "tampered": "签名被篡改"}

    def __init__(self, driver, timeout: int = 15):
        super().__init__(driver, "E04", timeout)
        self.api = ApiClient()
        self.logger = get_logger()

    # ---------------- 拉取报文 ---------------- #
    def pick_mode(self, mode: str) -> None:
        """选通道状态：mode ∈ normal / expired / tampered。"""
        locator = (By.XPATH, self.xpath("mode_radio").format(mode=self.MODES[mode]))
        self.wait.click_params(locator)

    def fetch_envelope(self, mode: str) -> None:
        """拉取报文：确认页面上已是新报文后，再断言「本地解密成功」。"""
        self.pick_mode(mode)
        before = self.envelope_value_or_empty("enc")
        self.click("fetch_btn")
        self.assert_log(f"已拉取 {mode} 报文")
        # 密文每次都不同（随机 IV）：用它确认页面已换用新报文，
        # 否则「本地解密成功」会命中上一轮的历史日志，断言失去意义
        self.wait_envelope_refreshed(before)
        self.assert_log("本地解密成功")

    def envelope_value_or_empty(self, field: str) -> str:
        try:
            return self.envelope_value(field)
        except Exception:  # 首个报文尚未渲染时返回空串
            return ""

    def wait_envelope_refreshed(self, before: str, timeout: int | None = None) -> str:
        deadline = time.time() + (timeout or self.wait.timeout)
        current = before
        while time.time() < deadline:
            current = self.envelope_value_or_empty("enc")
            if current and current != before:
                return current
            time.sleep(0.2)
        raise AssertionError("拉取后报文密文未刷新，无法确认页面已换用新报文")

    def envelope_value(self, field: str) -> str:
        """服务端原始报文字段：ts / sign / enc（全为密文或摘要，不含明文）。"""
        return self.text_of(f"envelope_{field}").strip()

    def envelope_payload(self) -> dict:
        """页面当前展示的那一份报文。

        解密与验签必须基于同一份报文：接口每次都会生成新的随机 IV 与时间戳，
        重新调一次 `/crypto/envelope` 拿到的密文与页面上的不是同一份。
        """
        session = self.session_key()
        return {
            "ts": self.envelope_value("ts"),
            "sign": self.envelope_value("sign"),
            "encB64": self.envelope_value("enc"),
            "ivB64": self.envelope_value("iv"),
            "keyVersion": session.get("keyVersion"),
            "alg": session.get("alg"),
        }

    # ---------------- 解密后的成交明细 ---------------- #
    def decoded_rows(self) -> list:
        return self.driver.find_elements(*self.loc("env_row"))

    def decoded_amounts(self) -> list[Decimal]:
        """解密后渲染的成交金额（页面文本为 `¥1,286,500.00`，需清洗后比较）。"""
        amounts: list[Decimal] = []
        for row in self.decoded_rows():
            try:
                amounts.append(
                    parse_amount(
                        row.find_element(By.CSS_SELECTOR, self.xpath("env_amount")).text
                    )
                )
            except StaleElementReferenceException:
                continue
        return amounts

    # ---------------- 脚本侧解密口径（脱离浏览器亦可复算） ---------------- #
    def session_key(self) -> dict:
        return self.api.crypto_session_key().get("data", {})

    def decrypt_envelope_api(self, envelope: dict) -> list[dict]:
        """会话密钥 + 服务端解密通道：与浏览器 Web Crypto 的解密结果一致。"""
        self.session_key()
        body = self.api.crypto_decrypt(
            envelope["encB64"], envelope["ivB64"], envelope.get("keyVersion")
        )
        assert body.get("code") == 0, f"报文解密失败: {body}"
        return json.loads(body["data"]["plainText"]).get("rows", [])

    # ---------------- 时间戳 / 签名校验 ---------------- #
    def verify(self) -> None:
        self.click("verify_btn")

    def wait_verify_passed(self, timeout: int | None = None) -> None:
        self.assert_log("签名校验通过", timeout)

    def wait_verify_failed(self, keyword: str, timeout: int | None = None) -> None:
        """失败分支：keyword ∈ {时间戳已过期(2001), 内容已被篡改(2002)}。"""
        self.assert_log("签名校验未通过", timeout)
        self.assert_log(keyword, timeout)

    def verify_by_api(self, ts, sign: str, enc_b64: str) -> dict:
        """接口层验签：与页面同一套时间戳窗口（±120s）与 HMAC 签名算法。"""
        return self.api.crypto_envelope_verify(ts, sign, enc_b64)
