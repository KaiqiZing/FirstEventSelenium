"""数据加密类业务（E-01~E-04）。

业务层只负责「组合动作 + 以正确口径断言」，所有期望值一律来自：
1. 服务端数据源接口（`/crypto/masked/raw`、`/crypto/vault/db/query`）；
2. 解密后的明文（`/crypto/decrypt`、`/crypto/vault/decrypt`）；
3. 页面「操作结果」日志区（ElMessage 提示会自动消失，不能抓浮层）。
"""
from __future__ import annotations

import time
from typing import NamedTuple

from util import allure_compat
from business.business_context import biz_step
from handle.crypt_handles import E01Handle, E02Handle, E03Handle, E04Handle
from util.digest_util import password_digest


class E03WriteResult(NamedTuple):
    """E-03「同一明文重复登记」结果：两份密文必不相同，但检索摘要相同。"""

    handle: E03Handle
    first_cust_no: str
    second_cust_no: str


@allure_compat.feature("数据加密")
class CryptBusiness:
    def __init__(self, driver):
        self.driver = driver

    # ================================================================== #
    # E-01 传输字段加密（RSA-OAEP）
    # ================================================================== #
    @allure_compat.story("E-01 传输字段加密")
    def run_e01_wait_pubkey(self) -> E01Handle:
        """公钥是异步资源：进页面先等指纹就绪，不能一进来就点提交。"""
        h = E01Handle(self.driver)
        with biz_step("等待公钥异步签发完成（0.3~0.8s）"):
            h.wait_pubkey_ready()
        return h

    @allure_compat.story("E-01 传输字段加密")
    def run_e01_encrypted_login(self, account: str, password: str) -> E01Handle:
        """加密提交：断言「服务端解密摘要 == 输入明文的摘要」，而不是密文。"""
        h = E01Handle(self.driver)
        with biz_step("等待公钥就绪"):
            h.wait_pubkey_ready()
        with biz_step("填写账号密码并加密提交"):
            h.fill_credentials(account, password)
            h.submit_encrypted()
            h.wait_submit_success(password)
        return h

    @allure_compat.story("E-01 传输字段加密")
    def run_e01_ciphertext_randomness(self, account: str, password: str) -> tuple[str, str]:
        """同一明文提交两次：密文必须不同（OAEP 随机填充）→ 禁止密文相等断言。"""
        h = E01Handle(self.driver)
        with biz_step("等待公钥就绪并首次加密提交"):
            h.wait_pubkey_ready()
            h.fill_credentials(account, password)
            h.submit_encrypted()
            h.wait_submit_success(password)
            first = h.credential_b64()
        with biz_step("同明文再次提交，取第二份密文"):
            # 必须先取旧报文再点击：前端在发请求前就刷新了报文区，
            # 若把 h.request_body() 写在点击之后，取到的已是新报文，永远等不到「变化」
            before = h.request_body()
            h.submit_encrypted()
            h.wait_request_body_changed(before)
            second = h.credential_b64()
        return first, second

    @allure_compat.story("E-01 传输字段加密")
    def run_e01_plaintext_rejected(self, account: str, password: str) -> E01Handle:
        """对照组：明文通道被服务端拒绝（code=1001，HTTP 仍 200），且摘要区被清空。"""
        h = E01Handle(self.driver)
        with biz_step("走明文旧通道提交，应被服务端拒绝且不产生任何解密结果"):
            h.fill_credentials(account, password)
            h.submit_plain()
            h.assert_log(E01Handle.PLAIN_REJECTED)
            h.wait_digest_cleared()
        return h

    @allure_compat.story("E-01 传输字段加密")
    def run_e01_rotate_then_resubmit(self, account: str, password: str) -> tuple[str, str]:
        """密钥轮换：旧公钥加密的密文失效（1003），重新签发公钥后才能提交成功。"""
        h = E01Handle(self.driver)
        with biz_step("等待公钥就绪并记录当前指纹"):
            h.wait_pubkey_ready()
            before = h.fingerprint()
            h.fill_credentials(account, password)
        with biz_step("服务端轮换密钥对，页面仍用旧公钥提交（应失败）"):
            h.rotate_pubkey_by_api()
            h.submit_encrypted()
            assert h.wait_log(E01Handle.ENCRYPT_FAILED), "轮换后旧密文应解密失败（1003）"
            assert h.digest_match() != E01Handle.DIGEST_MATCHED, (
                f"轮换后不应再出现「{E01Handle.DIGEST_MATCHED}」的摘要比对结果"
            )
            assert h.server_digest().upper() != password_digest(password), (
                "轮换后旧密文不应解密成功，摘要区不得出现本次口令的摘要"
            )
        with biz_step("页面重新签发公钥后再次提交（应成功）"):
            after = h.reload_pubkey()
            h.submit_encrypted()
            h.wait_submit_success(password)
        return before, after

    # ================================================================== #
    # E-02 敏感字段脱敏展示
    # ================================================================== #
    @allure_compat.story("E-02 敏感字段脱敏")
    def run_e02_refresh(self) -> E02Handle:
        h = E02Handle(self.driver)
        with biz_step("刷新客户档案列表"):
            h.refresh_list()
        return h

    @allure_compat.story("E-02 敏感字段脱敏")
    def run_e02_reveal(self, cust_id: int) -> tuple[E02Handle, str]:
        """申请查看明文：抽屉限时自动收起，打开后须立即读取。"""
        h = E02Handle(self.driver)
        with biz_step(f"申请查看客户 {cust_id} 的敏感字段"):
            h.reveal(cust_id)
            mobile = h.revealed_text("mobile")
        return h, mobile

    @allure_compat.story("E-02 敏感字段脱敏")
    def run_e02_cooldown(self, cust_id: int, cust_no: str) -> E02Handle:
        """冷却期内重复申请同一条：code=1002（批量核对必须换记录或等冷却）。"""
        h = E02Handle(self.driver)
        with biz_step(f"冷却期内再次申请查看 {cust_no}，应被限流"):
            h.close_drawer()
            h.click_reveal(cust_id)
            h.wait_cooldown_rejected(cust_no)
        return h

    @allure_compat.story("E-02 敏感字段脱敏")
    def run_e02_export_raw(self) -> dict[str, str]:
        """导出服务端原始数据：脱敏断言的稳定数据源。"""
        h = E02Handle(self.driver)
        with biz_step("导出服务端未掩码的原始数据"):
            return h.export_server_raw()

    # ================================================================== #
    # E-03 密文存储核对
    # ================================================================== #
    @allure_compat.story("E-03 密文存储核对")
    def run_e03_reset(self) -> E03Handle:
        """重建密文库（密钥随进程生成，跨会话缓存的密文必然失效）。"""
        h = E03Handle(self.driver)
        with biz_step("重置密文库，恢复初始数据"):
            h.reset_vault()
        return h

    @allure_compat.story("E-03 密文存储核对")
    def run_e03_collect_all(self) -> dict[str, dict[str, str]]:
        """翻完全部分页取全量解密结果（页面每页只有 5 行）。"""
        h = E03Handle(self.driver)
        with biz_step("逐页翻页收集全量档案"):
            return h.collect_all_rows()

    @allure_compat.story("E-03 密文存储核对")
    def run_e03_db_dialog(self) -> tuple[int, str]:
        """页面「查询库表原始行」+「查看库表信息」。"""
        h = E03Handle(self.driver)
        with biz_step("打开库表原始行（全为密文）并读取库元信息"):
            return h.query_db_raw(), h.load_meta()

    @allure_compat.story("E-03 密文存储核对")
    def run_e03_write_twice(self, mobile: str, cust_name: str = "自动化测试客户") -> E03WriteResult:
        """同一手机号重复登记：密文必不相同，只能用摘要列做等值检索。"""
        h = E03Handle(self.driver)
        stamp = time.time_ns() % 100000
        first_no = f"C-9{stamp:05d}A"
        second_no = f"C-9{stamp:05d}B"
        with biz_step(f"首次登记 {first_no}"):
            h.write_profile(first_no, cust_name, mobile, "1000.00")
        with biz_step(f"同明文再次登记 {second_no}，应提示同明文密文共 2 份"):
            h.write_profile(second_no, cust_name, mobile, "1000.00")
            h.assert_log("同明文密文共 2 份")
        return E03WriteResult(handle=h, first_cust_no=first_no, second_cust_no=second_no)

    @allure_compat.story("E-03 密文存储核对")
    def run_e03_decrypt_by_version(self, cipher_b64: str, iv_b64: str, version: str) -> dict:
        """按密钥版本解密库里的一段密文（历史版本必须显式指定）。"""
        h = E03Handle(self.driver)
        with biz_step(f"用密钥版本 {version or '默认'} 解密该字段"):
            return h.decrypt_by_api(cipher_b64, iv_b64, version or None)

    # ================================================================== #
    # E-04 报文加密 + 时间戳/签名
    # ================================================================== #
    @allure_compat.story("E-04 报文加密签名")
    def run_e04_fetch(self, mode: str) -> E04Handle:
        """拉取报文并本地解密：解密成功与校验通过是两件事。"""
        h = E04Handle(self.driver)
        with biz_step(f"以「{E04Handle.MODES[mode]}」拉取加密报文并本地解密"):
            h.fetch_envelope(mode)
        return h

    @allure_compat.story("E-04 报文加密签名")
    def run_e04_verify_passed(self) -> E04Handle:
        h = E04Handle(self.driver)
        with biz_step("校验此报文：时间戳在窗口内且签名正确"):
            h.verify()
            h.wait_verify_passed()
        return h

    @allure_compat.story("E-04 报文加密签名")
    def run_e04_verify_failed(self, keyword: str) -> E04Handle:
        """失败分支：2001 时间戳过期 / 2002 签名被篡改。"""
        h = E04Handle(self.driver)
        with biz_step(f"校验此报文，应失败于「{keyword}」"):
            h.verify()
            h.wait_verify_failed(keyword)
        return h
