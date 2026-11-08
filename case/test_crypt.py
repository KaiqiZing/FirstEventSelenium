# coding=utf-8
"""数据加密类场景（E-01 ~ E-04）。

四个场景的共同口径：**页面上能直接看到的都不是可信断言源**。

- E-01 传输字段加密（RSA-OAEP，密文每次不同；日志/响应体不再回显明文，断言解密摘要）
- E-02 敏感字段脱敏展示（掩码 / 限时查看 / 冷却）
- E-03 客户档案密文存储核对（AES-256-GCM，多密钥版本）
- E-04 接口报文加密 + 时间戳/签名校验

断言口径说明：
1. 期望值一律来自服务端数据源接口或「按密钥版本解密后的明文」；E-01 因明文不再回显，
   稳定断言点为「解密结果的摘要」（脚本用 hashlib 独立复算，不依赖前端 Web Crypto）；
2. 页面掩码、库中密文只能作为「不可直接相等」的反面证据；
3. 业务失败（1001/1002/1003/2001/2002/2003）HTTP 仍为 200，
   且失败提示由 ElMessage 承载会自动消失，故一律读页面底部「操作结果」日志区。
"""
from __future__ import annotations

import json
import time
from decimal import Decimal

import pytest
from selenium.webdriver.common.by import By

from business.crypt_business import CryptBusiness
from handle.crypt_handles import E01Handle, E02Handle, E03Handle
from util import allure_compat
from util.amount_util import amount_equal
from util.api_client import ApiClient
from util.digest_util import password_digest
from util.scenario_support import open_scenario


@allure_compat.feature("数据加密")
@pytest.mark.regression
class TestCryptScenario:
    """数据加密类：断言全部落在服务端数据源 / 解密后的明文上。"""

    # ================================================================ #
    # E-01 传输字段加密
    # ================================================================ #
    def test_e01_transport_encryption(self, driver):
        """公钥异步签发 → 摘要比对（明文不再回显）→ 明文通道被拒 → 密钥轮换后旧密文失效。

        证据分级（由强到弱），网络层是本次新增的第 2 级：
        1. 脚本 hashlib 独立复算摘要 —— 期望值来源，完全不依赖被测系统；
        2. 浏览器网络层真实请求/响应体（CDP）—— 替代页面报文区的前端自证；
        3. 接口层 ApiClient —— Firefox 等无 CDP 时的兜底，并负责触发服务端状态变更；
        4. 页面日志区 / 摘要锚点 —— 只验证前端渲染与交互是否正确。
        """
        open_scenario(driver, "/e/01")
        biz = CryptBusiness(driver)
        account = "fund001"
        # 口令每次随机：摘要随之变化，才不会命中上一轮的旧日志与旧摘要
        password = f"Pwd-{time.time_ns() % 1000000:06d}"
        expect_digest = password_digest(password)

        # 1. 公钥是异步资源（0.3~0.8s），进页面就提交必然失败
        #    el-tag 有过渡动画，切换瞬间新旧标签并存，须等收敛后再读
        h: E01Handle = biz.run_e01_wait_pubkey()
        # 指纹先于状态标签更新，只等「DOM 收敛」仍会稳定读到旧值，故一并等期望文案
        state = h.wait_state_settled(E01Handle.KEY_READY)
        assert state == E01Handle.KEY_READY, f"公钥未就绪时不能提交: {state}"

        # 网络层取证：必须在提交**之前**开启，否则 requestId 无效、取不到响应体。
        # 非 Chromium 内核会返回 False 并告警，后续网络断言整体跳过（不阻断用例）
        net = h.net
        net.start()

        # 2. 加密提交：断言服务端解密结果的摘要，而不是密文
        biz.run_e01_encrypted_login(account, password)

        # 3. 浏览器网络层：真实发出的请求体 + 真实收到的响应体
        #    页面 #request-body 由前端自己渲染，属自证；这里看的是网络栈实际内容
        wire = net.try_wait_record(E01Handle.ENC_URL)
        if wire:
            req_json = wire.get("req_json") or {}
            resp_json = wire.get("resp_json") or {}
            assert password not in json.dumps(req_json, ensure_ascii=False), (
                f"真实请求体中出现明文口令，传输加密失效: {req_json}"
            )
            assert req_json.get("credentialB64"), f"实际请求报文缺少密文字段: {req_json}"
            assert req_json["credentialB64"] != password, "密文字段不应等于明文口令"
            assert req_json.get("keyVersion"), (
                f"请求应携带 keyVersion，否则服务端无法选择对应私钥: {req_json}"
            )
            assert wire.get("status") == 200, (
                f"业务失败时 HTTP 仍应为 200，实际: {wire.get('status')}"
            )
            assert resp_json.get("code") == 0, f"服务端解密失败: {resp_json}"
            wire_data = resp_json.get("data") or {}
            assert wire_data.get("decrypted") is True, f"服务端未解密成功: {wire_data}"
            assert str(wire_data.get("serverDigest") or "").upper() == expect_digest, (
                f"网络层摘要与脚本复算不一致: {wire_data.get('serverDigest')} != {expect_digest}"
            )
            assert "revealedPassword" not in wire_data, (
                "网络层响应回显了明文口令（CRYPTO_ECHO_PLAINTEXT 应为 False）"
            )

        # 4. 页面报文区：前端自证，仅验证展示正确，不作为「加密是否生效」的判据
        body = h.wait_request_body_ready()
        assert password not in body, f"请求体中出现明文口令，传输加密失效: {body}"
        payload = h.request_payload()
        assert payload.get("credentialB64"), f"报文缺少密文字段 credentialB64: {body}"
        assert payload["credentialB64"] != password, "密文字段不应等于明文口令"
        # 交叉验证：页面声称发出的密文 == 网络层真实发出的密文（前端没造假）
        if wire:
            assert payload["credentialB64"] == (wire.get("req_json") or {}).get("credentialB64"), (
                "页面报文区与网络层真实报文不一致，前端展示不可信"
            )

        # 5. 摘要三处互校：脚本独立复算 / 前端本地摘要 / 服务端解密摘要
        #    （wait_submit_success 已按「非安全上下文 → 仅校验服务端侧」处理）
        assert h.server_digest().upper() == expect_digest, (
            f"服务端解密摘要与脚本复算不一致: {h.server_digest()} != {expect_digest}"
        )
        if h.digest_match() != E01Handle.DIGEST_NOT_COMPARED:
            assert h.local_digest().upper() == expect_digest, (
                f"前端本地摘要与脚本复算不一致: {h.local_digest()} != {expect_digest}"
            )
            assert h.digest_match() == E01Handle.DIGEST_MATCHED, (
                f"摘要比对结论应为「{E01Handle.DIGEST_MATCHED}」，实际: {h.digest_match()}"
            )

        # 6. 掩码口令只能作为反面证据：不得等于明文，也不得残留完整明文
        masked = h.masked_password()
        assert masked and masked != password, f"掩码口令不应等于明文口令: {masked}"
        assert password not in masked, f"掩码口令中泄漏了完整明文: {masked}"

        # 7. 接口层响应体：与网络层结论一致，且在无 CDP 的浏览器上承担兜底
        resp = ApiClient().crypto_login_encrypted(
            account, payload["credentialB64"], payload.get("keyVersion")
        )
        assert resp.get("code") == 0, f"服务端解密失败: {resp}"
        data = resp.get("data") or {}
        assert data.get("decrypted") is True, f"服务端未解密成功: {data}"
        assert str(data.get("serverDigest") or "").upper() == expect_digest, (
            f"服务端摘要与脚本复算不一致: {data.get('serverDigest')} != {expect_digest}"
        )
        assert "revealedPassword" not in data, (
            "测试环境不应回显明文口令（CRYPTO_ECHO_PLAINTEXT 应为 False）"
        )

        # 8. 同一明文两次提交：密文必须不同（OAEP 随机填充）
        first, second = biz.run_e01_ciphertext_randomness(account, password=f"{password}A")
        assert first and second and first != second, (
            "同一明文两次加密的密文不应相同，禁止用密文做相等断言"
        )
        # 网络层复核：两条真实报文的密文互不相同，且与页面展示的第二份一致
        if net.enabled:
            wires = [
                w for w in net.records(E01Handle.ENC_URL)
                if (w.get("req_json") or {}).get("credentialB64")
            ]
            assert len(wires) >= 2, f"网络层未捕获到两次加密提交，当前仅 {len(wires)} 条"
            wire_first = wires[-2]["req_json"]["credentialB64"]
            wire_second = wires[-1]["req_json"]["credentialB64"]
            assert wire_first != wire_second, (
                "真实请求报文中同一明文两次加密的密文不应相同（OAEP 随机填充失效）"
            )
            assert wire_second == second, (
                "页面展示的第二份密文与网络层真实报文不一致，前端展示不可信"
            )

        # 9. 对照组：明文通道被服务端拒绝（code=1001，HTTP 仍 200），且摘要区被清空
        biz.run_e01_plaintext_rejected(account, password=f"{password}B")
        plain = ApiClient().crypto_login_plain(account, f"{password}B")
        assert plain.get("code") == 1001, f"明文通道应返回 1001: {plain}"
        # 网络层证明对照组确实是「明文」通道：请求体里就该是原始口令
        plain_wire = net.try_wait_record(E01Handle.PLAIN_URL) if net.enabled else None
        if plain_wire:
            plain_req = plain_wire.get("req_json") or {}
            assert plain_req.get("password") == f"{password}B", (
                f"对照组请求体应携带明文口令，实际: {plain_req}"
            )
            assert (plain_wire.get("resp_json") or {}).get("code") == 1001, (
                f"明文通道网络层响应应为 1001，实际: {plain_wire.get('resp_json')}"
            )

        # 10. 密钥轮换：轮换前的密文失效（1003），重新签发公钥后才能提交成功
        before, after = biz.run_e01_rotate_then_resubmit(account, f"{password}C")
        assert before != after, f"轮换并重新签发后公钥指纹应变化: {before} -> {after}"
        if net.enabled:
            codes = [
                (w.get("resp_json") or {}).get("code")
                for w in net.records(E01Handle.ENC_URL)
            ]
            assert 1003 in codes, f"网络层未捕获到密钥轮换导致的 1003，实际 code 序列: {codes}"

        # session 级 driver 跨用例复用，用完必须关闭 Network 域
        net.stop()

    # ================================================================ #
    # E-02 敏感字段脱敏展示
    # ================================================================ #
    def test_e02_masked_display(self, driver):
        """页面只有掩码 → 完整值须单独申请 → 限时收起 + 冷却 → 以服务端原文为准。"""
        open_scenario(driver, "/e/02")
        biz = CryptBusiness(driver)
        h = biz.run_e02_refresh()

        rows_meta = h.api.crypto_masked_customers()["data"]["rows"]
        raw = h.server_raw_map()
        assert len(rows_meta) == len(raw) == 5, f"档案条数异常: {len(rows_meta)} / {len(raw)}"

        # 1. 页面只有掩码：完整值不能从页面文本取
        page_text = driver.find_element(By.TAG_NAME, "body").text
        for meta in rows_meta:
            source = raw[meta["custNo"]]
            mobile = h.cell_text(meta["id"], "mobile")
            assert "****" in mobile, f"手机号未脱敏: {mobile}"
            assert "****" in h.cell_text(meta["id"], "idcard"), "证件号码未脱敏"
            assert source["mobile"] not in page_text, (
                f"页面文本中泄漏了明文手机号 {source['mobile']}"
            )
            # 未登记是「—」，已登记一律掩码（与「余额为 0」区分开）
            expected = "¥ ****.**" if source["balance"] else E02Handle.UNREGISTERED
            assert h.cell_text(meta["id"], "balance") == expected, (
                f"{meta['custNo']} 余额掩码异常: {h.cell_text(meta['id'], 'balance')}"
            )

        # 2. data-raw 是脏路径：只有个别行有，不能当主断言口径
        leaked = {m["custNo"]: h.data_raw(m["id"]) for m in rows_meta}
        leaked = {no: v for no, v in leaked.items() if v}
        assert 0 < len(leaked) < len(rows_meta), (
            f"data-raw 只应存在于个别行，当前: {sorted(leaked)}"
        )
        for cust_no, value in leaked.items():
            assert value == raw[cust_no]["mobile"], (
                f"{cust_no} 的 data-raw 与服务端明文不一致: {value}"
            )

        # 3. 申请查看：抽屉限时可见，打开后必须立即读取
        target = rows_meta[0]
        h, mobile = biz.run_e02_reveal(target["id"])
        assert mobile == raw[target["custNo"]]["mobile"], (
            f"抽屉明文与服务端不一致: {mobile} != {raw[target['custNo']]['mobile']}"
        )
        assert h.countdown() > 0, "抽屉未展示倒计时，无法验证限时收起"

        # 4. 冷却期内重复申请同一条：code=1002
        biz.run_e02_cooldown(target["id"], target["custNo"])
        h.wait_auto_collapsed(target["custNo"])

        # 5. 服务端原始数据：脱敏断言的稳定数据源
        exported = biz.run_e02_export_raw()
        assert len(exported) == len(raw), f"服务端原始数据条数异常: {len(exported)}"
        for cust_no, source in raw.items():
            assert exported.get(cust_no) == source["mobile"], (
                f"{cust_no} 服务端原始数据未还原明文: {exported.get(cust_no)}"
            )

    # ================================================================ #
    # E-03 客户档案密文存储核对
    # ================================================================ #
    def test_e03_cipher_storage(self, driver):
        """库里是 AES-256-GCM 密文 → 按密钥版本解密后才可与页面明文比对。"""
        open_scenario(driver, "/e/03")
        biz = CryptBusiness(driver)
        h = biz.run_e03_reset()
        meta = h.db_meta()
        db_rows = h.db_rows()
        assert len(db_rows) == meta["rows"], "密文库行数与库元信息不一致"
        assert h.page_info()["pages"] >= 2, "样本数据需跨页，才能覆盖翻页口径"

        # 1. 库中敏感字段一定是密文：不是纯数字，且带随机 IV + GCM 认证标签
        for row in db_rows:
            for field in ("mobile_enc", "idcard_enc", "balance_enc"):
                cipher = row[field]
                if not cipher:
                    continue
                assert not cipher.isdigit(), (
                    f"{row['cust_no']}.{field} 疑似明文入库: {cipher}"
                )
                assert len(cipher) >= 24, (
                    f"{row['cust_no']}.{field} 密文过短，未包含随机 IV 与认证标签: {cipher}"
                )

        # 2. 页面「库表原始行」同样只有密文
        raw_count, meta_text = biz.run_e03_db_dialog()
        assert raw_count == meta["rows"], f"库表原始行条数异常: {raw_count}"
        assert meta["dbPath"] in meta_text, f"库表信息未回显库路径: {meta_text}"
        assert meta["currentKeyVersion"] in meta_text, f"库表信息未回显当前密钥版本: {meta_text}"
        assert h.cipher_cells(), "库表原始行未渲染密文"

        # 3. 页面展示的是解密结果：必须按密钥版本解密后再比（且不能只看当前页）
        page_rows = biz.run_e03_collect_all()
        assert len(page_rows) == meta["rows"], (
            "页面只渲染当前页 5 行，直接计数必然漏数据"
        )
        for row in db_rows:
            cust_no = row["cust_no"]
            page_row = page_rows.get(cust_no)
            assert page_row, f"翻页后仍未收集到客户 {cust_no}"
            assert page_row["keyVersion"] == row["key_version"], (
                f"{cust_no} 密钥版本不一致: 页面 {page_row['keyVersion']} / 库 {row['key_version']}"
            )
            for cipher_field, iv_field, page_field in (
                ("mobile_enc", "mobile_iv", "mobile"),
                ("idcard_enc", "idcard_iv", "idcard"),
                ("balance_enc", "balance_iv", "balance"),
            ):
                if not row[cipher_field]:
                    # 未登记：库中 NULL → 页面「—」，解密接口 2003（与「解密失败」文案不同）
                    assert page_row[page_field] == E03Handle.NULL_TEXT, (
                        f"{cust_no}.{page_field} 库中为 NULL，页面应为「—」"
                    )
                    body = biz.run_e03_decrypt_by_version(row[cipher_field], row[iv_field], "")
                    assert body.get("code") == 2003, f"{cust_no}.{page_field} 未登记应返回 2003: {body}"
                    continue
                if row["key_version"] == E03Handle.REVOKED_VERSION:
                    assert page_row[page_field] == E03Handle.FAIL_TEXT, (
                        f"{cust_no}.{page_field} 已吊销密钥应展示「解密失败」"
                    )
                    continue
                body = biz.run_e03_decrypt_by_version(
                    row[cipher_field], row[iv_field], row["key_version"]
                )
                assert body.get("code") == 0, f"{cust_no}.{page_field} 解密失败: {body}"
                assert body["data"]["plainText"] == page_row[page_field], (
                    f"{cust_no}.{page_field} 解密结果({body['data']['plainText']})"
                    f" 与页面({page_row[page_field]})不一致"
                )
                assert row[cipher_field] != page_row[page_field], (
                    f"{cust_no}.{page_field} 库中不应存明文"
                )

        # 4. 多密钥版本：历史版本密文必须显式指定版本才能解开
        versions = sorted({r["key_version"] for r in db_rows})
        historical = next(
            (v for v in versions if v != h.current_key_version() and v != E03Handle.REVOKED_VERSION),
            None,
        )
        assert historical, f"密文库缺少历史密钥版本样本: {versions}"
        old_row = h.pick_row(historical)
        failed = biz.run_e03_decrypt_by_version(old_row["mobile_enc"], old_row["mobile_iv"], "")
        assert failed.get("code") == 2003, f"历史版本密文用默认密钥解密应失败: {failed}"
        ok = biz.run_e03_decrypt_by_version(
            old_row["mobile_enc"], old_row["mobile_iv"], historical
        )
        assert ok.get("code") == 0, f"显式指定 {historical} 后应解密成功: {ok}"

        # 页面「密文解密核验」区：留空（默认版本）解不开，选中历史版本才行
        h.decrypt_on_page(old_row["mobile_enc"], old_row["mobile_iv"])
        assert "解密失败" in h.wait_decrypt_failed(), "默认密钥版本应解不开历史密文"
        plain = ok["data"]["plainText"]
        h.decrypt_on_page(old_row["mobile_enc"], old_row["mobile_iv"], f"{historical}（历史）")
        h.wait_decrypt_success(plain)

        # 5. 同一明文重复登记：密文不同，等值检索只能靠摘要列
        mobile = f"139{time.time_ns() % 100000000:08d}"
        result = biz.run_e03_write_twice(mobile)
        first = result.handle.db_row(result.first_cust_no)
        second = result.handle.db_row(result.second_cust_no)
        assert first["mobile_enc"] != second["mobile_enc"], "同明文两次加密的密文竟然相同"
        assert first["mobile_iv"] != second["mobile_iv"], "IV 应每次随机生成"
        assert first["mobile_hmac"] == second["mobile_hmac"], "等值检索只能依赖摘要列"

        # 6. 复原密文库，保证用例可重复执行
        biz.run_e03_reset()

    # ================================================================ #
    # E-04 接口报文加密 + 时间戳/签名
    # ================================================================ #
    def test_e04_response_encryption(self, driver):
        """接口只给密文 → 本地解密 ≠ 校验通过 → 时间戳过期与签名篡改分别断言。"""
        open_scenario(driver, "/e/04")
        biz = CryptBusiness(driver)

        # 1. 正常报文：通道上只有密文，解密后与页面一致
        h = biz.run_e04_fetch("normal")
        payload = h.envelope_payload()
        assert payload["encB64"] and payload["ivB64"], f"报文字段缺失: {payload}"
        decoded = h.decrypt_envelope_api(payload)
        assert len(decoded) == 5, f"解密后明细条数异常: {len(decoded)}"
        assert len(h.decoded_rows()) == len(decoded), "页面渲染条数与解密结果不一致"

        # 密文里不能出现任何明文业务字段
        for row in decoded:
            assert row["customer"] not in payload["encB64"], "密文中泄漏了客户名称"
            assert row["tradeNo"] not in payload["encB64"], "密文中泄漏了成交编号"

        # 金额口径：页面千分位文本清洗后与解密值按容差比较
        page_amounts = h.decoded_amounts()
        api_amounts = [Decimal(str(r["amount"])) for r in decoded]
        assert len(page_amounts) == len(api_amounts), (
            f"金额条数不一致: 页面 {len(page_amounts)} / 解密 {len(api_amounts)}"
        )
        for actual, expected in zip(page_amounts, api_amounts):
            assert amount_equal(actual, expected), f"金额不一致: 页面 {actual} / 解密 {expected}"

        # 2. 校验通过：时间戳在 ±120s 窗口内且签名正确
        biz.run_e04_verify_passed()
        verify = h.verify_by_api(payload["ts"], payload["sign"], payload["encB64"])
        assert verify.get("code") == 0, f"正常报文校验应通过: {verify}"
        assert verify["data"]["ageSeconds"] <= 120, f"报文偏差超出有效窗口: {verify}"

        # 3. 过期时间戳：解密照样成功，但校验 2001（解密成功 ≠ 校验通过）
        h = biz.run_e04_fetch("expired")
        assert len(h.decoded_rows()) == 5, "过期报文仍可解密，只是校验不通过"
        biz.run_e04_verify_failed("时间戳已过期")

        # 4. 签名被篡改：明细照样渲染出来，但校验 2002
        h = biz.run_e04_fetch("tampered")
        assert len(h.decoded_rows()) == 5, "被篡改报文仍能解密，必须靠签名校验兜底"
        biz.run_e04_verify_failed("内容已被篡改")
